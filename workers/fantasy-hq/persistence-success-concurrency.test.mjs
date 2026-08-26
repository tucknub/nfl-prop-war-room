import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import {
  FANTASY_PERSISTENCE_PROTOCOL_VERSION,
  SYNC_SUCCESS,
  UnsafeFantasyPersistenceCommand,
  buildPersistenceStatementsFromCommand,
  executeFantasyPersistenceCommand,
} from "./persistence-command.mjs";
import { D1BatchExecutionError } from "./d1-executor.mjs";

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

function sha256(value) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function normalizedState(player = "player-2") {
  return JSON.stringify({
    league: {
      platform: "SLEEPER",
      platform_league_id: "league-2026",
      season: "2026",
      status: "in_season",
      rules_ready: true,
      draft_ready: true,
      ownership_ready: true,
      marker: player,
    },
    transactions: [],
  });
}

function event(beforeSnapshotId = "snapshot-old") {
  return {
    event_fingerprint: "a".repeat(64),
    event_type: "PLAYER_ADDED",
    before_snapshot_id: beforeSnapshotId,
    after_snapshot_id: "snapshot-new",
    platform_roster_id: "1",
    platform_player_id: "player-2",
    before_value_json: '{"owner_roster_id":null}',
    after_value_json: '{"owner_roster_id":"1"}',
    source_transaction_ids_json: "[]",
    reason_codes_json: '["OWNERSHIP_CHANGED"]',
    derived_at_ms: 220,
  };
}

