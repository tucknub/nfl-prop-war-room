export const READ_PROTOCOL_VERSION = 1;
export const READ_LEAGUE_SEASON = "READ_LEAGUE_SEASON";
export const READ_SYNC_RUN = "READ_SYNC_RUN";
export const READ_LATEST_SNAPSHOT = "READ_LATEST_SNAPSHOT";

const LEAGUE_SEASON_SQL = `SELECT
  league_season_id,
  league_family_id,
  platform,
  platform_league_id,
  season,
  display_name,
  created_at_ms,
  metadata_json
FROM fantasy_league_seasons
WHERE league_season_id = ?
LIMIT 1`;

const SYNC_RUN_SQL = `SELECT
  sync_run_id,
  league_season_id,
  platform,
  platform_league_id,
  season,
  started_at_ms,
  completed_at_ms,
  status,
  accepted_snapshot_id,
  error_code
FROM fantasy_sync_runs
WHERE sync_run_id = ?
LIMIT 1`;

const LATEST_SNAPSHOT_SQL = `SELECT
  s.snapshot_id,
  s.league_season_id,
  s.content_fingerprint,
  s.observed_at_ms,
  s.accepted_at_ms,
  s.provider_status,
  s.rules_ready,
  s.draft_ready,
  s.ownership_ready,
  s.normalized_state_json,
  s.source_metadata_json
FROM fantasy_state_snapshots AS s
WHERE s.league_season_id = ?
  AND EXISTS (
    SELECT 1
    FROM fantasy_sync_runs AS r
    WHERE r.league_season_id = s.league_season_id
      AND r.accepted_snapshot_id = s.snapshot_id
      AND r.status = 'COMPLETED'
  )
ORDER BY s.accepted_at_ms DESC, s.snapshot_id DESC
LIMIT 1`;

export class UnsafeFantasyReadRequest extends Error {
  constructor(message) {
    super(message);
    this.name = "UnsafeFantasyReadRequest";
  }
}

export class FantasyReadExecutionError extends Error {
  constructor(message, options = {}) {
    super(message, options);
    this.name = "FantasyReadExecutionError";
  }
}

export function parseFantasyReadPath(pathname) {
  if (typeof pathname !== "string") {
    return null;
  }
  const segments = pathname.split("/");
  if (
    segments.length === 6 &&
    segments[0] === "" &&
    segments[1] === "v1" &&
    segments[2] === "fantasy" &&
    segments[3] === "read"
  ) {
    if (segments[4] === "league-seasons") {
      return {
        kind: READ_LEAGUE_SEASON,
        identifier: _decodeCanonicalIdentifier(segments[5]),
      };
    }
    if (segments[4] === "sync-runs") {
      return {
        kind: READ_SYNC_RUN,
        identifier: _decodeCanonicalIdentifier(segments[5]),
      };
    }
  }

  if (
    segments.length === 7 &&
    segments[0] === "" &&
    segments[1] === "v1" &&
    segments[2] === "fantasy" &&
    segments[3] === "read" &&
    segments[4] === "league-seasons" &&
    segments[6] === "latest-snapshot"
  ) {
    return {
      kind: READ_LATEST_SNAPSHOT,
      identifier: _decodeCanonicalIdentifier(segments[5]),
    };
  }
  return null;
}

export async function executeFantasyRead(db, request) {
  _validateDatabase(db);
  const normalized = _validateReadRequest(request);

  let session;
  try {
    session = db.withSession("first-primary");
  } catch (cause) {
    throw new FantasyReadExecutionError("failed to create D1 read session", { cause });
  }
  if (!session || typeof session.prepare !== "function") {
    throw new FantasyReadExecutionError("D1 read session is unavailable");
  }

  let row;
  try {
    const sql = _sqlForKind(normalized.kind);
    const statement = session.prepare(sql);
    if (!statement || typeof statement.bind !== "function") {
      throw new TypeError("D1 read statement is not bindable");
    }
    const bound = statement.bind(normalized.identifier);
    if (!bound || typeof bound.first !== "function") {
      throw new TypeError("D1 read statement does not support first()");
    }
    row = await bound.first();
  } catch (cause) {
    throw new FantasyReadExecutionError("D1 read query failed", { cause });
  }

  return _readResponse(normalized, row);
}

