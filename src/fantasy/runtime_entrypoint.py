from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .runtime_handshake import (
    FantasyRuntimeDeploymentHandshakeResult,
    run_fantasy_runtime_deployment_handshake,
)
from .scheduled_sync import (
    SleeperScheduledLeague,
    SleeperScheduledSyncPlan,
    SleeperScheduledSyncRunResult,
    build_sleeper_scheduled_sync_plan,
    run_sleeper_scheduled_sync_plan,
)
from .sleeper_multi_persistence import SleeperMultiPersistenceReader
from .sleeper_persistence import SleeperPersistenceTransport


class FantasyScheduledRuntimeClient(SleeperPersistenceTransport, Protocol):
    """Persistence client surface required after the read-only runtime gate.

    The same client is used for the #78 handshake and, only after readiness is
    proven, for the existing persistence lifecycle.
    """

    def health(self) -> Mapping[str, Any]: ...


class FantasyScheduledRuntimeGateError(RuntimeError):
    """Raised if a runtime gate result violates the READY invariant."""


@dataclass(frozen=True)
class FantasyScheduledRuntimeResult:
    """Sanitized gate proof plus the scheduled persistence result."""

    handshake: FantasyRuntimeDeploymentHandshakeResult
    scheduled: SleeperScheduledSyncRunResult

    def __post_init__(self) -> None:
        if self.handshake.ready is not True:
            raise ValueError("scheduled runtime result requires a ready handshake")

    @property
    def ready(self) -> bool:
        return self.handshake.ready

    @property
    def batch_id(self) -> str:
        return self.scheduled.batch_id

    @property
    def accepted_count(self) -> int:
        return self.scheduled.accepted_count

    @property
    def no_change_count(self) -> int:
        return self.scheduled.no_change_count

    @property
    def provider_failed_count(self) -> int:
        return self.scheduled.provider_failed_count

    @property
    def persistence_error_count(self) -> int:
        return self.scheduled.persistence_error_count

    @property
    def recovery_required_count(self) -> int:
        return self.scheduled.recovery_required_count


def build_handshake_gated_scheduled_plan(
    leagues: Sequence[SleeperScheduledLeague],
    *,
    scheduled_at_ms: int,
    schedule_name: str = "fantasy-hq-sleeper",
) -> SleeperScheduledSyncPlan:
    """Validate and freeze scheduled work before any runtime network I/O."""

    return build_sleeper_scheduled_sync_plan(
        leagues,
        scheduled_at_ms=scheduled_at_ms,
        schedule_name=schedule_name,
    )


def run_handshake_gated_scheduled_sleeper_sync(
    reader: SleeperMultiPersistenceReader,
    client: FantasyScheduledRuntimeClient,
    leagues: Sequence[SleeperScheduledLeague],
    *,
    scheduled_at_ms: int,
    current_user_id: str | None,
    schedule_name: str = "fantasy-hq-sleeper",
) -> FantasyScheduledRuntimeResult:
    """Run scheduled Sleeper persistence only after the read-only runtime gate.

    Ordering is intentional and security-sensitive:

        validate/freeze plan
        -> #78 read-only deployment handshake
        -> execute the frozen #76 plan
        -> #75 multi-league orchestration
        -> #74 persistence lifecycle

    If plan validation or the handshake fails, the Sleeper reader is never
    invoked and no persistence write path is reached.
    """

    plan = build_handshake_gated_scheduled_plan(
        leagues,
        scheduled_at_ms=scheduled_at_ms,
        schedule_name=schedule_name,
    )

    handshake = run_fantasy_runtime_deployment_handshake(client)
    if handshake.ready is not True:
        raise FantasyScheduledRuntimeGateError(
            "Fantasy HQ runtime handshake did not reach READY"
        )

    scheduled = run_sleeper_scheduled_sync_plan(
        reader,
        client,
        plan,
        current_user_id=current_user_id,
    )
    return FantasyScheduledRuntimeResult(
        handshake=handshake,
        scheduled=scheduled,
    )
