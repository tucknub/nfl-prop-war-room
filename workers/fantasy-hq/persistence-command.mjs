import { executePersistenceBatch } from "./d1-executor.mjs";

export const FANTASY_PERSISTENCE_PROTOCOL_VERSION = 1;
export const SYNC_START = "SYNC_START";
export const SYNC_FAILED = "SYNC_FAILED";
export const SYNC_NO_CHANGE = "SYNC_NO_CHANGE";
export const SYNC_SUCCESS = "SYNC_SUCCESS";

const FINGERPRINT = /^[0-9a-f]{64}$/;

export class UnsafeFantasyPersistenceCommand extends Error {
  constructor(message) {
    super(message);
    this.name = "UnsafeFantasyPersistenceCommand";
  }
}

/**
 * Convert one narrow, versioned Fantasy HQ persistence command into fixed SQL.
 * Caller-supplied SQL is never accepted or executed.
 */
export async function buildPersistenceStatementsFromCommand(command) {
  _requireObject(command, "command");

  const kind = _requiredText(command.kind, "command.kind");
  if (command.protocol_version !== FANTASY_PERSISTENCE_PROTOCOL_VERSION) {
    throw new UnsafeFantasyPersistenceCommand(
      `unsupported persistence protocol version ${String(command.protocol_version)}`,
    );
  }

  if (kind === SYNC_START) {
    return _buildSyncStart(command);
  }
  if (kind === SYNC_FAILED) {
    return _buildSyncFailed(command);
  }
  if (kind === SYNC_NO_CHANGE) {
    return _buildSyncNoChange(command);
  }
  if (kind === SYNC_SUCCESS) {
    return _buildSyncSuccess(command);
  }

  throw new UnsafeFantasyPersistenceCommand(
    `unsupported persistence command kind ${kind}`,
  );
}

export async function executeFantasyPersistenceCommand(db, command) {
  const statements = await buildPersistenceStatementsFromCommand(command);
  const results = await executePersistenceBatch(db, statements);
  return {
    protocol_version: FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    kind: command.kind,
    sync_run_id: command.sync_run_id,
    results,
  };
}

function _buildSyncStart(command) {
  _assertAllowedKeys(command, [
    "protocol_version",
    "kind",
    "identity",
    "sync_run_id",
    "started_at_ms",
    "request_metadata_json",
  ], "command");

  const identity = _identity(command.identity);
  const syncRunId = _requiredText(command.sync_run_id, "command.sync_run_id");
  const startedAt = _nonnegativeSafeInteger(command.started_at_ms, "command.started_at_ms");
  const requestMetadata = _jsonObjectText(
    command.request_metadata_json,
    "command.request_metadata_json",
  );

  return [{
    sql: (
      "INSERT INTO fantasy_sync_runs (" +
      "sync_run_id, league_season_id, platform, platform_league_id, season, " +
      "started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, " +
      "error_summary, request_metadata_json" +
      ") VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, ?)"
    ),
    parameters: [
      syncRunId,
      identity.league_season_id,
      identity.platform,
      identity.platform_league_id,
      identity.season,
      startedAt,
      "STARTED",
      requestMetadata,
    ],
    expected_affected_rows: 1,
  }];
}

function _buildSyncFailed(command) {
  _assertAllowedKeys(command, [
    "protocol_version",
    "kind",
    "identity",
    "sync_run_id",
    "completed_at_ms",
    "error_code",
    "error_summary",
  ], "command");

  const identity = _identity(command.identity);
  const syncRunId = _requiredText(command.sync_run_id, "command.sync_run_id");
  const completedAt = _nonnegativeSafeInteger(command.completed_at_ms, "command.completed_at_ms");
  const errorCode = _requiredText(command.error_code, "command.error_code");
  const errorSummary = _requiredText(command.error_summary, "command.error_summary");

  return [{
    sql: (
      "UPDATE fantasy_sync_runs SET completed_at_ms = ?, status = ?, error_code = ?, " +
      "error_summary = ?, accepted_snapshot_id = NULL " +
      "WHERE sync_run_id = ? AND league_season_id = ? AND platform = ? " +
      "AND platform_league_id = ? AND season = ? AND status = ?"
    ),
    parameters: [
      completedAt,
      "FAILED",
      errorCode,
      errorSummary,
      syncRunId,
      identity.league_season_id,
      identity.platform,
      identity.platform_league_id,
      identity.season,
      "STARTED",
    ],
    expected_affected_rows: 1,
  }];
}

