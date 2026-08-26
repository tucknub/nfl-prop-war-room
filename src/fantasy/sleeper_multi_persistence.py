from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .persistence import LeagueSeasonIdentity, canonical_json
from .persistence_http import (
    FantasyPersistenceProtocolError,
    FantasyPersistenceRejected,
    FantasyPersistenceTransportError,
    UnsafeFantasyPersistenceTransport,
)
from .persistence_lifecycle import (
    FantasyPersistenceLifecycleError,
    FantasyPersistenceOutcomeUnknown,
)
from .persistence_rehydrate import UnsafePersistedFantasySnapshot
from .sleeper_current import (
    SleeperNflState,
    UnsafeSleeperCurrentSnapshot,
)
from .sleeper_persistence import (
    SLEEPER_PERSIST_ACCEPTED,
    SLEEPER_PERSIST_FAILED,
    SLEEPER_PERSIST_NO_CHANGE,
    SleeperPersistenceRunResult,
    SleeperPersistenceTransport,
    run_sleeper_persistence_sync,
)


SLEEPER_MULTI_PERSIST_ERROR = "PERSISTENCE_ERROR"


class SleeperMultiPersistenceReader(Protocol):
    """Read-only Sleeper surface required by the multi-league runner."""

    def fetch_nfl_state(self) -> SleeperNflState: ...

    def fetch_normalized_league(
        self,
        league_id: str,
        *,
        current_user_id: str | None = None,
    ) -> Any: ...

    def fetch_transactions(
        self,
        league_id: str,
        week: int,
    ) -> tuple[Any, ...]: ...


@dataclass(frozen=True)
class SleeperPersistenceLeagueSpec:
    """Caller-owned deterministic inputs for one league persistence run."""

    identity: LeagueSeasonIdentity
    league_family_id: str
    family_display_name: str
    season_display_name: str
    registration_created_at_ms: int
    sync_run_id: str
    snapshot_id: str
    started_at_ms: int
    observed_at_ms: int
    accepted_at_ms: int
    completed_at_ms: int
    derived_at_ms: int
    family_metadata: Mapping[str, Any] | None = None
    season_metadata: Mapping[str, Any] | None = None
    request_metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.identity.platform != "SLEEPER":
            raise ValueError("Sleeper persistence league spec requires platform=SLEEPER")

        for field_name in (
            "league_family_id",
            "family_display_name",
            "season_display_name",
            "sync_run_id",
            "snapshot_id",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )

        timestamps = {
            "registration_created_at_ms": _nonnegative_int(
                self.registration_created_at_ms,
                "registration_created_at_ms",
            ),
            "started_at_ms": _nonnegative_int(self.started_at_ms, "started_at_ms"),
            "observed_at_ms": _nonnegative_int(self.observed_at_ms, "observed_at_ms"),
            "accepted_at_ms": _nonnegative_int(self.accepted_at_ms, "accepted_at_ms"),
            "completed_at_ms": _nonnegative_int(self.completed_at_ms, "completed_at_ms"),
            "derived_at_ms": _nonnegative_int(self.derived_at_ms, "derived_at_ms"),
        }
        for field_name, value in timestamps.items():
            object.__setattr__(self, field_name, value)

        if self.accepted_at_ms < self.observed_at_ms:
            raise ValueError("accepted_at_ms cannot precede observed_at_ms")
        if self.derived_at_ms < self.observed_at_ms:
            raise ValueError("derived_at_ms cannot precede observed_at_ms")
        if self.completed_at_ms < self.accepted_at_ms:
            raise ValueError("completed_at_ms cannot precede accepted_at_ms")
        if self.completed_at_ms < self.derived_at_ms:
            raise ValueError("completed_at_ms cannot precede derived_at_ms")

        for field_name in (
            "family_metadata",
            "season_metadata",
            "request_metadata",
        ):
            object.__setattr__(
                self,
                field_name,
                _validated_metadata(getattr(self, field_name), field_name),
            )


@dataclass(frozen=True)
class SleeperMultiPersistenceLeagueResult:
    """One league outcome without retaining private exception messages."""

    spec: SleeperPersistenceLeagueSpec
    result: SleeperPersistenceRunResult | None = None
    error_type: str | None = None
    error_stage: str | None = None
    recovery_required: bool = False

    def __post_init__(self) -> None:
        if (self.result is None) == (self.error_type is None):
            raise ValueError(
                "multi-league outcome requires exactly one of result or error_type"
            )

    @property
    def league_season_id(self) -> str:
        return self.spec.identity.league_season_id

    @property
    def platform_league_id(self) -> str:
        return self.spec.identity.platform_league_id

    @property
    def mode(self) -> str:
        return (
            SLEEPER_MULTI_PERSIST_ERROR
            if self.result is None
            else self.result.mode
        )

    @property
    def accepted_snapshot_id(self) -> str | None:
        return None if self.result is None else self.result.accepted_snapshot_id


@dataclass(frozen=True)
class MultiSleeperPersistenceRunResult:
    """Ordered results for one shared-NFL-state multi-league sync batch."""

    nfl_state: SleeperNflState
    leagues: tuple[SleeperMultiPersistenceLeagueResult, ...]

    @property
    def league_count(self) -> int:
        return len(self.leagues)

    @property
    def league_ids(self) -> tuple[str, ...]:
        return tuple(result.platform_league_id for result in self.leagues)

    @property
    def accepted_count(self) -> int:
        return sum(result.mode == SLEEPER_PERSIST_ACCEPTED for result in self.leagues)

    @property
    def no_change_count(self) -> int:
        return sum(result.mode == SLEEPER_PERSIST_NO_CHANGE for result in self.leagues)

    @property
    def provider_failed_count(self) -> int:
        return sum(result.mode == SLEEPER_PERSIST_FAILED for result in self.leagues)

    @property
    def persistence_error_count(self) -> int:
        return sum(result.mode == SLEEPER_MULTI_PERSIST_ERROR for result in self.leagues)

    @property
    def recovery_required_count(self) -> int:
        return sum(result.recovery_required for result in self.leagues)

    @property
    def has_persistence_errors(self) -> bool:
        return self.persistence_error_count > 0


