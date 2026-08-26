import {
  LEAGUE_SEASON_UPSERT,
  executeLeagueSeasonRegistrationCommand,
} from "./league-registration-command.mjs";
import { executeFantasyPersistenceCommand } from "./persistence-command.mjs";

/**
 * Route versioned Fantasy HQ commands without ever exposing a generic SQL path.
 * Sync commands retain the existing persistence-command validator; registration
 * has its own fixed-SQL validator.
 */
export async function executeFantasyWorkerCommand(db, command) {
  if (command?.kind === LEAGUE_SEASON_UPSERT) {
    return executeLeagueSeasonRegistrationCommand(db, command);
  }
  return executeFantasyPersistenceCommand(db, command);
}
