import assert from "node:assert/strict";
import test from "node:test";

import worker from "./index.mjs";
import {
  FANTASY_SHADOW_EVENT,
  FANTASY_SHADOW_MODE,
  FANTASY_SHADOW_SCHEMA_SQL,
  FantasyShadowReadinessError,
  runFantasyShadowScheduled,
} from "./shadow-scheduled.mjs";

function controller(overrides = {}) {
  return {
    scheduledTime: 1_777_777_777_000,
    cron: "17 * * * *",
    ...overrides,
  };
}

function fakeShadowD1({ rowCount = 0, firstError = null } = {}) {
  const calls = {
    prepared: [],
    first: 0,
    batch: 0,
  };
  return {
    calls,
    db: {
      prepare(sql) {
        calls.prepared.push(sql);
        return {
          async first() {
            calls.first += 1;
            if (firstError) {
              throw firstError;
            }
            return { row_count: rowCount };
          },
        };
      },
      async batch() {
        calls.batch += 1;
        throw new Error("shadow readiness must never write with D1 batch");
      },
    },
  };
}

function logger() {
  const entries = [];
  return {
    entries,
    info(message, fields) {
      entries.push({ message, fields });
    },
  };
}

test("shadow scheduled readiness probes migrated schema without writes", async () => {
  const { db, calls } = fakeShadowD1({ rowCount: 2 });
  const log = logger();

  const result = await runFantasyShadowScheduled(
    controller(),
    {
      FANTASY_SCHEDULE_MODE: FANTASY_SHADOW_MODE,
      FANTASY_DB: db,
    },
    { logger: log },
  );

  assert.deepEqual(result, {
    event: FANTASY_SHADOW_EVENT,
    status: "ready",
    mode: "SHADOW",
    scheduled_at_ms: 1_777_777_777_000,
    cron: "17 * * * *",
    protocol_version: 1,
    d1_schema_ready: true,
    write_enabled: false,
  });
  assert.deepEqual(calls.prepared, [FANTASY_SHADOW_SCHEMA_SQL]);
  assert.equal(calls.first, 1);
  assert.equal(calls.batch, 0);
  assert.equal(log.entries.length, 1);
  assert.equal(log.entries[0].fields.write_enabled, false);
});

test("shadow readiness succeeds with an empty migrated league table", async () => {
  const { db } = fakeShadowD1({ rowCount: 0 });

  const result = await runFantasyShadowScheduled(
    controller(),
    {
      FANTASY_SCHEDULE_MODE: FANTASY_SHADOW_MODE,
      FANTASY_DB: db,
    },
    { logger: { info() {} } },
  );

  assert.equal(result.d1_schema_ready, true);
});

test("scheduled handler fails closed unless SHADOW mode is explicit", async () => {
  const { db, calls } = fakeShadowD1();

  for (const mode of [undefined, "", "LIVE", "shadow"]) {
    await assert.rejects(
      () =>
        runFantasyShadowScheduled(
          controller(),
          {
            FANTASY_SCHEDULE_MODE: mode,
            FANTASY_DB: db,
          },
          { logger: { info() {} } },
        ),
      FantasyShadowReadinessError,
    );
  }

  assert.equal(calls.prepared.length, 0);
  assert.equal(calls.batch, 0);
});

test("missing D1 binding and missing schema fail as readiness errors", async () => {
  await assert.rejects(
    () =>
      runFantasyShadowScheduled(
        controller(),
        { FANTASY_SCHEDULE_MODE: FANTASY_SHADOW_MODE },
        { logger: { info() {} } },
      ),
    /D1 binding is unavailable/,
  );

  const { db } = fakeShadowD1({
    firstError: new Error("no such table: fantasy_league_seasons"),
  });
  await assert.rejects(
    () =>
      runFantasyShadowScheduled(
        controller(),
        {
          FANTASY_SCHEDULE_MODE: FANTASY_SHADOW_MODE,
          FANTASY_DB: db,
        },
        { logger: { info() {} } },
      ),
    /schema probe failed/,
  );
});

test("invalid schema probe shape fails closed", async () => {
  const values = [
    null,
    {},
    { row_count: -1 },
    { row_count: 1.5 },
    { row_count: "0" },
  ];

  for (const value of values) {
    const db = {
      prepare() {
        return {
          async first() {
            return value;
          },
        };
      },
    };
    await assert.rejects(
      () =>
        runFantasyShadowScheduled(
          controller(),
          {
            FANTASY_SCHEDULE_MODE: FANTASY_SHADOW_MODE,
            FANTASY_DB: db,
          },
          { logger: { info() {} } },
        ),
      /invalid result/,
    );
  }
});

test("scheduled event identity must be canonical and safe", async () => {
  const { db } = fakeShadowD1();
  const env = {
    FANTASY_SCHEDULE_MODE: FANTASY_SHADOW_MODE,
    FANTASY_DB: db,
  };

  for (const scheduledTime of [-1, 1.5, Number.MAX_SAFE_INTEGER + 1, undefined]) {
    await assert.rejects(
      () =>
        runFantasyShadowScheduled(
          controller({ scheduledTime }),
          env,
          { logger: { info() {} } },
        ),
      /scheduledTime/,
    );
  }

  for (const cron of ["", " 17 * * * *", "17 * * * * ", "bad\ncron", undefined]) {
    await assert.rejects(
      () =>
        runFantasyShadowScheduled(
          controller({ cron }),
          env,
          { logger: { info() {} } },
        ),
      /cron/,
    );
  }
});

test("shadow logs contain no Worker secret or fantasy payload", async () => {
  const { db } = fakeShadowD1();
  const log = logger();
  const secret = "super-private-token-that-must-never-be-logged";

  await runFantasyShadowScheduled(
    controller(),
    {
      FANTASY_SCHEDULE_MODE: FANTASY_SHADOW_MODE,
      FANTASY_PERSISTENCE_TOKEN: secret,
      FANTASY_DB: db,
    },
    { logger: log },
  );

  const serialized = JSON.stringify(log.entries);
  assert.equal(serialized.includes(secret), false);
  assert.equal(serialized.includes("league_season_id"), false);
  assert.equal(serialized.includes("platform_player_id"), false);
});

test("Worker module exposes the Cloudflare scheduled handler", async () => {
  assert.equal(typeof worker.scheduled, "function");

  const { db } = fakeShadowD1();
  const originalInfo = console.info;
  console.info = () => {};
  try {
    await worker.scheduled(
      controller(),
      {
        FANTASY_SCHEDULE_MODE: FANTASY_SHADOW_MODE,
        FANTASY_DB: db,
      },
    );
  } finally {
    console.info = originalInfo;
  }
});
