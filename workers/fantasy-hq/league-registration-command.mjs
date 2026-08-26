import { executePersistenceBatch } from "./d1-executor.mjs";
import {
  FANTASY_PERSISTENCE_PROTOCOL_VERSION,
  UnsafeFantasyPersistenceCommand,
} from "./persistence-command.mjs";

export const LEAGUE_SEASON_UPSERT = "LEAGUE_SEASON_UPSERT";

/**
 * Build the only SQL allowed for registering one fantasy league family/season.
 *
 * Existing family labels/metadata may be refreshed. Existing league-season
 * identity is immutable: if a league_season_id is reused with a different
 * family/platform/platform league/season, the guarded UPDATE deliberately
 * writes an invalid empty display name so the table CHECK constraint fails and
 * D1 rolls back the entire batch.
 */
export function buildLeagueSeasonRegistrationStatements(command) {
  _requireObject(command, "command");
  _assertAllowedKeys(command, [
    "protocol_version",
    "kind",
    "identity",
    "league_family_id",
    "family_display_name",
    "season_display_name",
    "created_at_ms",
    "family_metadata_json",
    "season_metadata_json",
  ], "command");

  if (command.protocol_version !== FANTASY_PERSISTENCE_PROTOCOL_VERSION) {
    throw new UnsafeFantasyPersistenceCommand(
      `unsupported persistence protocol version ${String(command.protocol_version)}`,
    );
  }
  if (_requiredText(command.kind, "command.kind") !== LEAGUE_SEASON_UPSERT) {
    throw new UnsafeFantasyPersistenceCommand(
      `unsupported league registration command kind ${String(command.kind)}`,
    );
  }

  const identity = _identity(command.identity);
  const leagueFamilyId = _requiredText(
    command.league_family_id,
    "command.league_family_id",
  );
  const familyDisplayName = _requiredText(
    command.family_display_name,
    "command.family_display_name",
  );
  const seasonDisplayName = _requiredText(
    command.season_display_name,
    "command.season_display_name",
  );
  const createdAt = _nonnegativeSafeInteger(
    command.created_at_ms,
    "command.created_at_ms",
  );
  const familyMetadata = _jsonObjectText(
    command.family_metadata_json,
    "command.family_metadata_json",
  );
  const seasonMetadata = _jsonObjectText(
    command.season_metadata_json,
    "command.season_metadata_json",
  );

  const familyStatement = {
    sql: (
      "INSERT INTO fantasy_league_families (" +
      "league_family_id, display_name, created_at_ms, metadata_json" +
      ") VALUES (?, ?, ?, ?) " +
      "ON CONFLICT(league_family_id) DO UPDATE SET " +
      "display_name = excluded.display_name, metadata_json = excluded.metadata_json"
    ),
    parameters: [
      leagueFamilyId,
      familyDisplayName,
      createdAt,
      familyMetadata,
    ],
    expected_affected_rows: 1,
  };

  const seasonStatement = {
    sql: (
      "INSERT INTO fantasy_league_seasons (" +
      "league_season_id, league_family_id, platform, platform_league_id, season, " +
      "display_name, created_at_ms, metadata_json" +
      ") VALUES (?, ?, ?, ?, ?, ?, ?, ?) " +
      "ON CONFLICT(league_season_id) DO UPDATE SET " +
      "display_name = CASE WHEN " +
      "fantasy_league_seasons.league_family_id = excluded.league_family_id AND " +
      "fantasy_league_seasons.platform = excluded.platform AND " +
      "fantasy_league_seasons.platform_league_id = excluded.platform_league_id AND " +
      "fantasy_league_seasons.season = excluded.season " +
      "THEN excluded.display_name ELSE '' END, " +
      "metadata_json = excluded.metadata_json"
    ),
    parameters: [
      identity.league_season_id,
      leagueFamilyId,
      identity.platform,
      identity.platform_league_id,
      identity.season,
      seasonDisplayName,
      createdAt,
      seasonMetadata,
    ],
    expected_affected_rows: 1,
  };

  return [familyStatement, seasonStatement];
}

export async function executeLeagueSeasonRegistrationCommand(db, command) {
  const statements = buildLeagueSeasonRegistrationStatements(command);
  const results = await executePersistenceBatch(db, statements);
  return {
    protocol_version: FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    kind: LEAGUE_SEASON_UPSERT,
    league_season_id: command.identity.league_season_id.trim(),
    results,
  };
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
    league_season_id: _requiredText(
      value.league_season_id,
      "command.identity.league_season_id",
    ),
    platform: _requiredText(value.platform, "command.identity.platform"),
    platform_league_id: _requiredText(
      value.platform_league_id,
      "command.identity.platform_league_id",
    ),
    season: _requiredText(value.season, "command.identity.season"),
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

function _nonnegativeSafeInteger(value, label) {
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new UnsafeFantasyPersistenceCommand(
      `${label} must be a non-negative JavaScript safe integer`,
    );
  }
  return value;
}

function _jsonObjectText(value, label) {
  if (typeof value !== "string" || !value.trim()) {
    throw new UnsafeFantasyPersistenceCommand(`${label} must be non-empty JSON text`);
  }
  let parsed;
  try {
    parsed = JSON.parse(value);
  } catch {
    throw new UnsafeFantasyPersistenceCommand(`${label} is not valid JSON`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new UnsafeFantasyPersistenceCommand(`${label} must encode a JSON object`);
  }
  return value;
}
