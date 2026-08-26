from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote, urlsplit

import httpx

from .league_registration_protocol import LEAGUE_SEASON_UPSERT
from .persistence_protocol import (
    FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    SYNC_FAILED,
    SYNC_START,
    SYNC_SUCCESS,
)


PERSISTENCE_PATH = "/v1/fantasy/persistence"
READ_PATH_PREFIX = "/v1/fantasy/read"
HEALTH_PATH = "/health"
MAX_COMMAND_BODY_BYTES = 512 * 1024
MAX_RESPONSE_BODY_BYTES = 64 * 1024
MAX_SNAPSHOT_RESPONSE_BODY_BYTES = MAX_COMMAND_BODY_BYTES + 16 * 1024
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
READ_LEAGUE_SEASON = "READ_LEAGUE_SEASON"
READ_SYNC_RUN = "READ_SYNC_RUN"
READ_LATEST_SNAPSHOT = "READ_LATEST_SNAPSHOT"
SUPPORTED_COMMAND_KINDS = frozenset(
    {LEAGUE_SEASON_UPSERT, SYNC_START, SYNC_FAILED, SYNC_SUCCESS}
)


class UnsafeFantasyPersistenceTransport(ValueError):
    """Raised before network I/O when transport configuration/input is unsafe."""


class FantasyPersistenceTransportError(RuntimeError):
    """Raised when the request could not complete or the response was unreadable."""


class FantasyPersistenceProtocolError(RuntimeError):
    """Raised when the Worker returns a response that violates the v1 contract."""