function _buildSyncNoChange(command) {
  _assertAllowedKeys(command, [
    "protocol_version",
    "kind",
    "identity",
    "sync_run_id",
    "accepted_snapshot_id",
    "content_fingerprint",
    "completed_at_ms",
  ], "command");

  const identity = _identity(command.identity);
  const syncRunId = _requiredText(command.sync_run_id, "command.sync_run_id");
  const acceptedSnapshotId = _requiredText(
    command.accepted_snapshot_id,
    "command.accepted_snapshot_id",
  );
  const fingerprint = _fingerprint(
    command.content_fingerprint,
    "command.content_fingerprint",
  );
  const completedAt = _nonnegativeSafeInteger(
    command.completed_at_ms,
    "command.completed_at_ms",
  );

  return [{
    sql: (
      "UPDATE fantasy_sync_runs SET completed_at_ms = ?, status = ?, " +
      "accepted_snapshot_id = ?, error_code = NULL, error_summary = NULL " +
      "WHERE sync_run_id = ? AND league_season_id = ? AND platform = ? " +
      "AND platform_league_id = ? AND season = ? AND status = ? " +
      "AND ? = (" +
      "SELECT s.snapshot_id FROM fantasy_state_snapshots AS s " +
      "WHERE s.league_season_id = ? AND EXISTS (" +
      "SELECT 1 FROM fantasy_sync_runs AS prior " +
      "WHERE prior.league_season_id = s.league_season_id " +
      "AND prior.accepted_snapshot_id = s.snapshot_id " +
      "AND prior.status = 'COMPLETED'" +
      ") ORDER BY s.accepted_at_ms DESC, s.snapshot_id DESC LIMIT 1" +
      ") AND EXISTS (" +
      "SELECT 1 FROM fantasy_state_snapshots AS s " +
      "WHERE s.snapshot_id = ? AND s.league_season_id = ? " +
      "AND s.content_fingerprint = ?" +
      ")"
    ),
    parameters: [
      completedAt,
      "COMPLETED",
      acceptedSnapshotId,
      syncRunId,
      identity.league_season_id,
      identity.platform,
      identity.platform_league_id,
      identity.season,
      "STARTED",
      acceptedSnapshotId,
      identity.league_season_id,
      acceptedSnapshotId,
      identity.league_season_id,
      fingerprint,
    ],
    expected_affected_rows: 1,
  }];
}