function _readResponse(request, row) {
  if (row === null || row === undefined) {
    return {
      protocol_version: READ_PROTOCOL_VERSION,
      kind: request.kind,
      requested_id: request.identifier,
      found: false,
      record: null,
    };
  }
  if (typeof row !== "object" || Array.isArray(row)) {
    throw new FantasyReadExecutionError("D1 read query returned an invalid row");
  }

  const record = { ...row };
  if (request.kind === READ_LEAGUE_SEASON) {
    _parseJsonColumn(record, "metadata_json", "metadata");
  } else if (request.kind === READ_LATEST_SNAPSHOT) {
    _parseJsonColumn(record, "normalized_state_json", "normalized_state");
    _parseJsonColumn(record, "source_metadata_json", "source_metadata");
    record.rules_ready = _sqliteBoolean(record.rules_ready, "rules_ready");
    record.draft_ready = _sqliteBoolean(record.draft_ready, "draft_ready");
    record.ownership_ready = _sqliteBoolean(record.ownership_ready, "ownership_ready");
  }

  return {
    protocol_version: READ_PROTOCOL_VERSION,
    kind: request.kind,
    requested_id: request.identifier,
    found: true,
    record,
  };
}

function _parseJsonColumn(record, sourceKey, targetKey) {
  const value = record[sourceKey];
  if (typeof value !== "string") {
    throw new FantasyReadExecutionError(`D1 ${sourceKey} must be JSON text`);
  }
  let parsed;
  try {
    parsed = JSON.parse(value);
  } catch (cause) {
    throw new FantasyReadExecutionError(`D1 ${sourceKey} is invalid JSON`, { cause });
  }
  delete record[sourceKey];
  record[targetKey] = parsed;
}

function _sqliteBoolean(value, label) {
  if (value === 0) {
    return false;
  }
  if (value === 1) {
    return true;
  }
  throw new FantasyReadExecutionError(`D1 ${label} must be 0 or 1`);
}

function _validateDatabase(db) {
  if (!db || typeof db.withSession !== "function") {
    throw new FantasyReadExecutionError("D1 database binding must support withSession()");
  }
}

function _validateReadRequest(request) {
  if (!request || typeof request !== "object" || Array.isArray(request)) {
    throw new UnsafeFantasyReadRequest("read request must be an object");
  }
  if (![READ_LEAGUE_SEASON, READ_SYNC_RUN, READ_LATEST_SNAPSHOT].includes(request.kind)) {
    throw new UnsafeFantasyReadRequest("read request kind is not supported");
  }
  return {
    kind: request.kind,
    identifier: _validatedIdentifier(request.identifier),
  };
}

function _sqlForKind(kind) {
  if (kind === READ_LEAGUE_SEASON) {
    return LEAGUE_SEASON_SQL;
  }
  if (kind === READ_SYNC_RUN) {
    return SYNC_RUN_SQL;
  }
  return LATEST_SNAPSHOT_SQL;
}

function _decodeCanonicalIdentifier(segment) {
  if (typeof segment !== "string" || !segment) {
    throw new UnsafeFantasyReadRequest("read identifier is required");
  }
  let decoded;
  try {
    decoded = decodeURIComponent(segment);
  } catch {
    throw new UnsafeFantasyReadRequest("read identifier encoding is invalid");
  }
  const identifier = _validatedIdentifier(decoded);
  if (encodeURIComponent(identifier) !== segment) {
    throw new UnsafeFantasyReadRequest("read identifier path encoding is not canonical");
  }
  return identifier;
}

function _validatedIdentifier(value) {
  if (typeof value !== "string" || !value || value !== value.trim()) {
    throw new UnsafeFantasyReadRequest("read identifier must be nonblank without surrounding whitespace");
  }
  if (value.length > 256) {
    throw new UnsafeFantasyReadRequest("read identifier exceeds 256 characters");
  }
  if (/[/\\\u0000-\u001f\u007f]/u.test(value)) {
    throw new UnsafeFantasyReadRequest("read identifier contains prohibited characters");
  }
  return value;
}
