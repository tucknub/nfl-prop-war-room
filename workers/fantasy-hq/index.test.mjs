import assert from "node:assert/strict";
import { timingSafeEqual, webcrypto } from "node:crypto";
import test from "node:test";

import { D1BatchExecutionError } from "./d1-executor.mjs";
import {
  HEALTH_PATH,
  MAX_COMMAND_BODY_BYTES,
  PERSISTENCE_PATH,
  handleFantasyPersistenceRequest,
  readLimitedUtf8Body,
  verifyBearerToken,
} from "./index.mjs";

const TOKEN = "fantasy-hq-test-token-0123456789abcdef";
const BASE = "https://fantasy-hq.example.test";

const timingSubtle = {
  digest: webcrypto.subtle.digest.bind(webcrypto.subtle),
  timingSafeEqual(left, right) {
    return timingSafeEqual(Buffer.from(left), Buffer.from(right));
  },
};

function fakeD1({ batchError = null } = {}) {
  const calls = { prepared: [], batches: [] };
  const db = {
    prepare(sql) {
      const record = { sql, parameters: [] };
      calls.prepared.push(record);
      return {
        record,
        bind(...parameters) {
          record.parameters = parameters;
          return { record };
        },
      };
    },
    async batch(statements) {
      calls.batches.push(statements);
      if (batchError) {
        throw batchError;
      }
      return statements.map(() => ({
        success: true,
        meta: {
          changes: 1,
          rows_read: 0,
          rows_written: 1,
          changed_db: true,
        },
      }));
    },
  };
  return { db, calls };
}

function env(overrides = {}) {
  return {
    FANTASY_PERSISTENCE_TOKEN: TOKEN,
    FANTASY_DB: fakeD1().db,
    ...overrides,
  };
}

function startCommand(overrides = {}) {
  return {
    protocol_version: 1,
    kind: "SYNC_START",
    identity: {
      league_season_id: "ffl:2026",
      platform: "SLEEPER",
      platform_league_id: "league-2026",
      season: "2026",
    },
    sync_run_id: "sync-1",
    started_at_ms: 100,
    request_metadata_json: "{}",
    ...overrides,
  };
}

function postRequest(body, { token = TOKEN, headers = {} } = {}) {
  const finalHeaders = new Headers({
    "content-type": "application/json; charset=utf-8",
    ...headers,
  });
  if (token !== null) {
    finalHeaders.set("authorization", `Bearer ${token}`);
  }
  return new Request(`${BASE}${PERSISTENCE_PATH}`, {
    method: "POST",
    headers: finalHeaders,
    body,
  });
}

async function payload(response) {
  return JSON.parse(await response.text());
}


test("health endpoint is public, minimal, and no-store", async () => {
  const response = await handleFantasyPersistenceRequest(
    new Request(`${BASE}${HEALTH_PATH}`),
    {},
  );
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  assert.deepEqual(await payload(response), {
    ok: true,
    status: "ok",
    protocol_version: 1,
  });
});


test("unknown paths and unsupported methods fail closed", async () => {
  const missing = await handleFantasyPersistenceRequest(
    new Request(`${BASE}/nope`),
    {},
  );
  assert.equal(missing.status, 404);

  const wrongMethod = await handleFantasyPersistenceRequest(
    new Request(`${BASE}${PERSISTENCE_PATH}`, { method: "GET" }),
    {},
  );
  assert.equal(wrongMethod.status, 405);
  assert.equal(wrongMethod.headers.get("allow"), "POST");
});


test("missing or weak Worker secret makes persistence unavailable", async () => {
  for (const configured of [undefined, "short-secret"]) {
    const response = await handleFantasyPersistenceRequest(
      postRequest(JSON.stringify(startCommand())),
      env({ FANTASY_PERSISTENCE_TOKEN: configured }),
      { subtle: timingSubtle },
    );
    assert.equal(response.status, 503);
    assert.equal((await payload(response)).error.code, "SERVICE_UNAVAILABLE");
  }
});


test("missing or incorrect bearer token returns 401 without executing command", async () => {
  let executions = 0;
  const options = {
    subtle: timingSubtle,
    executeCommand: async () => {
      executions += 1;
      return {};
    },
  };

  for (const token of [null, "wrong-token-that-is-definitely-not-right"]) {
    const response = await handleFantasyPersistenceRequest(
      postRequest(JSON.stringify(startCommand()), { token }),
      env(),
      options,
    );
    assert.equal(response.status, 401);
    assert.equal(response.headers.get("www-authenticate"), 'Bearer realm="fantasy-hq"');
  }
  assert.equal(executions, 0);
});


test("bearer verification hashes both sides before timing-safe comparison", async () => {
  assert.equal(await verifyBearerToken(TOKEN, TOKEN, timingSubtle), true);
  assert.equal(await verifyBearerToken(`${TOKEN}x`, TOKEN, timingSubtle), false);
  await assert.rejects(
    () => verifyBearerToken(TOKEN, TOKEN, webcrypto.subtle),
    /timingSafeEqual/,
  );
});


test("authorized request still fails closed without a D1 binding", async () => {
  const response = await handleFantasyPersistenceRequest(
    postRequest(JSON.stringify(startCommand())),
    env({ FANTASY_DB: null }),
    { subtle: timingSubtle },
  );
  assert.equal(response.status, 503);
  assert.equal((await payload(response)).error.code, "SERVICE_UNAVAILABLE");
});