async function _buildSyncSuccess(command) {
  _assertAllowedKeys(command, [
    "protocol_version",
    "kind",
    "identity",
    "sync_run_id",
    "snapshot",
    "events",
    "completed_at_ms",
  ], "command");

  const identity = _identity(command.identity);
  const syncRunId = _requiredText(command.sync_run_id, "command.sync_run_id");
  const completedAt = _nonnegativeSafeInteger(command.completed_at_ms, "command.completed_at_ms");
  const snapshot = await _snapshot(command.snapshot, identity, completedAt);

  if (!Array.isArray(command.events)) {
    throw new UnsafeFantasyPersistenceCommand("command.events must be an array");
  }

  const seenFingerprints = new Set();
  const eventStatements = command.events.map((event, index) => {
    const normalized = _event(
      event,
      index,
      identity,
      snapshot.snapshot_id,
      snapshot.observed_at_ms,
      completedAt,
    );
    if (seenFingerprints.has(normalized.event_fingerprint)) {
      throw new UnsafeFantasyPersistenceCommand(
        `command.events contains duplicate event_fingerprint ${normalized.event_fingerprint}`,
      );
    }
    seenFingerprints.add(normalized.event_fingerprint);

    return {
      sql: (
        "INSERT INTO fantasy_change_events (" +
        "event_fingerprint, league_season_id, event_type, platform, platform_league_id, season, " +
        "before_snapshot_id, after_snapshot_id, platform_roster_id, platform_player_id, " +
        "before_value_json, after_value_json, source_transaction_ids_json, reason_codes_json, " +
        "derived_at_ms" +
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
      ),
      parameters: [
        normalized.event_fingerprint,
        identity.league_season_id,
        normalized.event_type,
        identity.platform,
        identity.platform_league_id,
        identity.season,
        normalized.before_snapshot_id,
        normalized.after_snapshot_id,
        normalized.platform_roster_id,
        normalized.platform_player_id,
        normalized.before_value_json,
        normalized.after_value_json,
        normalized.source_transaction_ids_json,
        normalized.reason_codes_json,
        normalized.derived_at_ms,
      ],
      expected_affected_rows: 1,
    };
  });

  const snapshotStatement = {
    sql: (
      "INSERT INTO fantasy_state_snapshots (" +
      "snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, " +
      "provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, " +
      "source_metadata_json" +
      ") VALUES (?, (SELECT league_season_id FROM fantasy_sync_runs " +
      "WHERE sync_run_id = ? AND league_season_id = ? AND platform = ? " +
      "AND platform_league_id = ? AND season = ? AND status = 'STARTED'), " +
      "?, ?, ?, ?, ?, ?, ?, ?, ?)"
    ),
    parameters: [
      snapshot.snapshot_id,
      syncRunId,
      identity.league_season_id,
      identity.platform,
      identity.platform_league_id,
      identity.season,
      snapshot.content_fingerprint,
      snapshot.observed_at_ms,
      snapshot.accepted_at_ms,
      snapshot.provider_status,
      snapshot.rules_ready ? 1 : 0,
      snapshot.draft_ready ? 1 : 0,
      snapshot.ownership_ready ? 1 : 0,
      snapshot.normalized_state_json,
      snapshot.source_metadata_json,
    ],
    expected_affected_rows: 1,
  };

  const completionStatement = {
    sql: (
      "UPDATE fantasy_sync_runs SET completed_at_ms = ?, status = ?, accepted_snapshot_id = ?, " +
      "error_code = NULL, error_summary = NULL " +
      "WHERE sync_run_id = ? AND league_season_id = ? AND platform = ? " +
      "AND platform_league_id = ? AND season = ? AND status = ?"
    ),
    parameters: [
      completedAt,
      "COMPLETED",
      snapshot.snapshot_id,
      syncRunId,
      identity.league_season_id,
      identity.platform,
      identity.platform_league_id,
      identity.season,
      "STARTED",
    ],
    expected_affected_rows: 1,
  };

  return [snapshotStatement, ...eventStatements, completionStatement];
}

function _identity(value) {
  _requireObject(value, "command.identity");
  _assertAllowedKeys(value, [
    "league_season_id",
    "platform",
    "platform_league_id",
    "season",
  ], "command.identity");
  return {
    league_season_id: _requiredText(value.league_season_id, "command.identity.league_season_id"),
    platform: _requiredText(value.platform, "command.identity.platform"),
    platform_league_id: _requiredText(value.platform_league_id, "command.identity.platform_league_id"),
    season: _requiredText(value.season, "command.identity.season"),
  };
}