function successCommand({
  expectedPreviousSnapshotId = "snapshot-old",
  events = [event()],
  snapshotId = "snapshot-new",
  marker = "player-2",
} = {}) {
  const normalized = normalizedState(marker);
  return {
    protocol_version: FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    kind: SYNC_SUCCESS,
    identity: { ...IDENTITY },
    sync_run_id: "sync-current",
    expected_previous_snapshot_id: expectedPreviousSnapshotId,
    snapshot: {
      snapshot_id: snapshotId,
      content_fingerprint: sha256(normalized),
      observed_at_ms: 210,
      accepted_at_ms: 215,
      provider_status: "HEALTHY",
      rules_ready: true,
      draft_ready: true,
      ownership_ready: true,
      normalized_state_json: normalized,
      source_metadata_json: "{}",
    },
    events,
    completed_at_ms: 230,
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

function seedAccepted(sqlite, { snapshotId, acceptedAt, syncId }) {
  sqlite.prepare(
    "INSERT INTO fantasy_state_snapshots (snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, source_metadata_json) VALUES (?, 'ffl:2026', ?, ?, ?, 'HEALTHY', 1, 1, 1, '{}', '{}')",
  ).run(snapshotId, snapshotId.padEnd(64, "a").slice(0, 64), acceptedAt - 1, acceptedAt);
  sqlite.prepare(
    "INSERT INTO fantasy_sync_runs (sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) VALUES (?, 'ffl:2026', 'SLEEPER', 'league-2026', '2026', ?, ?, 'COMPLETED', ?, NULL, NULL, '{}')",
  ).run(syncId, acceptedAt - 2, acceptedAt + 1, snapshotId);
}

function seedStarted(sqlite) {
  sqlite.prepare(
    "INSERT INTO fantasy_sync_runs (sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) VALUES ('sync-current', 'ffl:2026', 'SLEEPER', 'league-2026', '2026', 200, NULL, 'STARTED', NULL, NULL, NULL, '{}')",
  ).run();
}

test("first accepted snapshot succeeds only while no accepted prior exists", async () => {
  const { sqlite, db } = createDatabase();
  try {
    seedLeague(sqlite);
    seedStarted(sqlite);
    const command = successCommand({
      expectedPreviousSnapshotId: null,
      events: [],
      snapshotId: "snapshot-first",
    });
    const result = await executeFantasyPersistenceCommand(db, command);
    assert.equal(result.kind, SYNC_SUCCESS);
    assert.equal(
      sqlite.prepare("SELECT accepted_snapshot_id FROM fantasy_sync_runs WHERE sync_run_id='sync-current'").get().accepted_snapshot_id,
      "snapshot-first",
    );
  } finally {
    sqlite.close();
  }
});

test("first-snapshot assertion fails and rolls back if accepted state already exists", async () => {
  const { sqlite, db } = createDatabase();
  try {
    seedLeague(sqlite);
    seedAccepted(sqlite, {
      snapshotId: "snapshot-old",
      acceptedAt: 100,
      syncId: "sync-old",
    });
    seedStarted(sqlite);

    await assert.rejects(
      executeFantasyPersistenceCommand(
        db,
        successCommand({
          expectedPreviousSnapshotId: null,
          events: [],
          snapshotId: "snapshot-illegal-first",
        }),
      ),
      D1BatchExecutionError,
    );
    assert.equal(
      sqlite.prepare("SELECT COUNT(*) AS n FROM fantasy_state_snapshots WHERE snapshot_id='snapshot-illegal-first'").get().n,
      0,
    );
    assert.equal(
      sqlite.prepare("SELECT status FROM fantasy_sync_runs WHERE sync_run_id='sync-current'").get().status,
      "STARTED",
    );
  } finally {
    sqlite.close();
  }
});

test("changed-state success accepts exact current previous snapshot", async () => {
  const { sqlite, db } = createDatabase();
  try {
    seedLeague(sqlite);
    seedAccepted(sqlite, {
      snapshotId: "snapshot-old",
      acceptedAt: 100,
      syncId: "sync-old",
    });
    seedStarted(sqlite);

    await executeFantasyPersistenceCommand(db, successCommand());

    assert.equal(
      sqlite.prepare("SELECT accepted_snapshot_id FROM fantasy_sync_runs WHERE sync_run_id='sync-current'").get().accepted_snapshot_id,
      "snapshot-new",
    );
    assert.equal(
      sqlite.prepare("SELECT before_snapshot_id FROM fantasy_change_events").get().before_snapshot_id,
      "snapshot-old",
    );
  } finally {
    sqlite.close();
  }
});

test("stale expected previous snapshot fails and rolls back entire success batch", async () => {
  const { sqlite, db } = createDatabase();
  try {
    seedLeague(sqlite);
    seedAccepted(sqlite, {
      snapshotId: "snapshot-old",
      acceptedAt: 100,
      syncId: "sync-old",
    });
    seedAccepted(sqlite, {
      snapshotId: "snapshot-newer",
      acceptedAt: 150,
      syncId: "sync-newer",
    });
    seedStarted(sqlite);

    await assert.rejects(
      executeFantasyPersistenceCommand(db, successCommand()),
      D1BatchExecutionError,
    );
    assert.equal(
      sqlite.prepare("SELECT COUNT(*) AS n FROM fantasy_state_snapshots WHERE snapshot_id='snapshot-new'").get().n,
      0,
    );
    assert.equal(
      sqlite.prepare("SELECT COUNT(*) AS n FROM fantasy_change_events").get().n,
      0,
    );
    assert.equal(
      sqlite.prepare("SELECT status FROM fantasy_sync_runs WHERE sync_run_id='sync-current'").get().status,
      "STARTED",
    );
  } finally {
    sqlite.close();
  }
});

test("event before snapshot must equal expected previous snapshot", async () => {
  const bad = successCommand({
    events: [event("different-before")],
  });
  await assert.rejects(
    buildPersistenceStatementsFromCommand(bad),
    /before_snapshot_id must equal command.expected_previous_snapshot_id/,
  );
});

test("initial snapshot cannot carry change events without previous state", async () => {
  const bad = successCommand({
    expectedPreviousSnapshotId: null,
    events: [event()],
  });
  await assert.rejects(
    buildPersistenceStatementsFromCommand(bad),
    UnsafeFantasyPersistenceCommand,
  );
});
