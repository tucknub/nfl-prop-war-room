export class UnsafeD1WritePlan extends Error {
  constructor(message) {
    super(message);
    this.name = "UnsafeD1WritePlan";
  }
}

export class D1BatchExecutionError extends Error {
  constructor(message, options = {}) {
    super(message, options);
    this.name = "D1BatchExecutionError";
  }
}

export class D1WriteInvariantError extends Error {
  constructor(message) {
    super(message);
    this.name = "D1WriteInvariantError";
  }
}

/**
 * Prepare a storage-neutral persistence plan for Cloudflare D1.
 *
 * Expected input shape matches src/fantasy/persistence.py after JSON transport:
 *   { sql: string, parameters: primitive[], expected_affected_rows: number | null }
 *
 * This is an internal execution primitive. Never expose it as an arbitrary SQL
 * HTTP endpoint.
 */
export function preparePersistenceStatements(db, statements) {
  _validateDatabase(db);
  const normalized = _validateStatements(statements);

  const preparedStatements = normalized.map((statement, index) => {
    try {
      const prepared = db.prepare(statement.sql);
      if (!prepared || typeof prepared.bind !== "function") {
        throw new TypeError("db.prepare() did not return a bindable statement");
      }
      return statement.parameters.length
        ? prepared.bind(...statement.parameters)
        : prepared;
    } catch (cause) {
      throw new D1BatchExecutionError(
        `failed to prepare persistence statement ${index}`,
        { cause },
      );
    }
  });

  return { statements: normalized, preparedStatements };
}

/**
 * Execute one ordered D1 transaction batch and validate its returned metadata.
 *
 * IMPORTANT: expected_affected_rows is a post-batch invariant/audit check. A
 * row-count mismatch is not itself a SQL error and therefore cannot be relied on
 * to roll back a transaction after D1 has successfully committed it. Critical
 * write preconditions must be encoded in SQL constraints/foreign keys/guards so
 * invalid state makes db.batch() reject and D1 roll back the batch.
 */
export async function executePersistenceBatch(db, statements) {
  const prepared = preparePersistenceStatements(db, statements);

  let results;
  try {
    results = await db.batch(prepared.preparedStatements);
  } catch (cause) {
    throw new D1BatchExecutionError("D1 persistence batch failed", { cause });
  }

  if (!Array.isArray(results)) {
    throw new D1WriteInvariantError("D1 batch result must be an array");
  }
  if (results.length !== prepared.statements.length) {
    throw new D1WriteInvariantError(
      `D1 batch returned ${results.length} results for ${prepared.statements.length} statements`,
    );
  }

  return results.map((result, index) => {
    if (!result || result.success !== true) {
      throw new D1WriteInvariantError(
        `D1 statement ${index} did not report success=true`,
      );
    }

    const expected = prepared.statements[index].expected_affected_rows;
    const changes = result.meta?.changes;

    if (expected !== null) {
      if (!Number.isSafeInteger(changes) || changes < 0) {
        throw new D1WriteInvariantError(
          `D1 statement ${index} did not report a valid meta.changes value`,
        );
      }
      if (changes !== expected) {
        throw new D1WriteInvariantError(
          `D1 statement ${index} changed ${changes} rows; expected ${expected}`,
        );
      }
    }

    return {
      index,
      expected_affected_rows: expected,
      changes: Number.isSafeInteger(changes) ? changes : null,
      rows_read: _optionalSafeCount(result.meta?.rows_read),
      rows_written: _optionalSafeCount(result.meta?.rows_written),
      changed_db: result.meta?.changed_db === true,
    };
  });
}

function _validateDatabase(db) {
  if (!db || typeof db.prepare !== "function" || typeof db.batch !== "function") {
    throw new UnsafeD1WritePlan(
      "D1 database binding must expose prepare() and batch()",
    );
  }
}

function _validateStatements(statements) {
  if (!Array.isArray(statements) || statements.length === 0) {
    throw new UnsafeD1WritePlan(
      "persistence plan must contain at least one statement",
    );
  }

  return statements.map((statement, statementIndex) => {
    if (!statement || typeof statement !== "object" || Array.isArray(statement)) {
      throw new UnsafeD1WritePlan(
        `persistence statement ${statementIndex} must be an object`,
      );
    }

    const sql = typeof statement.sql === "string" ? statement.sql.trim() : "";
    if (!sql) {
      throw new UnsafeD1WritePlan(
        `persistence statement ${statementIndex} requires non-empty SQL`,
      );
    }

    if (!Array.isArray(statement.parameters)) {
      throw new UnsafeD1WritePlan(
        `persistence statement ${statementIndex} parameters must be an array`,
      );
    }
    const parameters = statement.parameters.map((value, parameterIndex) =>
      _validateParameter(value, statementIndex, parameterIndex),
    );

    const expected = statement.expected_affected_rows;
    if (
      expected !== null &&
      (!Number.isSafeInteger(expected) || expected < 0)
    ) {
      throw new UnsafeD1WritePlan(
        `persistence statement ${statementIndex} expected_affected_rows must be a non-negative safe integer or null`,
      );
    }

    return {
      sql,
      parameters,
      expected_affected_rows: expected,
    };
  });
}

function _validateParameter(value, statementIndex, parameterIndex) {
  if (value === null || typeof value === "string" || typeof value === "boolean") {
    return value;
  }

  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new UnsafeD1WritePlan(
        `persistence statement ${statementIndex} parameter ${parameterIndex} must be finite`,
      );
    }
    if (Number.isInteger(value) && !Number.isSafeInteger(value)) {
      throw new UnsafeD1WritePlan(
        `persistence statement ${statementIndex} parameter ${parameterIndex} exceeds JavaScript safe integer range`,
      );
    }
    return value;
  }

  throw new UnsafeD1WritePlan(
    `persistence statement ${statementIndex} parameter ${parameterIndex} has unsupported type ${typeof value}`,
  );
}

function _optionalSafeCount(value) {
  return Number.isSafeInteger(value) && value >= 0 ? value : null;
}