async function _snapshot(value, identity, completedAt) {
  _requireObject(value, "command.snapshot");
  _assertAllowedKeys(value, [
    "snapshot_id",
    "content_fingerprint",
    "observed_at_ms",
    "accepted_at_ms",
    "provider_status",
    "rules_ready",
    "draft_ready",
    "ownership_ready",
    "normalized_state_json",
    "source_metadata_json",
  ], "command.snapshot");

  const snapshotId = _requiredText(value.snapshot_id, "command.snapshot.snapshot_id");
  const fingerprint = _fingerprint(value.content_fingerprint, "command.snapshot.content_fingerprint");
  const observedAt = _nonnegativeSafeInteger(value.observed_at_ms, "command.snapshot.observed_at_ms");
  const acceptedAt = _nonnegativeSafeInteger(value.accepted_at_ms, "command.snapshot.accepted_at_ms");
  const providerStatus = _requiredText(value.provider_status, "command.snapshot.provider_status");
  const rulesReady = _boolean(value.rules_ready, "command.snapshot.rules_ready");
  const draftReady = _boolean(value.draft_ready, "command.snapshot.draft_ready");
  const ownershipReady = _boolean(value.ownership_ready, "command.snapshot.ownership_ready");
  const normalizedStateJson = _jsonObjectText(
    value.normalized_state_json,
    "command.snapshot.normalized_state_json",
  );
  const sourceMetadataJson = _jsonObjectText(
    value.source_metadata_json,
    "command.snapshot.source_metadata_json",
  );

  if (acceptedAt < observedAt) {
    throw new UnsafeFantasyPersistenceCommand(
      "command.snapshot.accepted_at_ms cannot precede observed_at_ms",
    );
  }
  if (completedAt < acceptedAt) {
    throw new UnsafeFantasyPersistenceCommand(
      "command.completed_at_ms cannot precede snapshot.accepted_at_ms",
    );
  }

  const parsedState = JSON.parse(normalizedStateJson);
  const league = parsedState.league;
  if (!league || typeof league !== "object" || Array.isArray(league)) {
    throw new UnsafeFantasyPersistenceCommand(
      "command.snapshot.normalized_state_json must contain a league object",
    );
  }
  if (
    league.platform !== identity.platform ||
    league.platform_league_id !== identity.platform_league_id ||
    league.season !== identity.season
  ) {
    throw new UnsafeFantasyPersistenceCommand(
      "command.snapshot normalized league identity does not match command.identity",
    );
  }
  if (
    league.rules_ready !== rulesReady ||
    league.draft_ready !== draftReady ||
    league.ownership_ready !== ownershipReady
  ) {
    throw new UnsafeFantasyPersistenceCommand(
      "command.snapshot readiness flags do not match normalized league state",
    );
  }

  const actualFingerprint = await _sha256Hex(normalizedStateJson);
  if (actualFingerprint !== fingerprint) {
    throw new UnsafeFantasyPersistenceCommand(
      "command.snapshot.content_fingerprint does not match normalized_state_json",
    );
  }

  return {
    snapshot_id: snapshotId,
    content_fingerprint: fingerprint,
    observed_at_ms: observedAt,
    accepted_at_ms: acceptedAt,
    provider_status: providerStatus,
    rules_ready: rulesReady,
    draft_ready: draftReady,
    ownership_ready: ownershipReady,
    normalized_state_json: normalizedStateJson,
    source_metadata_json: sourceMetadataJson,
  };
}

function _event(value, index, identity, snapshotId, observedAt, completedAt) {
  const label = `command.events[${index}]`;
  _requireObject(value, label);
  _assertAllowedKeys(value, [
    "event_fingerprint",
    "event_type",
    "before_snapshot_id",
    "after_snapshot_id",
    "platform_roster_id",
    "platform_player_id",
    "before_value_json",
    "after_value_json",
    "source_transaction_ids_json",
    "reason_codes_json",
    "derived_at_ms",
  ], label);

  const beforeSnapshotId = _requiredText(value.before_snapshot_id, `${label}.before_snapshot_id`);
  const afterSnapshotId = _requiredText(value.after_snapshot_id, `${label}.after_snapshot_id`);
  if (afterSnapshotId !== snapshotId) {
    throw new UnsafeFantasyPersistenceCommand(
      `${label}.after_snapshot_id must equal command.snapshot.snapshot_id`,
    );
  }
  if (beforeSnapshotId === afterSnapshotId) {
    throw new UnsafeFantasyPersistenceCommand(
      `${label} cannot use one snapshot as both before and after`,
    );
  }

  const derivedAt = _nonnegativeSafeInteger(value.derived_at_ms, `${label}.derived_at_ms`);
  if (derivedAt < observedAt || derivedAt > completedAt) {
    throw new UnsafeFantasyPersistenceCommand(
      `${label}.derived_at_ms must be between snapshot observation and sync completion`,
    );
  }

  return {
    event_fingerprint: _fingerprint(value.event_fingerprint, `${label}.event_fingerprint`),
    event_type: _requiredText(value.event_type, `${label}.event_type`),
    before_snapshot_id: beforeSnapshotId,
    after_snapshot_id: afterSnapshotId,
    platform_roster_id: _optionalText(value.platform_roster_id, `${label}.platform_roster_id`),
    platform_player_id: _optionalText(value.platform_player_id, `${label}.platform_player_id`),
    before_value_json: _nullableJsonText(value.before_value_json, `${label}.before_value_json`),
    after_value_json: _nullableJsonText(value.after_value_json, `${label}.after_value_json`),
    source_transaction_ids_json: _jsonStringArrayText(
      value.source_transaction_ids_json,
      `${label}.source_transaction_ids_json`,
    ),
    reason_codes_json: _jsonStringArrayText(
      value.reason_codes_json,
      `${label}.reason_codes_json`,
    ),
    derived_at_ms: derivedAt,
    identity,
  };
}

