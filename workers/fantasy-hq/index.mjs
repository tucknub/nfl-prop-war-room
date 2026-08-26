import {
  FANTASY_PERSISTENCE_PROTOCOL_VERSION,
  UnsafeFantasyPersistenceCommand,
} from "./persistence-command.mjs";
import { executeFantasyWorkerCommand } from "./command-router.mjs";
import {
  FantasyReadExecutionError,
  UnsafeFantasyReadRequest,
  executeFantasyRead,
  parseFantasyReadPath,
} from "./read-query.mjs";
import {
  D1BatchExecutionError,
  D1WriteInvariantError,
  UnsafeD1WritePlan,
} from "./d1-executor.mjs";

export const HEALTH_PATH = "/health";
export const PERSISTENCE_PATH = "/v1/fantasy/persistence";
export const READ_PATH_PREFIX = "/v1/fantasy/read/";
export const MAX_COMMAND_BODY_BYTES = 512 * 1024;

const JSON_HEADERS = Object.freeze({
  "Cache-Control": "no-store",
  "Content-Type": "application/json; charset=utf-8",
  "X-Content-Type-Options": "nosniff",
});

const encoder = new TextEncoder();

export default {
  async fetch(request, env) {
    return handleFantasyPersistenceRequest(request, env);
  },
};

/**
 * Authenticated HTTP boundary for Fantasy HQ persistence protocol v1.
 *
 * Writes never accept SQL: structured commands are validated by the command
 * router, which delegates only to fixed-SQL command handlers. Recovery reads
 * are GET-only and map only to fixed SELECT templates in read-query.mjs.
 */
export async function handleFantasyPersistenceRequest(request, env = {}, options = {}) {
  const url = new URL(request.url);

  if (url.pathname === HEALTH_PATH) {
    if (request.method !== "GET") {
      return methodNotAllowed("GET");
    }
    return jsonResponse(200, {
      ok: true,
      status: "ok",
      protocol_version: FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    });
  }

  let readRequest = null;
  if (url.pathname.startsWith(READ_PATH_PREFIX)) {
    try {
      readRequest = parseFantasyReadPath(url.pathname);
    } catch (error) {
      if (error instanceof UnsafeFantasyReadRequest) {
        return errorResponse(400, "INVALID_READ_REQUEST", error.message);
      }
      return errorResponse(400, "INVALID_READ_REQUEST", "Invalid read request");
    }
    if (readRequest === null) {
      return errorResponse(404, "NOT_FOUND", "Not found");
    }
  } else if (url.pathname !== PERSISTENCE_PATH) {
    return errorResponse(404, "NOT_FOUND", "Not found");
  }

  if (readRequest !== null) {
    if (request.method !== "GET") {
      return methodNotAllowed("GET");
    }
  } else if (request.method !== "POST") {
    return methodNotAllowed("POST");
  }

  const expectedToken = _configuredToken(env.FANTASY_PERSISTENCE_TOKEN);
  if (expectedToken === null) {
    return errorResponse(503, "SERVICE_UNAVAILABLE", "Service unavailable");
  }

  const providedToken = _bearerToken(request.headers.get("authorization"));
  if (providedToken === null) {
    return unauthorized();
  }

  const subtle = options.subtle ?? globalThis.crypto?.subtle;
  let authorized = false;
  try {
    authorized = await verifyBearerToken(providedToken, expectedToken, subtle);
  } catch {
    return errorResponse(503, "SERVICE_UNAVAILABLE", "Service unavailable");
  }
  if (!authorized) {
    return unauthorized();
  }

  if (!_isD1Binding(env.FANTASY_DB)) {
    return errorResponse(503, "SERVICE_UNAVAILABLE", "Service unavailable");
  }

  if (readRequest !== null) {
    const executeRead = options.executeRead ?? executeFantasyRead;
    try {
      const result = await executeRead(env.FANTASY_DB, readRequest);
      return jsonResponse(200, { ok: true, ...result });
    } catch (error) {
      if (error instanceof UnsafeFantasyReadRequest) {
        return errorResponse(400, "INVALID_READ_REQUEST", error.message);
      }
      if (error instanceof FantasyReadExecutionError) {
        _logPersistenceFailure(options.logger ?? console, error);
        return errorResponse(500, "READ_FAILED", "Fantasy read failed");
      }
      _logPersistenceFailure(options.logger ?? console, error);
      return errorResponse(500, "INTERNAL_ERROR", "Internal server error");
    }
  }

  if (!_isJsonContentType(request.headers.get("content-type"))) {
    return errorResponse(
      415,
      "UNSUPPORTED_MEDIA_TYPE",
      "Content-Type must be application/json",
    );
  }

  if (!_isIdentityEncoding(request.headers.get("content-encoding"))) {
    return errorResponse(
      415,
      "UNSUPPORTED_CONTENT_ENCODING",
      "Compressed request bodies are not accepted",
    );
  }

  let bodyText;
  try {
    bodyText = await readLimitedUtf8Body(request, MAX_COMMAND_BODY_BYTES);
  } catch (error) {
    if (error instanceof RequestBodyError) {
      return errorResponse(error.status, error.code, error.message);
    }
    return errorResponse(400, "INVALID_BODY", "Invalid request body");
  }

  let command;
  try {
    command = JSON.parse(bodyText);
  } catch {
    return errorResponse(400, "INVALID_JSON", "Request body must contain valid JSON");
  }

  const executeCommand = options.executeCommand ?? executeFantasyWorkerCommand;
  try {
    const result = await executeCommand(env.FANTASY_DB, command);
    return jsonResponse(200, { ok: true, ...result });
  } catch (error) {
    if (error instanceof UnsafeFantasyPersistenceCommand) {
      return errorResponse(400, "INVALID_COMMAND", error.message);
    }
    if (
      error instanceof UnsafeD1WritePlan ||
      error instanceof D1BatchExecutionError ||
      error instanceof D1WriteInvariantError
    ) {
      _logPersistenceFailure(options.logger ?? console, error);
      return errorResponse(500, "PERSISTENCE_FAILED", "Persistence command failed");
    }
    _logPersistenceFailure(options.logger ?? console, error);
    return errorResponse(500, "INTERNAL_ERROR", "Internal server error");
  }
}

