import assert from "node:assert/strict";
import { timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import test from "node:test";

import { executeFantasyWorkerCommand } from "./command-router.mjs";
import { handleFantasyPersistenceRequest } from "./index.mjs";
import {
  LEAGUE_SEASON_UPSERT,
  buildLeagueSeasonRegistrationStatements,
} from "./league-registration-command.mjs";
import { UnsafeFantasyPersistenceCommand } from "./persistence-command.mjs";

const fixture = JSON.parse(
  readFileSync(
    new URL("../../tests/fixtures/fantasy_league_registration_command_v1.json", import.meta.url),
    "utf8",
  ),
);
const migrationSql = readFileSync(
  new URL("../../migrations/0001_fantasy_hq_persistence.sql", import.meta.url),
  "utf8",
);
const TOKEN = "fantasy-hq-test-token-0123456789abcdef";

function createDatabase() {
  const db = new DatabaseSync(":memory:");
  db.exec("PRAGMA foreign_keys = ON");
  db.exec(migrationSql);
  return db;
}

function executeSqliteTransaction(db, statements) {
  db.exec("BEGIN");
  try {
    const results = statements.map((statement) =>
      db.prepare(statement.sql).run(...statement.parameters)
    );
    db.exec("COMMIT");
    return results;
  } catch (error) {
    db.exec("ROLLBACK");
    throw error;
  }
}

function d1Adapter(db) {
  return {
    prepare(sql) {
      return {
        sql,
        parameters: [],
        bind(...parameters) {
          return { sql, parameters };
        },
      };
    },
    async batch(statements) {
      db.exec("BEGIN");
      try {
        const results = statements.map((statement) => {
          const result = db
            .prepare(statement.sql)
            .run(...(statement.parameters ?? []));
          const changes = Number(result.changes);
          return {
            success: true,
            meta: {
              changes,
              rows_read: 0,
              rows_written: changes,
              changed_db: changes > 0,
            },
            results: [],
          };
        });
        db.exec("COMMIT");
        return results;
      } catch (error) {
        db.exec("ROLLBACK");
        throw error;
      }
    },
  };
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

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

test("cross-language fixture builds exactly two fixed SQL statements", () => {
  const statements = buildLeagueSeasonRegistrationStatements(fixture);

  assert.equal(fixture.kind, LEAGUE_SEASON_UPSERT);
  assert.equal(Object.hasOwn(fixture, "sql"), false);
  assert.equal(statements.length, 2);
  assert.match(statements[0].sql, /^INSERT INTO fantasy_league_families/);
  assert.match(statements[1].sql, /^INSERT INTO fantasy_league_seasons/);
  assert.match(statements[1].sql, /CASE WHEN/);
  assert.match(statements[1].sql, /THEN excluded\.display_name ELSE '' END/);
  assert.deepEqual(statements[0].parameters, [
    "ffl",
    "Franchise Football League",
    1787760000000,
    '{"source":"owner_config"}',
  ]);
  assert.deepEqual(statements[1].parameters, [
    "ffl:2026",
    "ffl",
    "SLEEPER",
    "league-2026",
    "2026",
    "Franchise Football League 2026",
    1787760000000,
    '{"platform_status":"in_season"}',
  ]);
});

test("exact repeat is idempotent and later labels/metadata refresh without changing created_at", () => {
  const db = createDatabase();
  try {
    executeSqliteTransaction(
      db,
      buildLeagueSeasonRegistrationStatements(fixture),
    );
    executeSqliteTransaction(
      db,
      buildLeagueSeasonRegistrationStatements(fixture),
    );

    assert.equal(
      db.prepare("SELECT COUNT(*) AS count FROM fantasy_league_families").get().count,
      1,
    );
    assert.equal(
      db.prepare("SELECT COUNT(*) AS count FROM fantasy_league_seasons").get().count,
      1,
    );

    const refreshed = clone(fixture);
    refreshed.family_display_name = "FFL";
    refreshed.season_display_name = "FFL 2026";
    refreshed.created_at_ms = 1789999999999;
    refreshed.family_metadata_json = '{"source":"owner_config","verified":true}';
    refreshed.season_metadata_json = '{"platform_status":"complete"}';
    executeSqliteTransaction(
      db,
      buildLeagueSeasonRegistrationStatements(refreshed),
    );

    const family = db
      .prepare(
        "SELECT display_name, created_at_ms, metadata_json FROM fantasy_league_families WHERE league_family_id = ?",
      )
      .get("ffl");
    assert.equal(family.display_name, "FFL");
    assert.equal(family.created_at_ms, 1787760000000);
    assert.equal(
      family.metadata_json,
      '{"source":"owner_config","verified":true}',
    );

    const season = db
      .prepare(
        "SELECT display_name, created_at_ms, metadata_json FROM fantasy_league_seasons WHERE league_season_id = ?",
      )
      .get("ffl:2026");
    assert.equal(season.display_name, "FFL 2026");
    assert.equal(season.created_at_ms, 1787760000000);
    assert.equal(season.metadata_json, '{"platform_status":"complete"}');
  } finally {
    db.close();
  }
});

test("same league_season_id with different identity fails inside SQL and rolls back family refresh", () => {
  const db = createDatabase();
  try {
    executeSqliteTransaction(
      db,
      buildLeagueSeasonRegistrationStatements(fixture),
    );

    const collision = clone(fixture);
    collision.identity.platform_league_id = "different-league";
    collision.family_display_name = "SHOULD ROLL BACK";

    assert.throws(
      () => executeSqliteTransaction(
        db,
        buildLeagueSeasonRegistrationStatements(collision),
      ),
      /CHECK constraint failed/i,
    );

    const family = db
      .prepare(
        "SELECT display_name FROM fantasy_league_families WHERE league_family_id = ?",
      )
      .get("ffl");
    assert.equal(family.display_name, "Franchise Football League");

    const season = db
      .prepare(
        "SELECT platform_league_id FROM fantasy_league_seasons WHERE league_season_id = ?",
      )
      .get("ffl:2026");
    assert.equal(season.platform_league_id, "league-2026");
  } finally {
    db.close();
  }
});

test("different league_season_id cannot claim an existing provider league identity", () => {
  const db = createDatabase();
  try {
    executeSqliteTransaction(
      db,
      buildLeagueSeasonRegistrationStatements(fixture),
    );

    const collision = clone(fixture);
    collision.identity.league_season_id = "other:2026";
    collision.league_family_id = "other";
    collision.family_display_name = "Other League";
    collision.season_display_name = "Other League 2026";

    assert.throws(
      () => executeSqliteTransaction(
        db,
        buildLeagueSeasonRegistrationStatements(collision),
      ),
      /UNIQUE constraint failed/i,
    );
    assert.equal(
      db.prepare(
        "SELECT COUNT(*) AS count FROM fantasy_league_families WHERE league_family_id = ?",
      ).get("other").count,
      0,
    );
    assert.equal(
      db.prepare("SELECT COUNT(*) AS count FROM fantasy_league_seasons").get().count,
      1,
    );
  } finally {
    db.close();
  }
});

test("registration validator rejects raw SQL, unknown fields, bad metadata, and unsafe time", () => {
  for (const mutation of [
    (command) => { command.sql = "DROP TABLE fantasy_league_seasons"; },
    (command) => { command.extra = true; },
    (command) => { command.family_metadata_json = "[]"; },
    (command) => { command.created_at_ms = Number.MAX_SAFE_INTEGER + 1; },
  ]) {
    const command = clone(fixture);
    mutation(command);
    assert.throws(
      () => buildLeagueSeasonRegistrationStatements(command),
      UnsafeFantasyPersistenceCommand,
    );
  }
});

test("command router selects registration by kind", async () => {
  const sqlite = createDatabase();
  try {
    const result = await executeFantasyWorkerCommand(d1Adapter(sqlite), fixture);

    assert.equal(result.protocol_version, 1);
    assert.equal(result.kind, LEAGUE_SEASON_UPSERT);
    assert.equal(result.league_season_id, "ffl:2026");
    assert.equal(result.results.length, 2);
  } finally {
    sqlite.close();
  }
});

test("authenticated HTTP route accepts the Python fixture through the default command router", async () => {
  const sqlite = createDatabase();
  try {
    const request = new Request("https://fantasy.example/v1/fantasy/persistence", {
      method: "POST",
      headers: {
        authorization: `Bearer ${TOKEN}`,
        "content-type": "application/json",
      },
      body: JSON.stringify(fixture),
    });
    const response = await handleFantasyPersistenceRequest(
      request,
      {
        FANTASY_PERSISTENCE_TOKEN: TOKEN,
        FANTASY_DB: d1Adapter(sqlite),
      },
      {
        subtle: workerSubtle(),
        logger: { error() {} },
      },
    );
    const payload = await response.json();

    assert.equal(response.status, 200);
    assert.equal(payload.ok, true);
    assert.equal(payload.kind, LEAGUE_SEASON_UPSERT);
    assert.equal(payload.league_season_id, "ffl:2026");
    assert.equal(
      sqlite.prepare(
        "SELECT COUNT(*) AS count FROM fantasy_league_seasons WHERE league_season_id = ?",
      ).get("ffl:2026").count,
      1,
    );
  } finally {
    sqlite.close();
  }
});