function _requireObject(value, label) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new UnsafeFantasyPersistenceCommand(`${label} must be an object`);
  }
}

function _assertAllowedKeys(value, allowed, label) {
  const allowedSet = new Set(allowed);
  const unknown = Object.keys(value).filter((key) => !allowedSet.has(key));
  if (unknown.length) {
    throw new UnsafeFantasyPersistenceCommand(
      `${label} contains unsupported field(s): ${unknown.sort().join(", ")}`,
    );
  }
}

function _requiredText(value, label) {
  if (typeof value !== "string" || !value.trim()) {
    throw new UnsafeFantasyPersistenceCommand(`${label} must be a non-empty string`);
  }
  return value.trim();
}

function _optionalText(value, label) {
  if (value === null) {
    return null;
  }
  return _requiredText(value, label);
}

function _boolean(value, label) {
  if (typeof value !== "boolean") {
    throw new UnsafeFantasyPersistenceCommand(`${label} must be boolean`);
  }
  return value;
}

function _nonnegativeSafeInteger(value, label) {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new UnsafeFantasyPersistenceCommand(
      `${label} must be a non-negative JavaScript safe integer`,
    );
  }
  return value;
}

function _fingerprint(value, label) {
  const normalized = _requiredText(value, label);
  if (!FINGERPRINT.test(normalized)) {
    throw new UnsafeFantasyPersistenceCommand(
      `${label} must be a lowercase SHA-256 hex digest`,
    );
  }
  return normalized;
}

function _jsonObjectText(value, label) {
  const parsed = _jsonText(value, label);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new UnsafeFantasyPersistenceCommand(`${label} must encode a JSON object`);
  }
  return value;
}

function _jsonStringArrayText(value, label) {
  const parsed = _jsonText(value, label);
  if (!Array.isArray(parsed) || parsed.some((item) => typeof item !== "string")) {
    throw new UnsafeFantasyPersistenceCommand(
      `${label} must encode an array of strings`,
    );
  }
  return value;
}

function _nullableJsonText(value, label) {
  if (value === null) {
    return null;
  }
  _jsonText(value, label);
  return value;
}

function _jsonText(value, label) {
  if (typeof value !== "string" || !value.trim()) {
    throw new UnsafeFantasyPersistenceCommand(`${label} must be non-empty JSON text`);
  }
  try {
    return JSON.parse(value);
  } catch {
    throw new UnsafeFantasyPersistenceCommand(`${label} is not valid JSON`);
  }
}

async function _sha256Hex(value) {
  if (!globalThis.crypto?.subtle) {
    throw new UnsafeFantasyPersistenceCommand(
      "Web Crypto SHA-256 support is required for persistence fingerprint validation",
    );
  }
  const encoded = new TextEncoder().encode(value);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", encoded);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0")
  ).join("");
}
