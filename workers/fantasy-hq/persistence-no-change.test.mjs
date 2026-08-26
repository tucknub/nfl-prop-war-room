import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import {
  SYNC_NO_CHANGE,
  UnsafeFantasyPersistenceCommand,
  buildPersistenceStatementsFromCommand,
} from "./persistence-command.mjs";

const migrationSql = readFileSync(
  new URL("../../migrations/0001_fantasy_hq_persistence.sql", import.meta.url),
  "utf8",
);

const IDENTITY = {
  league_season_id: "ffl:2026",
  platform: "SLEEPER",
  platform_league_id: "league-2026",
  season: "2026",
};

function createDatabase() {
  const db = new DatabaseSync(":memory:");
  db.exec("PRAGMA foreign_keys = ON");
  db.exec(migrationSql);
  db.prepare(
    "INSERT INTO fantasy_league_families (league_family_id, display_name, created_at_ms, metadata_json) VALUES (?, ?, ?, ?)",
  ).run("ffl", "Franchise Football League", 1, "{}");
  db.prepare(
    "INSERT INTO fantasy_league_seasons (league_season_id, league_family_id, platform, platform_league_id, season, display_name, created_at_ms, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
  ).run(
    "ffl:2026",
    "ffl",
    "SLEEPER",
    "league-2026",
    "2026",
    "Franchise Football League 2026",
    1,
    "{}",
  );
  return db;
}

function seedAcceptedSnapshot(
  db,
  { syncId, snapshotId, fingerprint, acceptedAt },
) {
  db.prepare(
    "INSERT INTO fantasy_sync_runs (sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) VALUES (?, ?, ?, ?, ?, ?, NULL, 'STARTED', NULL, NULL, NULL, '{}')",
  ).run(
    syncId,
    "ffl:2026",
    "SLEEPER",
    "league-2026",
    "2026",
    acceptedAt - 2,
  );
  db.prepare(
    "INSERT INTO fantasy_state_snapshots (snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, source_metadata_json) VALUES (?, ?, ?, ?, ?, ?, 1, 1, 1, ?, '{}')",
  ).run(
    snapshotId,
    "ffl:2026",
    fingerprint,
    acceptedAt - 1,
    acceptedAt,
    "HEALTHY",
    JSON.stringify({
      league: {
        platform: "SLEEPER",
        platform_league_id: "league-2026",
        season: "2026",
        rules_ready: true,
        draft_ready: true,
        ownership_ready: true,
      },
      transactions: [],
    }),
  );
  db.prepare(
    "UPDATE fantasy_sync_runs SET completed_at_ms = ?, status = 'COMPLETED', accepted_snapshot_id = ? WHERE sync_run_id = ?",
  ).run(acceptedAt + 1, snapshotId, syncId);
}

function seedStartedSync(db, syncId) {
  db.prepare(
    "INSERT INTO fantasy_sync_runs (sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) VALUES (?, ?, ?, ?, ?, ?, NULL, 'STARTED', NULL, NULL, NULL, '{}')",
  ).run(syncId, "ffl:2026", "SLEEPER", "league-2026", "2026", 500);
}

function command(overrides = {}) {
  return {
    protocol_version: 1,
    kind: SYNC_NO_CHANGE,
    identity: { ...IDENTITY },
    sync_run_id: "sync-current",
    accepted_snapshot_id: "snapshot-1",
    content_fingerprint: "a".repeat(64),
    completed_at_ms: 600,
    ...overrides,
  };
}

function executeStatement(db, statement) {
  return db.prepare(statement.sql).run(...statement.parameters);
}

test("SYNC_NO_CHANGE builds one fixed STARTED-only update and no insert", async () => {
  const statements = await buildPersistenceStatementsFromCommand(command());
  assert.equal(statements.length, 1);
  const [statement] = statements;
  assert.match(statement.sql, /^UPDATE fantasy_sync_runs/);
  assert.doesNotMatch(statement.sql, /INSERT INTO fantasy_state_snapshots/);
  assert.match(statement.sql, /ORDER BY s\.accepted_at_ms DESC, s\.snapshot_id DESC LIMIT 1/);
  assert.match(statement.sql, /s\.content_fingerprint = \?/);
  assert.equal(statement.expected_affected_rows, 1);
});

test("identical latest snapshot is reused without inserting snapshot or events", async () => {
  const db = createDatabase();
  try {
    seedAcceptedSnapshot(db, {
      syncId: "sync-previous",
      snapshotId: "snapshot-1",
      fingerprint: "a".repeat(64),
      acceptedAt: 100,
    });
    seedStartedSync(db, "sync-current");

    const [statement] = await buildPersistenceStatementsFromCommand(command());
    const result = executeStatement(db, statement);
    assert.equal(Number(result.changes), 1);

    const sync = db
      .prepare(
        "SELECT status, accepted_snapshot_id FROM fantasy_sync_runs WHERE sync_run_id = ?",
      )
      .get("sync-current");
    assert.equal(sync.status, "COMPLETED");
    assert.equal(sync.accepted_snapshot_id, "snapshot-1");
    assert.equal(
      db.prepare("SELECT COUNT(*) AS count FROM fantasy_state_snapshots").get().count,
      1,
    );
    assert.equal(
      db.prepare("SELECT COUNT(*) AS count FROM fantasy_change_events").get().count,
      0,
    );
  } finally {
    db.close();
  }
});

test("stale prior snapshot cannot be reused after a newer snapshot is accepted", async () => {
  const db = createDatabase();
  try {
    seedAcceptedSnapshot(db, {
      syncId: "sync-old",
      snapshotId: "snapshot-1",
      fingerprint: "a".repeat(64),
      acceptedAt: 100,
    });
    seedAcceptedSnapshot(db, {
      syncId: "sync-newer",
      snapshotId: "snapshot-2",
      fingerprint: "b".repeat(64),
      acceptedAt: 200,
    });
    seedStartedSync(db, "sync-current");

    const [statement] = await buildPersistenceStatementsFromCommand(command());
    const result = executeStatement(db, statement);
    assert.equal(Number(result.changes), 0);

    const sync = db
      .prepare(
        "SELECT status, accepted_snapshot_id FROM fantasy_sync_runs WHERE sync_run_id = ?",
      )
      .get("sync-current");
    assert.equal(sync.status, "STARTED");
    assert.equal(sync.accepted_snapshot_id, null);
  } finally {
    db.close();
  }
});

test("content fingerprint mismatch cannot complete no-change sync", async () => {
  const db = createDatabase();
  try {
    seedAcceptedSnapshot(db, {
      syncId: "sync-previous",
      snapshotId: "snapshot-1",
      fingerprint: "b".repeat(64),
      acceptedAt: 100,
    });
    seedStartedSync(db, "sync-current");

    const [statement] = await buildPersistenceStatementsFromCommand(command());
    const result = executeStatement(db, statement);
    assert.equal(Number(result.changes), 0);
    assert.equal(
      db.prepare("SELECT status FROM fantasy_sync_runs WHERE sync_run_id = ?").get(
        "sync-current",
      ).status,
      "STARTED",
    );
  } finally {
    db.close();
  }
});

test("no-change command rejects malformed fingerprints and caller SQL", async () => {
  await assert.rejects(
    buildPersistenceStatementsFromCommand(
      command({ content_fingerprint: "not-a-hash" }),
    ),
    UnsafeFantasyPersistenceCommand,
  );
  await assert.rejects(
    buildPersistenceStatementsFromCommand(command({ sql: "DROP TABLE x" })),
    /unsupported field\(s\): sql/,
  );
});
