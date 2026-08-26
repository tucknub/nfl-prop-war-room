import { FANTASY_PERSISTENCE_PROTOCOL_VERSION } from "./persistence-command.mjs";

export const FANTASY_SHADOW_MODE = "SHADOW";
export const FANTASY_SHADOW_EVENT = "fantasy_hq_shadow_schedule";
export const FANTASY_SHADOW_SCHEMA_SQL =
  "SELECT COUNT(*) AS row_count FROM fantasy_league_seasons";

export class FantasyShadowReadinessError extends Error {
  constructor(message, options = {}) {
    super(message, options);
    this.name = "FantasyShadowReadinessError";
  }
}

/**
 * Read-only Cloudflare scheduled-handler probe.
 *
 * This intentionally does not execute the Python Fantasy HQ scheduler contract
 * and does not write any fantasy state. It proves only that the Worker receives
 * a scheduled event, is explicitly in SHADOW mode, has a usable D1 binding,
 * and can read the migrated Fantasy HQ schema.
 */
export async function runFantasyShadowScheduled(
  controller,
  env = {},
  options = {},
) {
  const scheduledAtMs = _scheduledAt(controller);
  const cron = _cron(controller);

  if (env.FANTASY_SCHEDULE_MODE !== FANTASY_SHADOW_MODE) {
    throw new FantasyShadowReadinessError(
      "Fantasy HQ scheduled handler is not enabled in SHADOW mode",
    );
  }

  const db = env.FANTASY_DB;
  if (!db || typeof db.prepare !== "function") {
    throw new FantasyShadowReadinessError(
      "Fantasy HQ D1 binding is unavailable",
    );
  }

  let result;
  try {
    const statement = db.prepare(FANTASY_SHADOW_SCHEMA_SQL);
    if (!statement || typeof statement.first !== "function") {
      throw new TypeError("D1 schema probe does not support first()");
    }
    result = await statement.first();
  } catch (cause) {
    throw new FantasyShadowReadinessError(
      "Fantasy HQ D1 schema probe failed",
      { cause },
    );
  }

  if (
    !result ||
    typeof result !== "object" ||
    !Number.isSafeInteger(result.row_count) ||
    result.row_count < 0
  ) {
    throw new FantasyShadowReadinessError(
      "Fantasy HQ D1 schema probe returned an invalid result",
    );
  }

  const summary = Object.freeze({
    event: FANTASY_SHADOW_EVENT,
    status: "ready",
    mode: FANTASY_SHADOW_MODE,
    scheduled_at_ms: scheduledAtMs,
    cron,
    protocol_version: FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    d1_schema_ready: true,
    write_enabled: false,
  });

  _logShadowResult(options.logger ?? console, summary);
  return summary;
}

function _scheduledAt(controller) {
  const value = controller?.scheduledTime;
  if (!Number.isSafeInteger(value) || value < 0) {
    throw new FantasyShadowReadinessError(
      "Scheduled event requires a non-negative safe scheduledTime",
    );
  }
  return value;
}

function _cron(controller) {
  const value = controller?.cron;
  if (typeof value !== "string" || !value || value !== value.trim()) {
    throw new FantasyShadowReadinessError(
      "Scheduled event requires a canonical cron expression",
    );
  }
  if (value.length > 128 || /[\u0000-\u001f\u007f]/u.test(value)) {
    throw new FantasyShadowReadinessError(
      "Scheduled cron expression is invalid",
    );
  }
  return value;
}

function _logShadowResult(logger, summary) {
  if (!logger || typeof logger.info !== "function") {
    return;
  }
  logger.info("Fantasy HQ scheduled shadow readiness", summary);
}