test("content type and content encoding are restricted", async () => {
  const wrongType = await handleFantasyPersistenceRequest(
    postRequest(JSON.stringify(startCommand()), {
      headers: { "content-type": "text/plain" },
    }),
    env(),
    { subtle: timingSubtle },
  );
  assert.equal(wrongType.status, 415);
  assert.equal((await payload(wrongType)).error.code, "UNSUPPORTED_MEDIA_TYPE");

  const compressed = await handleFantasyPersistenceRequest(
    postRequest(JSON.stringify(startCommand()), {
      headers: { "content-encoding": "gzip" },
    }),
    env(),
    { subtle: timingSubtle },
  );
  assert.equal(compressed.status, 415);
  assert.equal((await payload(compressed)).error.code, "UNSUPPORTED_CONTENT_ENCODING");
});


test("declared and streamed oversized bodies are rejected", async () => {
  const declared = await handleFantasyPersistenceRequest(
    postRequest("{}", {
      headers: { "content-length": String(MAX_COMMAND_BODY_BYTES + 1) },
    }),
    env(),
    { subtle: timingSubtle },
  );
  assert.equal(declared.status, 413);
  assert.equal((await payload(declared)).error.code, "BODY_TOO_LARGE");

  const actual = await handleFantasyPersistenceRequest(
    postRequest(new Uint8Array(MAX_COMMAND_BODY_BYTES + 1)),
    env(),
    { subtle: timingSubtle },
  );
  assert.equal(actual.status, 413);
  assert.equal((await payload(actual)).error.code, "BODY_TOO_LARGE");
});


test("body reader rejects invalid length, empty body, invalid UTF-8, and invalid JSON", async () => {
  const badLengthRequest = postRequest("{}", {
    headers: { "content-length": "1.5" },
  });
  await assert.rejects(
    () => readLimitedUtf8Body(badLengthRequest),
    /Content-Length must be a non-negative integer/,
  );

  const empty = await handleFantasyPersistenceRequest(
    new Request(`${BASE}${PERSISTENCE_PATH}`, {
      method: "POST",
      headers: {
        authorization: `Bearer ${TOKEN}`,
        "content-type": "application/json",
      },
    }),
    env(),
    { subtle: timingSubtle },
  );
  assert.equal(empty.status, 400);
  assert.equal((await payload(empty)).error.code, "EMPTY_BODY");

  const invalidUtf8 = await handleFantasyPersistenceRequest(
    postRequest(new Uint8Array([0xff])),
    env(),
    { subtle: timingSubtle },
  );
  assert.equal(invalidUtf8.status, 400);
  assert.equal((await payload(invalidUtf8)).error.code, "INVALID_UTF8");

  const invalidJson = await handleFantasyPersistenceRequest(
    postRequest("{not-json}"),
    env(),
    { subtle: timingSubtle },
  );
  assert.equal(invalidJson.status, 400);
  assert.equal((await payload(invalidJson)).error.code, "INVALID_JSON");
});


test("structured command validation errors return 400 and raw SQL is never accepted", async () => {
  const malicious = startCommand({ sql: "DROP TABLE fantasy_sync_runs" });
  const response = await handleFantasyPersistenceRequest(
    postRequest(JSON.stringify(malicious)),
    env(),
    { subtle: timingSubtle },
  );
  assert.equal(response.status, 400);
  const result = await payload(response);
  assert.equal(result.error.code, "INVALID_COMMAND");
  assert.match(result.error.message, /unsupported field/);
});


test("D1 execution errors are generic and never echo command content", async () => {
  const loggerCalls = [];
  const logger = {
    error(message, metadata) {
      loggerCalls.push({ message, metadata });
    },
  };
  const response = await handleFantasyPersistenceRequest(
    postRequest(JSON.stringify(startCommand())),
    env(),
    {
      subtle: timingSubtle,
      logger,
      executeCommand: async () => {
        throw new D1BatchExecutionError("database exploded with internal detail");
      },
    },
  );
  assert.equal(response.status, 500);
  const result = await payload(response);
  assert.deepEqual(result, {
    ok: false,
    error: { code: "PERSISTENCE_FAILED", message: "Persistence command failed" },
  });
  assert.equal(loggerCalls.length, 1);
  assert.deepEqual(loggerCalls[0].metadata, { error_name: "D1BatchExecutionError" });
});


test("valid authenticated SYNC_START flows through real protocol and D1 executor", async () => {
  const { db, calls } = fakeD1();
  const response = await handleFantasyPersistenceRequest(
    postRequest(JSON.stringify(startCommand())),
    env({ FANTASY_DB: db }),
    { subtle: timingSubtle },
  );

  assert.equal(response.status, 200);
  const result = await payload(response);
  assert.equal(result.ok, true);
  assert.equal(result.protocol_version, 1);
  assert.equal(result.kind, "SYNC_START");
  assert.equal(result.sync_run_id, "sync-1");
  assert.equal(result.results.length, 1);
  assert.equal(calls.batches.length, 1);
  assert.equal(calls.prepared.length, 1);
  assert.match(calls.prepared[0].sql, /^INSERT INTO fantasy_sync_runs/);
  assert.equal(calls.prepared[0].parameters[0], "sync-1");
});
