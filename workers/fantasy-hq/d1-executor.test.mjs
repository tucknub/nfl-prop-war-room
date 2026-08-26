import assert from "node:assert/strict";
import test from "node:test";

import {
  D1BatchExecutionError,
  D1WriteInvariantError,
  UnsafeD1WritePlan,
  executePersistenceBatch,
  preparePersistenceStatements,
} from "./d1-executor.mjs";


function statement(overrides = {}) {
  return {
    sql: "UPDATE fantasy_sync_runs SET status = ? WHERE sync_run_id = ?",
    parameters: ["COMPLETED", "sync-1"],
    expected_affected_rows: 1,
    ...overrides,
  };
}

function mockDb({ results = null, batchError = null } = {}) {
  const calls = {
    prepared: [],
    batches: [],
  };

  const db = {
    prepare(sql) {
      const record = { sql, parameters: [] };
      calls.prepared.push(record);
      const prepared = {
        record,
        bind(...parameters) {
          record.parameters = parameters;
          return { record };
        },
      };
      return prepared;
    },
    async batch(preparedStatements) {
      calls.batches.push(preparedStatements);
      if (batchError) {
        throw batchError;
      }
      if (results !== null) {
        return results;
      }
      return preparedStatements.map(() => ({
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


test("rejects missing D1 binding and empty plans", () => {
  assert.throws(
    () => preparePersistenceStatements(null, [statement()]),
    UnsafeD1WritePlan,
  );

  const { db } = mockDb();
  assert.throws(
    () => preparePersistenceStatements(db, []),
    UnsafeD1WritePlan,
  );
});


test("rejects malformed statements and unsupported transport parameters", () => {
  const { db } = mockDb();

  assert.throws(
    () => preparePersistenceStatements(db, [{ ...statement(), sql: "  " }]),
    UnsafeD1WritePlan,
  );
  assert.throws(
    () => preparePersistenceStatements(db, [{ ...statement(), parameters: "bad" }]),
    UnsafeD1WritePlan,
  );
  assert.throws(
    () => preparePersistenceStatements(db, [{ ...statement(), parameters: [undefined] }]),
    /unsupported type undefined/,
  );
  assert.throws(
    () => preparePersistenceStatements(db, [{ ...statement(), parameters: [1n] }]),
    /unsupported type bigint/,
  );
  assert.throws(
    () => preparePersistenceStatements(db, [{ ...statement(), parameters: [Number.NaN] }]),
    /must be finite/,
  );
  assert.throws(
    () => preparePersistenceStatements(db, [{ ...statement(), parameters: [Number.MAX_SAFE_INTEGER + 1] }]),
    /safe integer range/,
  );
  assert.throws(
    () => preparePersistenceStatements(db, [{ ...statement(), expected_affected_rows: -1 }]),
    /expected_affected_rows/,
  );
});


test("prepares statements in order and binds parameters without mutation", () => {
  const { db, calls } = mockDb();
  const input = [
    statement({ sql: "  INSERT INTO one VALUES (?, ?)  ", parameters: ["a", 2] }),
    statement({ sql: "DELETE FROM two", parameters: [], expected_affected_rows: 0 }),
  ];

  const prepared = preparePersistenceStatements(db, input);

  assert.deepEqual(calls.prepared, [
    { sql: "INSERT INTO one VALUES (?, ?)", parameters: ["a", 2] },
    { sql: "DELETE FROM two", parameters: [] },
  ]);
  assert.equal(prepared.preparedStatements.length, 2);
  assert.equal(prepared.statements[0].expected_affected_rows, 1);
  assert.equal(prepared.statements[1].expected_affected_rows, 0);
  assert.equal(input[0].sql, "  INSERT INTO one VALUES (?, ?)  ");
});


test("executes exactly one D1 batch and returns compact write summaries", async () => {
  const { db, calls } = mockDb({
    results: [
      {
        success: true,
        meta: { changes: 1, rows_read: 2, rows_written: 1, changed_db: true },
      },
      {
        success: true,
        meta: { changes: 0, rows_read: 1, rows_written: 0, changed_db: false },
      },
    ],
  });

  const summaries = await executePersistenceBatch(db, [
    statement(),
    statement({
      sql: "DELETE FROM noop WHERE id = ?",
      parameters: ["missing"],
      expected_affected_rows: 0,
    }),
  ]);

  assert.equal(calls.batches.length, 1);
  assert.equal(calls.batches[0].length, 2);
  assert.deepEqual(summaries, [
    {
      index: 0,
      expected_affected_rows: 1,
      changes: 1,
      rows_read: 2,
      rows_written: 1,
      changed_db: true,
    },
    {
      index: 1,
      expected_affected_rows: 0,
      changes: 0,
      rows_read: 1,
      rows_written: 0,
      changed_db: false,
    },
  ]);
});


test("wraps D1 batch failures and preserves their cause", async () => {
  const providerError = new Error("NOT NULL constraint failed");
  const { db } = mockDb({ batchError: providerError });

  await assert.rejects(
    executePersistenceBatch(db, [statement()]),
    (error) => {
      assert.ok(error instanceof D1BatchExecutionError);
      assert.equal(error.cause, providerError);
      return true;
    },
  );
});


test("rejects result-count mismatches", async () => {
  const { db } = mockDb({ results: [] });
  await assert.rejects(
    executePersistenceBatch(db, [statement()]),
    D1WriteInvariantError,
  );
});


test("rejects statements that do not report success", async () => {
  const { db } = mockDb({ results: [{ success: false, meta: { changes: 1 } }] });
  await assert.rejects(
    executePersistenceBatch(db, [statement()]),
    /success=true/,
  );
});


test("requires valid meta.changes when an affected-row expectation exists", async () => {
  const { db: missing } = mockDb({ results: [{ success: true, meta: {} }] });
  await assert.rejects(
    executePersistenceBatch(missing, [statement()]),
    /valid meta.changes/,
  );

  const { db: nonInteger } = mockDb({
    results: [{ success: true, meta: { changes: 1.5 } }],
  });
  await assert.rejects(
    executePersistenceBatch(nonInteger, [statement()]),
    /valid meta.changes/,
  );
});


test("rejects affected-row mismatches after a successful batch", async () => {
  const { db } = mockDb({ results: [{ success: true, meta: { changes: 0 } }] });
  await assert.rejects(
    executePersistenceBatch(db, [statement()]),
    /changed 0 rows; expected 1/,
  );
});


test("allows diagnostic statements with no affected-row expectation", async () => {
  const { db } = mockDb({ results: [{ success: true, meta: {} }] });
  const [summary] = await executePersistenceBatch(db, [
    statement({
      sql: "SELECT 1",
      parameters: [],
      expected_affected_rows: null,
    }),
  ]);

  assert.deepEqual(summary, {
    index: 0,
    expected_affected_rows: null,
    changes: null,
    rows_read: null,
    rows_written: null,
    changed_db: false,
  });
});