class FantasyPersistenceRejected(RuntimeError):
    """Raised when the Worker explicitly rejects a valid HTTP request."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.worker_message = message
        super().__init__(f"Fantasy persistence request rejected ({status_code} {code})")


@dataclass(frozen=True)
class FantasyPersistenceClientConfig:
    endpoint: str
    token: str
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
    max_response_body_bytes: int = MAX_RESPONSE_BODY_BYTES
    max_snapshot_response_body_bytes: int = MAX_SNAPSHOT_RESPONSE_BODY_BYTES

    def __post_init__(self) -> None:
        object.__setattr__(self, "endpoint", _validated_endpoint(self.endpoint))
        object.__setattr__(self, "token", _validated_token(self.token))
        _positive_number(self.timeout_seconds, "timeout_seconds")
        _positive_number(self.connect_timeout_seconds, "connect_timeout_seconds")
        _positive_int(self.max_response_body_bytes, "max_response_body_bytes")
        _positive_int(
            self.max_snapshot_response_body_bytes,
            "max_snapshot_response_body_bytes",
        )

    @classmethod
    def from_env(
        cls,
        *,
        endpoint_var: str = "FANTASY_PERSISTENCE_URL",
        token_var: str = "FANTASY_PERSISTENCE_TOKEN",
    ) -> "FantasyPersistenceClientConfig":
        endpoint = os.environ.get(endpoint_var)
        token = os.environ.get(token_var)
        if endpoint is None:
            raise UnsafeFantasyPersistenceTransport(
                f"required environment variable {endpoint_var} is not configured"
            )
        if token is None:
            raise UnsafeFantasyPersistenceTransport(
                f"required environment variable {token_var} is not configured"
            )
        return cls(endpoint=endpoint, token=token)


class FantasyPersistenceHttpClient:
    """One-shot transport for versioned Fantasy HQ Worker commands and recovery reads.

    Automatic retries are intentionally absent. A caller cannot safely infer that
    a failed HTTP response means a write did not reach D1, so retry/recovery policy
    must be explicit at a higher layer and may use the authenticated read methods.
    """

    def __init__(
        self,
        config: FantasyPersistenceClientConfig,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        timeout = httpx.Timeout(
            config.timeout_seconds,
            connect=config.connect_timeout_seconds,
        )
        self._client = httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            transport=transport,
            trust_env=False,
            headers={"User-Agent": "propwar-fantasy-hq-persistence/1"},
        )

    def __enter__(self) -> "FantasyPersistenceHttpClient":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def send(self, command: Mapping[str, Any]) -> Mapping[str, Any]:
        encoded, expected_kind, expected_identifier_key, expected_identifier = (
            _encode_and_validate_command(command)
        )

        try:
            with self._client.stream(
                "POST",
                self.config.endpoint,
                headers={
                    "Authorization": f"Bearer {self.config.token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                content=encoded,
            ) as response:
                body = _read_limited_response(
                    response,
                    self.config.max_response_body_bytes,
                )
        except httpx.HTTPError as exc:
            raise FantasyPersistenceTransportError(
                "Fantasy persistence request could not be completed"
            ) from exc

        payload = _decode_json_response(response, body)
        if response.status_code != 200:
            raise _rejection_from_payload(response.status_code, payload)

        _validate_success_response(
            payload,
            expected_kind=expected_kind,
            expected_identifier_key=expected_identifier_key,
            expected_identifier=expected_identifier,
        )
        return payload

    def read_league_season(self, league_season_id: str) -> Mapping[str, Any]:
        identifier = _validated_read_identifier(league_season_id, "league_season_id")
        payload = self._read_resource(
            kind=READ_LEAGUE_SEASON,
            identifier=identifier,
            path=f"{READ_PATH_PREFIX}/league-seasons/{quote(identifier, safe='')}",
            max_bytes=self.config.max_response_body_bytes,
        )
        record = payload["record"]
        if payload["found"]:
            if record.get("league_season_id") != identifier:
                raise FantasyPersistenceProtocolError(
                    "Fantasy league-season read returned the wrong league_season_id"
                )
            if not isinstance(record.get("metadata"), Mapping):
                raise FantasyPersistenceProtocolError(
                    "Fantasy league-season read metadata must be an object"
                )
        return payload

    def read_sync_run(self, sync_run_id: str) -> Mapping[str, Any]:
        identifier = _validated_read_identifier(sync_run_id, "sync_run_id")
        payload = self._read_resource(
            kind=READ_SYNC_RUN,
            identifier=identifier,
            path=f"{READ_PATH_PREFIX}/sync-runs/{quote(identifier, safe='')}",
            max_bytes=self.config.max_response_body_bytes,
        )
        record = payload["record"]
        if payload["found"] and record.get("sync_run_id") != identifier:
            raise FantasyPersistenceProtocolError(
                "Fantasy sync-run read returned the wrong sync_run_id"
            )
        return payload

    def read_latest_snapshot(self, league_season_id: str) -> Mapping[str, Any]:
        identifier = _validated_read_identifier(league_season_id, "league_season_id")
        payload = self._read_resource(
            kind=READ_LATEST_SNAPSHOT,
            identifier=identifier,
            path=(
                f"{READ_PATH_PREFIX}/league-seasons/{quote(identifier, safe='')}"
                "/latest-snapshot"
            ),
            max_bytes=self.config.max_snapshot_response_body_bytes,
        )
        record = payload["record"]
        if payload["found"]:
            if record.get("league_season_id") != identifier:
                raise FantasyPersistenceProtocolError(
                    "Fantasy latest-snapshot read returned the wrong league_season_id"
                )
            if not isinstance(record.get("normalized_state"), Mapping):
                raise FantasyPersistenceProtocolError(
                    "Fantasy latest-snapshot normalized_state must be an object"
                )
            if not isinstance(record.get("source_metadata"), Mapping):
                raise FantasyPersistenceProtocolError(
                    "Fantasy latest-snapshot source_metadata must be an object"
                )
            for key in ("rules_ready", "draft_ready", "ownership_ready"):
                if not isinstance(record.get(key), bool):
                    raise FantasyPersistenceProtocolError(
                        f"Fantasy latest-snapshot {key} must be boolean"
                    )
        return payload

    def _read_resource(
        self,
        *,
        kind: str,
        identifier: str,
        path: str,
        max_bytes: int,
    ) -> Mapping[str, Any]:
        url = f"{_origin_url(self.config.endpoint)}{path}"
        try:
            with self._client.stream(
                "GET",
                url,
                headers={
                    "Authorization": f"Bearer {self.config.token}",
                    "Accept": "application/json",
                },
            ) as response:
                body = _read_limited_response(response, max_bytes)
        except httpx.HTTPError as exc:
            raise FantasyPersistenceTransportError(
                "Fantasy persistence read could not be completed"
            ) from exc

        payload = _decode_json_response(response, body)
        if response.status_code != 200:
            raise _rejection_from_payload(response.status_code, payload)
        _validate_read_response(payload, expected_kind=kind, expected_identifier=identifier)
        return payload

    def health(self) -> Mapping[str, Any]:
        health_url = _health_url(self.config.endpoint)
        try:
            with self._client.stream(
                "GET",
                health_url,
                headers={"Accept": "application/json"},
            ) as response:
                body = _read_limited_response(
                    response,
                    self.config.max_response_body_bytes,
                )
        except httpx.HTTPError as exc:
            raise FantasyPersistenceTransportError(
                "Fantasy persistence health request could not be completed"
            ) from exc

        payload = _decode_json_response(response, body)
        if response.status_code != 200:
            raise _rejection_from_payload(response.status_code, payload)
        if payload.get("ok") is not True or payload.get("status") != "ok":
            raise FantasyPersistenceProtocolError(
                "Fantasy persistence health response is not healthy"
            )
        if payload.get("protocol_version") != FANTASY_PERSISTENCE_PROTOCOL_VERSION:
            raise FantasyPersistenceProtocolError(
                "Fantasy persistence health protocol version does not match Python"
            )
        return payload


def _encode_and_validate_command(
    command: Mapping[str, Any],
) -> tuple[bytes, str, str, str]:
    if not isinstance(command, Mapping):
        raise UnsafeFantasyPersistenceTransport("command must be a mapping")
    kind = command.get("kind")
    if kind not in SUPPORTED_COMMAND_KINDS:
        raise UnsafeFantasyPersistenceTransport("command kind is not supported by transport v1")
    if command.get("protocol_version") != FANTASY_PERSISTENCE_PROTOCOL_VERSION:
        raise UnsafeFantasyPersistenceTransport(
            "command protocol version does not match transport v1"
        )

    if kind == LEAGUE_SEASON_UPSERT:
        identity = command.get("identity")
        if not isinstance(identity, Mapping):
            raise UnsafeFantasyPersistenceTransport("registration command identity is required")
        expected_identifier_key = "league_season_id"
        expected_identifier = _required_text(
            identity.get("league_season_id"),
            "command.identity.league_season_id",
        )
    else:
        expected_identifier_key = "sync_run_id"
        expected_identifier = _required_text(
            command.get("sync_run_id"),
            "command.sync_run_id",
        )

    try:
        text = json.dumps(
            dict(command),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise UnsafeFantasyPersistenceTransport(
            "command is not strict JSON serializable"
        ) from exc
    encoded = text.encode("utf-8")
    if not encoded:
        raise UnsafeFantasyPersistenceTransport("command body is empty")
    if len(encoded) > MAX_COMMAND_BODY_BYTES:
        raise UnsafeFantasyPersistenceTransport(
            "command exceeds the 512 KiB Worker request ceiling"
        )
    return encoded, kind, expected_identifier_key, expected_identifier


def _read_limited_response(response: httpx.Response, max_bytes: int) -> bytes:
    declared = response.headers.get("content-length")
    if declared is not None:
        normalized = declared.strip()
        if not normalized.isdigit():
            raise FantasyPersistenceProtocolError(
                "Fantasy persistence response has invalid Content-Length"
            )
        if int(normalized) > max_bytes:
            raise FantasyPersistenceProtocolError(
                "Fantasy persistence response exceeds the configured size limit"
            )

    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > max_bytes:
            raise FantasyPersistenceProtocolError(
                "Fantasy persistence response exceeds the configured size limit"
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_json_response(
    response: httpx.Response,
    body: bytes,
) -> Mapping[str, Any]:
    content_type = response.headers.get("content-type", "")
    if content_type.split(";", 1)[0].strip().lower() != "application/json":
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence response is not application/json"
        )
    try:
        text = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence response is not valid UTF-8"
        ) from exc
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence response is not valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence response must be a JSON object"
        )
    return payload


def _rejection_from_payload(
    status_code: int,
    payload: Mapping[str, Any],
) -> FantasyPersistenceRejected:
    error = payload.get("error")
    if not isinstance(error, Mapping):
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence error response is missing an error object"
        )
    code = _protocol_text(error.get("code"), "error.code")
    message = _protocol_text(error.get("message"), "error.message")
    if payload.get("ok") is not False:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence error response must set ok=false"
        )
    return FantasyPersistenceRejected(status_code, code, message)


def _validate_success_response(
    payload: Mapping[str, Any],
    *,
    expected_kind: str,
    expected_identifier_key: str,
    expected_identifier: str,
) -> None:
    if payload.get("ok") is not True:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence success response must set ok=true"
        )
    if payload.get("protocol_version") != FANTASY_PERSISTENCE_PROTOCOL_VERSION:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence response protocol version does not match Python"
        )
    if payload.get("kind") != expected_kind:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence response command kind does not match request"
        )
    if payload.get(expected_identifier_key) != expected_identifier:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence response command identifier does not match request"
        )
    results = payload.get("results")
    if not isinstance(results, list):
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence success response must contain a results array"
        )


def _validate_read_response(
    payload: Mapping[str, Any],
    *,
    expected_kind: str,
    expected_identifier: str,
) -> None:
    if payload.get("ok") is not True:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence read response must set ok=true"
        )
    if payload.get("protocol_version") != FANTASY_PERSISTENCE_PROTOCOL_VERSION:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence read protocol version does not match Python"
        )
    if payload.get("kind") != expected_kind:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence read kind does not match request"
        )
    if payload.get("requested_id") != expected_identifier:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence read identifier does not match request"
        )
    found = payload.get("found")
    if not isinstance(found, bool):
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence read found must be boolean"
        )
    record = payload.get("record")
    if found and not isinstance(record, Mapping):
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence read found record must be an object"
        )
    if not found and record is not None:
        raise FantasyPersistenceProtocolError(
            "Fantasy persistence missing read must return record=null"
        )


def _validated_endpoint(value: Any) -> str:
    endpoint = _required_text(value, "endpoint")
    parts = urlsplit(endpoint)
    if parts.scheme.lower() != "https":
        raise UnsafeFantasyPersistenceTransport("persistence endpoint must use HTTPS")
    if not parts.hostname:
        raise UnsafeFantasyPersistenceTransport("persistence endpoint must include a host")
    if parts.username is not None or parts.password is not None:
        raise UnsafeFantasyPersistenceTransport(
            "persistence endpoint must not contain URL credentials"
        )
    try:
        parts.port
    except ValueError as exc:
        raise UnsafeFantasyPersistenceTransport(
            "persistence endpoint contains an invalid port"
        ) from exc
    if parts.path != PERSISTENCE_PATH:
        raise UnsafeFantasyPersistenceTransport(
            f"persistence endpoint path must be exactly {PERSISTENCE_PATH}"
        )
    if parts.query or parts.fragment:
        raise UnsafeFantasyPersistenceTransport(
            "persistence endpoint must not contain query parameters or a fragment"
        )
    return endpoint


def _validated_token(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise UnsafeFantasyPersistenceTransport("token must be a non-empty string")
    if value != value.strip() or any(char.isspace() for char in value):
        raise UnsafeFantasyPersistenceTransport(
            "persistence token must not contain whitespace"
        )
    if len(value) < 32:
        raise UnsafeFantasyPersistenceTransport(
            "persistence token must contain at least 32 characters"
        )
    return value


def _validated_read_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise UnsafeFantasyPersistenceTransport(
            f"{label} must be nonblank without surrounding whitespace"
        )
    if len(value) > 256:
        raise UnsafeFantasyPersistenceTransport(f"{label} exceeds 256 characters")
    if any(ord(char) < 32 or ord(char) == 127 or char in {"/", "\\"} for char in value):
        raise UnsafeFantasyPersistenceTransport(f"{label} contains prohibited characters")
    return value


def _origin_url(endpoint: str) -> str:
    parts = urlsplit(endpoint)
    return f"https://{parts.netloc}"


def _health_url(endpoint: str) -> str:
    return f"{_origin_url(endpoint)}{HEALTH_PATH}"


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnsafeFantasyPersistenceTransport(f"{label} must be a non-empty string")
    return value.strip()


def _protocol_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise FantasyPersistenceProtocolError(
            f"Fantasy persistence response {label} must be a non-empty string"
        )
    return value


def _positive_number(value: Any, label: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise UnsafeFantasyPersistenceTransport(f"{label} must be a positive finite number")


def _positive_int(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise UnsafeFantasyPersistenceTransport(f"{label} must be a positive integer")
