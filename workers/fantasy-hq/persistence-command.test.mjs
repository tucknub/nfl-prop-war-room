import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";

import {
  FANTASY_PERSISTENCE_PROTOCOL_VERSION,
  SYNC_FAILED,
  SYNC_START,
  SYNC_SUCCESS,
  UnsafeFantasyPersistenceCommand,
  buildPersistenceStatementsFromCommand,
  executeFantasyPersistenceCommand,
} from "./persistence-command.mjs";


const IDENTITY = {
  league_season_id: "ffl:2026",
  platform: "SLEEPER",
  platform_league_id: "league-2026",
  season: "2026",
};

function sha256(value) {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

function normalizedState(overrides = {}) {
  return JSON.stringify({
    league: {
      platform: "SLEEPER",
      platform_league_id: "league-2026",
      season: "2026",
      status: "in_season",
      rules_ready: true,
      draft_ready: true,
      ownership_ready: true,
      ...overrides,
    },
    transactions: [],
  });
}

function startCommand(overrides = {}) {
  return {
    protocol_version: FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    kind: SYNC_START,
    identity: { ...IDENTITY },
    sync_run_id: "sync-1",
    started_at_ms: 100,
    request_metadata_json: '{"trigger":"manual"}',
    ...overrides,
  };
}

function failedCommand(overrides = {}) {
  return {
    protocol_version: FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    kind: SYNC_FAILED,
    identity: { ...IDENTITY },
    sync_run_id: "sync-1",
    completed_at_ms: 150,
    error_code: "SLEEPER_TIMEOUT",
    error_summary: "provider unavailable",
    ...overrides,
  };
}

function event(overrides = {}) {
  return {
    event_fingerprint: "a".repeat(64),
    event_type: "PLAYER_ADDED",
    before_snapshot_id: "snap-before",
    after_snapshot_id: "snap-after",
    platform_roster_id: "1",
    platform_player_id: "player-2",
    before_value_json: '{"owner_roster_id":null}',
    after_value_json: '{"owner_roster_id":"1"}',
    source_transaction_ids_json: '["tx-1"]',
    reason_codes_json: '["OWNERSHIP_CHANGED"]',
    derived_at_ms: 125,
    ...overrides,
  };
}

function successCommand(overrides = {}) {
  const normalized = normalizedState();
  return {
    protocol_version: FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    kind: SYNC_SUCCESS,
    identity: { ...IDENTITY },
    sync_run_id: "sync-1",
    snapshot: {
      snapshot_id: "snap-after",
      content_fingerprint: sha256(normalized),
      observed_at_ms: 120,
      accepted_at_ms: 121,
      provider_status: "HEALTHY",
      rules_ready: true,
      draft_ready: true,
      ownership_ready: true,
      normalized_state_json: normalized,
      source_metadata_json: '{"catalog_status":"HIT"}',
    },
    events: [event()],
    completed_at_ms: 130,
    ...overrides,
  };
}

function mockDb() {
  const calls = { prepared: [], batches: [] };
  return {
    calls,
    db: {
      prepare(sql) {
        const record = { sql, parameters: [] };
        calls.prepared.push(record);
        return {
          bind(...parameters) {
            record.parameters = parameters;
            return { record };
          },
        };
      },
      async batch(prepared) {
        calls.batches.push(prepared);
        return prepared.map(() => ({
          success: true,
          meta: {
            changes: 1,
            rows_read: 0,
            rows_written: 1,
            changed_db: true,
          },
        }));
      },
    },
  };
}


test("rejects unsupported protocol versions and command kinds", async () => {
  await assert.rejects(
    buildPersistenceStatementsFromCommand(startCommand({ protocol_version: 2 })),
    /unsupported persistence protocol version/,
  );
  await assert.rejects(
    buildPersistenceStatementsFromCommand(startCommand({ kind: "RUN_SQL" })),
    /unsupported persistence command kind/,
  );
});


test("rejects caller-supplied SQL and every other unknown top-level field", async () => {
  await assert.rejects(
    buildPersistenceStatementsFromCommand(startCommand({ sql: "DROP TABLE anything" })),
    /unsupported field\(s\): sql/,
  );
});


test("builds SYNC_START from a fixed SQL template", async () => {
  const [statement] = await buildPersistenceStatementsFromCommand(startCommand());

  assert.match(statement.sql, /^INSERT INTO fantasy_sync_runs/);
  assert.deepEqual(statement.parameters, [
    "sync-1",
    "ffl:2026",
    "SLEEPER",
    "league-2026",
    "2026",
    100,
    "STARTED",
    '{"trigger":"manual"}',
  ]);
  assert.equal(statement.expected_affected_rows, 1);
});


test("builds SYNC_FAILED as a constrained STARTED-only update", async () => {
  const [statement] = await buildPersistenceStatementsFromCommand(failedCommand());

  assert.match(statement.sql, /^UPDATE fantasy_sync_runs SET completed_at_ms/);
  assert.match(statement.sql, /status = \?$/);
  assert.deepEqual(statement.parameters.slice(-2), ["2026", "STARTED"]);
  assert.equal(statement.expected_affected_rows, 1);
});


test("builds successful snapshot, event, and completion statements in order", async () => {
  const statements = await buildPersistenceStatementsFromCommand(successCommand());

  assert.equal(statements.length, 3);
  assert.match(statements[0].sql, /^INSERT INTO fantasy_state_snapshots/);
  assert.match(statements[0].sql, /status = 'STARTED'/);
  assert.match(statements[1].sql, /^INSERT INTO fantasy_change_events/);
  assert.match(statements[2].sql, /^UPDATE fantasy_sync_runs SET completed_at_ms/);
  assert.equal(statements[0].parameters[0], "snap-after");
  assert.equal(statements[1].parameters[0], "a".repeat(64));
  assert.equal(statements[1].parameters[7], "snap-after");
  assert.equal(statements[2].parameters[2], "snap-after");
  assert.ok(statements.every((row) => row.expected_affected_rows === 1));
});


test("rejects snapshot content whose SHA-256 fingerprint was tampered", async () => {
  const command = successCommand();
  command.snapshot.content_fingerprint = "f".repeat(64);

  await assert.rejects(
    buildPersistenceStatementsFromCommand(command),
    /content_fingerprint does not match normalized_state_json/,
  );
});


test("rejects normalized state identity and readiness mismatches", async () => {
  const wrongIdentityJson = normalizedState({ platform_league_id: "other-league" });
  const wrongIdentity = successCommand();
  wrongIdentity.snapshot.normalized_state_json = wrongIdentityJson;
  wrongIdentity.snapshot.content_fingerprint = sha256(wrongIdentityJson);
  await assert.rejects(
    buildPersistenceStatementsFromCommand(wrongIdentity),
    /normalized league identity does not match/,
  );

  const wrongReadinessJson = normalizedState({ ownership_ready: false });
  const wrongReadiness = successCommand();
  wrongReadiness.snapshot.normalized_state_json = wrongReadinessJson;
  wrongReadiness.snapshot.content_fingerprint = sha256(wrongReadinessJson);
  await assert.rejects(
    buildPersistenceStatementsFromCommand(wrongReadiness),
    /readiness flags do not match/,
  );
});


test("rejects events that are not bound to the accepted snapshot", async () => {
  const command = successCommand({
    events: [event({ after_snapshot_id: "different-snapshot" })],
  });
  await assert.rejects(
    buildPersistenceStatementsFromCommand(command),
    /after_snapshot_id must equal command.snapshot.snapshot_id/,
  );
});


test("rejects duplicate event fingerprints", async () => {
  const command = successCommand({
    events: [event(), event({ platform_player_id: "player-3" })],
  });
  await assert.rejects(
    buildPersistenceStatementsFromCommand(command),
    /duplicate event_fingerprint/,
  );
});


test("rejects malformed JSON contracts and impossible timestamps", async () => {
  await assert.rejects(
    buildPersistenceStatementsFromCommand(
      startCommand({ request_metadata_json: "[]" }),
    ),
    /must encode a JSON object/,
  );

  const badArrays = successCommand({
    events: [event({ reason_codes_json: '["OK",3]' })],
  });
  await assert.rejects(
    buildPersistenceStatementsFromCommand(badArrays),
    /must encode an array of strings/,
  );

  const badTime = successCommand();
  badTime.snapshot.accepted_at_ms = 119;
  await assert.rejects(
    buildPersistenceStatementsFromCommand(badTime),
    /accepted_at_ms cannot precede observed_at_ms/,
  );
});


test("executes only generated statements through the D1 executor", async () => {
  const { db, calls } = mockDb();
  const result = await executeFantasyPersistenceCommand(db, successCommand());

  assert.equal(result.protocol_version, FANTASY_PERSISTENCE_PROTOCOL_VERSION);
  assert.equal(result.kind, SYNC_SUCCESS);
  assert.equal(result.sync_run_id, "sync-1");
  assert.equal(result.results.length, 3);
  assert.equal(calls.batches.length, 1);
  assert.equal(calls.prepared.length, 3);
  assert.ok(calls.prepared[0].sql.startsWith("INSERT INTO fantasy_state_snapshots"));
});