def run_multi_sleeper_persistence_sync(
    reader: SleeperMultiPersistenceReader,
    transport: SleeperPersistenceTransport,
    league_specs: Sequence[SleeperPersistenceLeagueSpec],
    *,
    current_user_id: str | None,
) -> MultiSleeperPersistenceRunResult:
    """Run current Sleeper persistence for multiple leagues with one NFL-state read.

    All specs are validated before provider or persistence I/O. The shared
    /state/nfl payload is also validated against the requested season before any
    league lifecycle begins.

    Provider/data-quality failures are handled by the single-league runner and
    become normal FAILED results. Known league-specific persistence/recovery
    failures are isolated so later leagues can still run. Unsafe transport
    configuration, protocol-version failures, authentication failures, and
    unexpected programming errors remain batch-fatal.
    """

    specs = _validated_specs(league_specs)
    nfl_state = reader.fetch_nfl_state()
    _validate_shared_nfl_state(nfl_state, specs[0].identity.season)

    outcomes: list[SleeperMultiPersistenceLeagueResult] = []
    for spec in specs:
        try:
            result = run_sleeper_persistence_sync(
                reader,
                transport,
                spec.identity,
                league_family_id=spec.league_family_id,
                family_display_name=spec.family_display_name,
                season_display_name=spec.season_display_name,
                registration_created_at_ms=spec.registration_created_at_ms,
                sync_run_id=spec.sync_run_id,
                snapshot_id=spec.snapshot_id,
                current_user_id=current_user_id,
                nfl_state=nfl_state,
                started_at_ms=spec.started_at_ms,
                observed_at_ms=spec.observed_at_ms,
                accepted_at_ms=spec.accepted_at_ms,
                completed_at_ms=spec.completed_at_ms,
                derived_at_ms=spec.derived_at_ms,
                family_metadata=spec.family_metadata,
                season_metadata=spec.season_metadata,
                request_metadata=spec.request_metadata,
            )
        except _BATCH_FATAL_PERSISTENCE_ERRORS:
            raise
        except FantasyPersistenceRejected as exc:
            if exc.status_code in {401, 403}:
                raise
            outcomes.append(_isolated_error(spec, exc))
        except _ISOLATED_PERSISTENCE_ERRORS as exc:
            outcomes.append(_isolated_error(spec, exc))
        else:
            outcomes.append(
                SleeperMultiPersistenceLeagueResult(
                    spec=spec,
                    result=result,
                )
            )

    return MultiSleeperPersistenceRunResult(
        nfl_state=nfl_state,
        leagues=tuple(outcomes),
    )


_ISOLATED_PERSISTENCE_ERRORS = (
    FantasyPersistenceLifecycleError,
    UnsafePersistedFantasySnapshot,
    FantasyPersistenceTransportError,
)

_BATCH_FATAL_PERSISTENCE_ERRORS = (
    UnsafeFantasyPersistenceTransport,
    FantasyPersistenceProtocolError,
)


def _isolated_error(
    spec: SleeperPersistenceLeagueSpec,
    error: Exception,
) -> SleeperMultiPersistenceLeagueResult:
    return SleeperMultiPersistenceLeagueResult(
        spec=spec,
        error_type=type(error).__name__,
        error_stage=(
            error.stage
            if isinstance(error, FantasyPersistenceOutcomeUnknown)
            else None
        ),
        recovery_required=isinstance(error, FantasyPersistenceOutcomeUnknown),
    )


def _validated_specs(
    league_specs: Sequence[SleeperPersistenceLeagueSpec],
) -> tuple[SleeperPersistenceLeagueSpec, ...]:
    specs = tuple(league_specs)
    if not specs:
        raise ValueError("At least one Sleeper persistence league spec is required")
    if any(not isinstance(spec, SleeperPersistenceLeagueSpec) for spec in specs):
        raise TypeError("league_specs must contain SleeperPersistenceLeagueSpec values")

    seasons = {spec.identity.season for spec in specs}
    if len(seasons) != 1:
        raise ValueError(
            "Multi-league Sleeper persistence requires one shared current season"
        )

    _require_unique(
        (spec.identity.league_season_id for spec in specs),
        "league_season_id",
    )
    _require_unique(
        (spec.identity.platform_league_id for spec in specs),
        "platform_league_id",
    )
    _require_unique((spec.sync_run_id for spec in specs), "sync_run_id")
    _require_unique((spec.snapshot_id for spec in specs), "snapshot_id")
    return specs


def _validate_shared_nfl_state(nfl_state: SleeperNflState, season: str) -> None:
    if not isinstance(nfl_state, SleeperNflState):
        raise UnsafeSleeperCurrentSnapshot(
            "Sleeper multi-league runner requires typed NFL state"
        )
    if season not in {nfl_state.season, nfl_state.league_season}:
        raise UnsafeSleeperCurrentSnapshot(
            "Shared Sleeper NFL state does not match requested league season"
        )


def _require_unique(values: Sequence[str] | Any, label: str) -> None:
    materialized = tuple(values)
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"Sleeper persistence {label} values must be unique")


def _validated_metadata(
    value: Mapping[str, Any] | None,
    label: str,
) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping or None")
    normalized = dict(value)
    canonical_json(normalized)
    return normalized


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a nonblank canonical string")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value