/**
 * Compare a supplied bearer token with the configured Worker secret without a
 * direct secret-string equality check. Both values are SHA-256 hashed first so
 * timingSafeEqual always receives equal-length inputs.
 */
export async function verifyBearerToken(providedToken, expectedToken, subtle) {
  if (
    !subtle ||
    typeof subtle.digest !== "function" ||
    typeof subtle.timingSafeEqual !== "function"
  ) {
    throw new TypeError("Web Crypto timingSafeEqual support is required");
  }

  const [providedHash, expectedHash] = await Promise.all([
    subtle.digest("SHA-256", encoder.encode(providedToken)),
    subtle.digest("SHA-256", encoder.encode(expectedToken)),
  ]);

  return subtle.timingSafeEqual(
    new Uint8Array(providedHash),
    new Uint8Array(expectedHash),
  );
}

export async function readLimitedUtf8Body(request, maxBytes = MAX_COMMAND_BODY_BYTES) {
  if (!Number.isSafeInteger(maxBytes) || maxBytes <= 0) {
    throw new TypeError("maxBytes must be a positive safe integer");
  }

  const declaredLength = request.headers.get("content-length");
  if (declaredLength !== null) {
    const normalized = declaredLength.trim();
    if (!/^(0|[1-9][0-9]*)$/.test(normalized)) {
      throw new RequestBodyError(
        400,
        "INVALID_CONTENT_LENGTH",
        "Content-Length must be a non-negative integer",
      );
    }
    const parsed = Number(normalized);
    if (!Number.isSafeInteger(parsed)) {
      throw new RequestBodyError(
        400,
        "INVALID_CONTENT_LENGTH",
        "Content-Length is outside the supported range",
      );
    }
    if (parsed > maxBytes) {
      throw new RequestBodyError(413, "BODY_TOO_LARGE", "Request body is too large");
    }
  }

  if (request.body === null) {
    throw new RequestBodyError(400, "EMPTY_BODY", "Request body is required");
  }

  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      if (!(value instanceof Uint8Array)) {
        throw new RequestBodyError(400, "INVALID_BODY", "Request body is invalid");
      }
      total += value.byteLength;
      if (total > maxBytes) {
        try {
          await reader.cancel();
        } catch {
          // Best effort only; the request is already being rejected.
        }
        throw new RequestBodyError(413, "BODY_TOO_LARGE", "Request body is too large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }

  if (total === 0) {
    throw new RequestBodyError(400, "EMPTY_BODY", "Request body is required");
  }

  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }

  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new RequestBodyError(400, "INVALID_UTF8", "Request body must be valid UTF-8");
  }

  if (!text.trim()) {
    throw new RequestBodyError(400, "EMPTY_BODY", "Request body is required");
  }
  return text;
}

class RequestBodyError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = "RequestBodyError";
    this.status = status;
    this.code = code;
  }
}

function _configuredToken(value) {
  if (typeof value !== "string") {
    return null;
  }
  if (value.length < 32 || /\s/u.test(value)) {
    return null;
  }
  return value;
}

function _bearerToken(value) {
  if (typeof value !== "string") {
    return null;
  }
  const match = /^Bearer ([^\s]+)$/i.exec(value.trim());
  return match ? match[1] : null;
}

function _isD1Binding(value) {
  return Boolean(
    value &&
      typeof value.prepare === "function" &&
      typeof value.batch === "function",
  );
}

function _isJsonContentType(value) {
  if (typeof value !== "string") {
    return false;
  }
  return value.split(";", 1)[0].trim().toLowerCase() === "application/json";
}

function _isIdentityEncoding(value) {
  if (value === null) {
    return true;
  }
  return value.trim().toLowerCase() === "identity";
}

function unauthorized() {
  const response = errorResponse(401, "UNAUTHORIZED", "Unauthorized");
  response.headers.set("WWW-Authenticate", 'Bearer realm="fantasy-hq"');
  return response;
}

function methodNotAllowed(allowed) {
  const response = errorResponse(405, "METHOD_NOT_ALLOWED", "Method not allowed");
  response.headers.set("Allow", allowed);
  return response;
}

function errorResponse(status, code, message) {
  return jsonResponse(status, {
    ok: false,
    error: { code, message },
  });
}

function jsonResponse(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: JSON_HEADERS,
  });
}

function _logPersistenceFailure(logger, error) {
  if (!logger || typeof logger.error !== "function") {
    return;
  }
  const name = error instanceof Error ? error.name : "UnknownError";
  logger.error("Fantasy HQ persistence request failed", { error_name: name });
}
