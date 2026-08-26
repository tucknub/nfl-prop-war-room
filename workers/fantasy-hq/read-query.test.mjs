import assert from "node:assert/strict";
import { timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import { handleFantasyPersistenceRequest } from "./index.mjs";
import {
  READ_LATEST_SNAPSHOT,
  READ_LEAGUE_SEASON,
  READ_SYNC_RUN,
  UnsafeFantasyReadRequest,
  executeFantasyRead,
  parseFantasyReadPath,
} from "./read-query.mjs";

const migrationSql = readFileSync(
  new URL("../../migrations/0001_fantasy_hq_persistence.sql", import.meta.url),
  "utf8",
);
const TOKEN = "fantasy-hq-read-test-token-0123456789abcdef";
const BASE = "https://fantasy.example";

function createDatabase() {
  const sqlite = new DatabaseSync(":memory:");
  sqlite.exec("PRAGMA foreign_keys = ON");
  sqlite.exec(migrationSql);
  const sessionConstraints = [];
  const db = {
    prepare(sql) {
      return sqliteStatement(sqlite, sql);
    },
    async batch() {
      throw new Error("batch should not be used by read tests");
    },
    withSession(constraint) {
      sessionConstraints.push(constraint);
      return {
        prepare(sql) {
          return sqliteStatement(sqlite, sql);
        },
      };
    },
  };
  return { sqlite, db, sessionConstraints };
}

function sqliteStatement(sqlite, sql) {
  return {
    bind(...parameters) {
      return {
        async first() {
          return sqlite.prepare(sql).get(...parameters) ?? null;
        },
      };
    },
  };
}

function seedLeague(sqlite) {
  sqlite.prepare(
    "INSERT INTO fantasy_league_families (league_family_id, display_name, created_at_ms, metadata_json) VALUES (?, ?, ?, ?)",
  ).run("ffl", "Franchise Football League", 100, '{"source":"test"}');
  sqlite.prepare(
    "INSERT INTO fantasy_league_seasons (league_season_id, league_family_id, platform, platform_league_id, season, display_name, created_at_ms, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
  ).run(
    "ffl:2026",
    "ffl",
    "SLEEPER",
    "league-2026",
    "2026",
    "Franchise Football League 2026",
    100,
    '{"verified":true}',
  );
}

function insertCompletedSnapshot(sqlite, { syncId, snapshotId, observed, accepted, marker }) {
  sqlite.prepare(
    "INSERT INTO fantasy_sync_runs (sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) VALUES (?, ?, ?, ?, ?, ?, NULL, 'STARTED', NULL, NULL, NULL, '{}')",
  ).run(syncId, "ffl:2026", "SLEEPER", "league-2026", "2026", observed - 1);
  sqlite.prepare(
    "INSERT INTO fantasy_state_snapshots (snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, source_metadata_json) VALUES (?, ?, ?, ?, ?, ?, 1, 1, 1, ?, ?)",
  ).run(
    snapshotId,
    "ffl:2026",
    `fingerprint-${marker}`,
    observed,
    accepted,
    "OK",
    JSON.stringify({ league: { marker }, transactions: [] }),
    JSON.stringify({ source: marker }),
  );
  sqlite.prepare(
    "UPDATE fantasy_sync_runs SET completed_at_ms = ?, status = 'COMPLETED', accepted_snapshot_id = ? WHERE sync_run_id = ?",
  ).run(accepted + 1, snapshotId, syncId);
}

function workerSubtle() {
  return {
    digest(algorithm, data) {
      return globalThis.crypto.subtle.digest(algorithm, data);
    },
    timingSafeEqual(left, right) {
      return timingSafeEqual(Buffer.from(left), Buffer.from(right));
    },
  };
}

function authRequest(path, { token = TOKEN, method = "GET" } = {}) {
  const headers = new Headers();
  if (token !== null) {
    headers.set("authorization", `Bearer ${token}`);
  }
  return new Request(`${BASE}${path}`, { method, headers });
}

async function responseJson(response) {
  return JSON.parse(await response.text());
}

test("read path parser accepts only canonical exact resource paths", () => {
  assert.deepEqual(parseFantasyReadPath("/v1/fantasy/read/league-seasons/ffl%3A2026"), {
    kind: READ_LEAGUE_SEASON,
    identifier: "ffl:2026",
  });
  assert.deepEqual(parseFantasyReadPath("/v1/fantasy/read/sync-runs/sync-1"), {
    kind: READ_SYNC_RUN,
    identifier: "sync-1",
  });
  assert.deepEqual(
    parseFantasyReadPath("/v1/fantasy/read/league-seasons/ffl%3A2026/latest-snapshot"),
    { kind: READ_LATEST_SNAPSHOT, identifier: "ffl:2026" },
  );
  assert.equal(parseFantasyReadPath("/v1/fantasy/read/league-seasons"), null);
  assert.throws(
    () => parseFantasyReadPath("/v1/fantasy/read/league-seasons/ffl:2026"),
    UnsafeFantasyReadRequest,
  );
  assert.throws(
    () => parseFantasyReadPath("/v1/fantasy/read/sync-runs/%2Fetc"),
    UnsafeFantasyReadRequest,
  );
});

test("league and sync recovery reads use first-primary and fixed bound SQL", async () => {
  const { sqlite, db, sessionConstraints } = createDatabase();
  try {
    seedLeague(sqlite);
    sqlite.prepare(
      "INSERT INTO fantasy_sync_runs (sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, '{}')",
    ).run(
      "sync-failed",
      "ffl:2026",
      "SLEEPER",
      "league-2026",
      "2026",
      200,
      250,
      "FAILED",
      "PROVIDER_TIMEOUT",
      "private detail not returned",
    );

    const league = await executeFantasyRead(db, {
      kind: READ_LEAGUE_SEASON,
      identifier: "ffl:2026",
    });
    assert.equal(league.found, true);
    assert.equal(league.record.platform_league_id, "league-2026");
    assert.deepEqual(league.record.metadata, { verified: true });
    assert.equal(Object.hasOwn(league.record, "metadata_json"), false);

    const sync = await executeFantasyRead(db, {
      kind: READ_SYNC_RUN,
      identifier: "sync-failed",
    });
    assert.equal(sync.found, true);
    assert.equal(sync.record.status, "FAILED");
    assert.equal(sync.record.error_code, "PROVIDER_TIMEOUT");
    assert.equal(Object.hasOwn(sync.record, "error_summary"), false);
    assert.deepEqual(sessionConstraints, ["first-primary", "first-primary"]);
  } finally {
    sqlite.close();
  }
});

test("missing exact reads are successful found=false facts", async () => {
  const { sqlite, db } = createDatabase();
  try {
    const result = await executeFantasyRead(db, {
      kind: READ_SYNC_RUN,
      identifier: "not-there",
    });
    assert.deepEqual(result, {
      protocol_version: 1,
      kind: READ_SYNC_RUN,
      requested_id: "not-there",
      found: false,
      record: null,
    });
  } finally {
    sqlite.close();
  }
});

test("latest snapshot returns only a snapshot accepted by a completed sync", async () => {
  const { sqlite, db } = createDatabase();
  try {
    seedLeague(sqlite);
    insertCompletedSnapshot(sqlite, {
      syncId: "sync-1",
      snapshotId: "snapshot-1",
      observed: 1000,
      accepted: 1010,
      marker: "older",
    });
    insertCompletedSnapshot(sqlite, {
      syncId: "sync-2",
      snapshotId: "snapshot-2",
      observed: 2000,
      accepted: 2010,
      marker: "newer",
    });

    sqlite.prepare(
      "INSERT INTO fantasy_state_snapshots (snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, source_metadata_json) VALUES (?, ?, ?, ?, ?, ?, 1, 1, 1, ?, '{}')",
    ).run(
      "orphan-snapshot",
      "ffl:2026",
      "orphan-fingerprint",
      3000,
      3010,
      "OK",
      JSON.stringify({ league: { marker: "must-not-return" }, transactions: [] }),
    );

    const result = await executeFantasyRead(db, {
      kind: READ_LATEST_SNAPSHOT,
      identifier: "ffl:2026",
    });
    assert.equal(result.found, true);
    assert.equal(result.record.snapshot_id, "snapshot-2");
    assert.deepEqual(result.record.normalized_state, {
      league: { marker: "newer" },
      transactions: [],
    });
    assert.deepEqual(result.record.source_metadata, { source: "newer" });
    assert.equal(result.record.rules_ready, true);
    assert.equal(result.record.draft_ready, true);
    assert.equal(result.record.ownership_ready, true);
  } finally {
    sqlite.close();
  }
});

test("authenticated Worker GET recovery route executes read and never uses batch", async () => {
  const { sqlite, db, sessionConstraints } = createDatabase();
  try {
    seedLeague(sqlite);
    const response = await handleFantasyPersistenceRequest(
      authRequest("/v1/fantasy/read/league-seasons/ffl%3A2026"),
      { FANTASY_PERSISTENCE_TOKEN: TOKEN, FANTASY_DB: db },
      { subtle: workerSubtle(), logger: { error() {} } },
    );
    const payload = await responseJson(response);

    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(payload.ok, true);
    assert.equal(payload.kind, READ_LEAGUE_SEASON);
    assert.equal(payload.requested_id, "ffl:2026");
    assert.equal(payload.found, true);
    assert.deepEqual(sessionConstraints, ["first-primary"]);
  } finally {
    sqlite.close();
  }
});

test("recovery routes require auth and GET while malformed canonical IDs fail closed", async () => {
  const { sqlite, db } = createDatabase();
  try {
    const noAuth = await handleFantasyPersistenceRequest(
      authRequest("/v1/fantasy/read/sync-runs/sync-1", { token: null }),
      { FANTASY_PERSISTENCE_TOKEN: TOKEN, FANTASY_DB: db },
      { subtle: workerSubtle() },
    );
    assert.equal(noAuth.status, 401);

    const wrongMethod = await handleFantasyPersistenceRequest(
      authRequest("/v1/fantasy/read/sync-runs/sync-1", { method: "POST" }),
      { FANTASY_PERSISTENCE_TOKEN: TOKEN, FANTASY_DB: db },
      { subtle: workerSubtle() },
    );
    assert.equal(wrongMethod.status, 405);
    assert.equal(wrongMethod.headers.get("allow"), "GET");

    const nonCanonical = await handleFantasyPersistenceRequest(
      authRequest("/v1/fantasy/read/league-seasons/ffl:2026"),
      { FANTASY_PERSISTENCE_TOKEN: TOKEN, FANTASY_DB: db },
      { subtle: workerSubtle() },
    );
    assert.equal(nonCanonical.status, 400);
    assert.equal((await responseJson(nonCanonical)).error.code, "INVALID_READ_REQUEST");
  } finally {
    sqlite.close();
  }
});
