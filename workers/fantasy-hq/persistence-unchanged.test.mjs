import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import {
  FANTASY_PERSISTENCE_PROTOCOL_VERSION,
  SYNC_UNCHANGED,
  UnsafeFantasyPersistenceCommand,
  buildPersistenceStatementsFromCommand,
  executeFantasyPersistenceCommand,
} from "./persistence-command.mjs";
import { D1WriteInvariantError } from "./d1-executor.mjs";

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

function command(overrides = {}) {
  return {
    protocol_version: FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    kind: SYNC_UNCHANGED,
    identity: { ...IDENTITY },
    sync_run_id: "sync-new",
    completed_at_ms: 250,
    accepted_snapshot_id: "snapshot-1",
    content_fingerprint: "a".repeat(64),
    ...overrides,
  };
}

function createDatabase() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec("PRAGMA foreign_keys = ON");
  sqlite.exec(migrationSql);

  const db = {
    prepare(sql) {
      return {
        bind(...parameters) {
          return { sql, parameters };
        },
      };
    },
    async batch(statements) {
      sqlite.exec("BEGIN");
      try {
        const results = statements.map(({ sql, parameters }) => {
          const result = sqlite.prepare(sql).run(...parameters);
          return {
            success: true,
            meta: {
              changes: Number(result.changes),
              rows_read: 0,
              rows_written: Number(result.changes),
              changed_db: Number(result.changes) > 0,
            },
          };
        });
        sqlite.exec("COMMIT");
        return results;
      } catch (error) {
        sqlite.exec("ROLLBACK");
        throw error;
      }
    },
  };
  return { sqlite, db };
}

function seedLeague(sqlite) {
  sqlite.prepare(
    "INSERT INTO fantasy_league_families (league_family_id, display_name, created_at_ms, metadata_json) VALUES (?, ?, ?, ?)",
  ).run("ffl", "FFL", 1, "{}");
  sqlite.prepare(
    "INSERT INTO fantasy_league_seasons (league_season_id, league_family_id, platform, platform_league_id, season, display_name, created_at_ms, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
  ).run("ffl:2026", "ffl", "SLEEPER", "league-2026", "2026", "FFL 2026", 1, "{}");
}

function seedAccepted(sqlite, { snapshotId, fingerprint, acceptedAt, syncId }) {
  sqlite.prepare(
    "INSERT INTO fantasy_state_snapshots (snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, source_metadata_json) VALUES (?, 'ffl:2026', ?, ?, ?, 'HEALTHY', 1, 1, 1, '{}', '{}')",
  ).run(snapshotId, fingerprint, acceptedAt - 1, acceptedAt);
  sqlite.prepare(
    "INSERT INTO fantasy_sync_runs (sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) VALUES (?, 'ffl:2026', 'SLEEPER', 'league-2026', '2026', ?, ?, 'COMPLETED', ?, NULL, NULL, '{}')",
  ).run(syncId, acceptedAt - 2, acceptedAt + 1, snapshotId);
}

function seedStarted(sqlite, syncId = "sync-new") {
  sqlite.prepare(
    "INSERT INTO fantasy_sync_runs (sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) VALUES (?, 'ffl:2026', 'SLEEPER', 'league-2026', '2026', 200, NULL, 'STARTED', NULL, NULL, NULL, '{}')",
  ).run(syncId);
}

test("builds one fixed STARTED-only unchanged update", async () => {
  const [statement] = await buildPersistenceStatementsFromCommand(command());
  assert.match(statement.sql, /^UPDATE fantasy_sync_runs SET completed_at_ms/);
  assert.match(statement.sql, /fantasy_state_snapshots AS latest/);
  assert.equal(statement.parameters[2], "snapshot-1");
  assert.equal(statement.parameters[12], "a".repeat(64));
  assert.equal(statement.expected_affected_rows, 1);
});

test("rejects unsupported fields and malformed fingerprints", async () => {
  await assert.rejects(
    buildPersistenceStatementsFromCommand(command({ sql: "SELECT 1" })),
    /unsupported field/,
  );
  await assert.rejects(
    buildPersistenceStatementsFromCommand(command({ content_fingerprint: "bad" })),
    UnsafeFantasyPersistenceCommand,
  );
});

test("real schema completes unchanged sync without inserting duplicate state", async () => {
  const { sqlite, db } = createDatabase();
  try {
    seedLeague(sqlite);
    seedAccepted(sqlite, {
      snapshotId: "snapshot-1",
      fingerprint: "a".repeat(64),
      acceptedAt: 100,
      syncId: "sync-old",
    });
    seedStarted(sqlite);

    const result = await executeFantasyPersistenceCommand(db, command());
    assert.equal(result.kind, SYNC_UNCHANGED);
    assert.equal(result.results.length, 1);

    const sync = sqlite.prepare(
      "SELECT status, accepted_snapshot_id FROM fantasy_sync_runs WHERE sync_run_id='sync-new'",
    ).get();
    assert.equal(sync.status, "COMPLETED");
    assert.equal(sync.accepted_snapshot_id, "snapshot-1");
    assert.equal(
      sqlite.prepare("SELECT COUNT(*) AS n FROM fantasy_state_snapshots").get().n,
      1,
    );
    assert.equal(
      sqlite.prepare("SELECT COUNT(*) AS n FROM fantasy_change_events").get().n,
      0,
    );
  } finally {
    sqlite.close();
  }
});

test("real schema rejects stale previously accepted snapshot", async () => {
  const { sqlite, db } = createDatabase();
  try {
    seedLeague(sqlite);
    seedAccepted(sqlite, {
      snapshotId: "snapshot-1",
      fingerprint: "a".repeat(64),
      acceptedAt: 100,
      syncId: "sync-old",
    });
    seedAccepted(sqlite, {
      snapshotId: "snapshot-newer",
      fingerprint: "b".repeat(64),
      acceptedAt: 150,
      syncId: "sync-newer",
    });
    seedStarted(sqlite);

    await assert.rejects(
      executeFantasyPersistenceCommand(db, command()),
      D1WriteInvariantError,
    );
    const sync = sqlite.prepare(
      "SELECT status, accepted_snapshot_id FROM fantasy_sync_runs WHERE sync_run_id='sync-new'",
    ).get();
    assert.equal(sync.status, "STARTED");
    assert.equal(sync.accepted_snapshot_id, null);
  } finally {
    sqlite.close();
  }
});

test("real schema rejects wrong content fingerprint without completing sync", async () => {
  const { sqlite, db } = createDatabase();
  try {
    seedLeague(sqlite);
    seedAccepted(sqlite, {
      snapshotId: "snapshot-1",
      fingerprint: "a".repeat(64),
      acceptedAt: 100,
      syncId: "sync-old",
    });
    seedStarted(sqlite);

    await assert.rejects(
      executeFantasyPersistenceCommand(
        db,
        command({ content_fingerprint: "b".repeat(64) }),
      ),
      D1WriteInvariantError,
    );
    assert.equal(
      sqlite.prepare(
        "SELECT status FROM fantasy_sync_runs WHERE sync_run_id='sync-new'",
      ).get().status,
      "STARTED",
    );
  } finally {
    sqlite.close();
  }
});
