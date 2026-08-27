from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

import httpx

from .persistence_http import (
    READ_SYNC_RUN,
    FantasyPersistenceClientConfig,
    FantasyPersistenceHttpClient,
)
from .persistence_protocol import FANTASY_PERSISTENCE_PROTOCOL_VERSION


FANTASY_RUNTIME_HANDSHAKE_VERSION = 1
FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID = (
    "propwar-runtime-handshake-v1-read-only-probe"
)


class FantasyRuntimeDeploymentHandshakeError(RuntimeError):
    """Raised when the runtime/Worker read-only deployment handshake is unsafe."""


class FantasyRuntimeHandshakeClient(Protocol):
    """Read-only transport surface required before live persistence is allowed."""

    def health(self) -> Mapping[str, Any]: ...

    def read_sync_run(self, sync_run_id: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class FantasyRuntimeDeploymentHandshakeResult:
    """Sanitized proof that Python can reach the Worker and authenticated D1 reads."""

    handshake_version: int
    protocol_version: int
    health_ready: bool
    authenticated_read_ready: bool
    probe_absent: bool
    write_enabled: bool = False

    def __post_init__(self) -> None:
        if self.handshake_version != FANTASY_RUNTIME_HANDSHAKE_VERSION:
            raise ValueError("runtime handshake version invariant changed")
        if self.protocol_version != FANTASY_PERSISTENCE_PROTOCOL_VERSION:
            raise ValueError("runtime handshake protocol version invariant changed")
        if self.health_ready is not True:
            raise ValueError("runtime handshake requires a healthy Worker")
        if self.authenticated_read_ready is not True:
            raise ValueError("runtime handshake requires an authenticated D1 read")
        if self.probe_absent is not True:
            raise ValueError("runtime handshake probe must remain absent")
        if self.write_enabled is not False:
            raise ValueError("runtime deployment handshake must remain read-only")

    @property
    def ready(self) -> bool:
        return (
            self.health_ready
            and self.authenticated_read_ready
            and self.probe_absent
            and not self.write_enabled
        )

    def safe_summary(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "handshake_version": self.handshake_version,
            "protocol_version": self.protocol_version,
            "health_ready": self.health_ready,
            "authenticated_read_ready": self.authenticated_read_ready,
            "probe_absent": self.probe_absent,
            "write_enabled": self.write_enabled,
        }


def run_fantasy_runtime_deployment_handshake(
    client: FantasyRuntimeHandshakeClient,
) -> FantasyRuntimeDeploymentHandshakeResult:
    """Prove Worker health + authenticated D1 read readiness without any write.

    The reserved probe ID must not exist. Its absence proves the authenticated
    read route and migrated D1 schema are reachable while also detecting any
    accidental prior use of the reserved handshake identity.
    """

    if not callable(getattr(client, "health", None)):
        raise TypeError("runtime handshake client must provide health()")
    if not callable(getattr(client, "read_sync_run", None)):
        raise TypeError("runtime handshake client must provide read_sync_run()")

    health = client.health()
    _validate_health_payload(health)

    probe = client.read_sync_run(FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID)
    _validate_probe_payload(probe)

    if probe["found"]:
        raise FantasyRuntimeDeploymentHandshakeError(
            "reserved runtime handshake probe unexpectedly exists"
        )

    return FantasyRuntimeDeploymentHandshakeResult(
        handshake_version=FANTASY_RUNTIME_HANDSHAKE_VERSION,
        protocol_version=FANTASY_PERSISTENCE_PROTOCOL_VERSION,
        health_ready=True,
        authenticated_read_ready=True,
        probe_absent=True,
        write_enabled=False,
    )


def run_fantasy_runtime_deployment_handshake_from_env(
    *,
    transport: httpx.BaseTransport | None = None,
) -> FantasyRuntimeDeploymentHandshakeResult:
    """Run the read-only deployment handshake using runtime environment secrets."""

    config = FantasyPersistenceClientConfig.from_env()
    with FantasyPersistenceHttpClient(config, transport=transport) as client:
        return run_fantasy_runtime_deployment_handshake(client)


def _validate_health_payload(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime health result must be a mapping"
        )
    if payload.get("ok") is not True or payload.get("status") != "ok":
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime health result is not healthy"
        )
    if payload.get("protocol_version") != FANTASY_PERSISTENCE_PROTOCOL_VERSION:
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime health protocol version does not match Python"
        )


def _validate_probe_payload(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime authenticated-read result must be a mapping"
        )
    if payload.get("ok") is not True:
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime authenticated-read result is not successful"
        )
    if payload.get("protocol_version") != FANTASY_PERSISTENCE_PROTOCOL_VERSION:
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime authenticated-read protocol version does not match Python"
        )
    if payload.get("kind") != READ_SYNC_RUN:
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime authenticated-read kind does not match probe"
        )
    if payload.get("requested_id") != FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID:
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime authenticated-read identifier does not match probe"
        )
    if not isinstance(payload.get("found"), bool):
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime authenticated-read found must be boolean"
        )
    if payload["found"] and not isinstance(payload.get("record"), Mapping):
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime authenticated-read found record must be an object"
        )
    if not payload["found"] and payload.get("record") is not None:
        raise FantasyRuntimeDeploymentHandshakeError(
            "runtime authenticated-read missing probe must return record=null"
        )
