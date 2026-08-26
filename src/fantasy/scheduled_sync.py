from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Mapping, Sequence

from .persistence import LeagueSeasonIdentity, canonical_json
from .persistence_protocol import JAVASCRIPT_MAX_SAFE_INTEGER
from .sleeper_multi_persistence import (
    MultiSleeperPersistenceRunResult,
    SleeperMultiPersistenceReader,
    SleeperPersistenceLeagueSpec,
    SleeperPersistenceTransport,
    run_multi_sleeper_persistence_sync,
)


SLEEPER_SCHEDULE_VERSION = "SLEEPER_SCHEDULE_V1"
SLEEPER_SCHEDULE_TRIGGER = "SCHEDULED"
_RESERVED_REQUEST_METADATA_KEYS = frozenset(
    {
        "trigger",
        "schedule_version",
        "schedule_name",
        "scheduled_at_ms",
        "batch_id",
    }
)


@dataclass(frozen=True)
class SleeperScheduledLeague:
    """Stable registration/configuration for one scheduled Sleeper league."""

    identity: LeagueSeasonIdentity
    league_family_id: str
    family_display_name: str
    season_display_name: str
    registration_created_at_ms: int
    family_metadata: Mapping[str, Any] | None = None
    season_metadata: Mapping[str, Any] | None = None
    request_metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.identity, LeagueSeasonIdentity):
            raise TypeError("identity must be a LeagueSeasonIdentity")
        if self.identity.platform != "SLEEPER":
            raise ValueError("scheduled Sleeper league requires platform=SLEEPER")

        for field_name in (
            "league_family_id",
            "family_display_name",
            "season_display_name",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(getattr(self, field_name), field_name),
            )

        object.__setattr__(
            self,
            "registration_created_at_ms",
            _javascript_safe_nonnegative_int(
                self.registration_created_at_ms,
                "registration_created_at_ms",
            ),
        )

        for field_name in ("family_metadata", "season_metadata", "request_metadata"):
            object.__setattr__(
                self,
                field_name,
                _validated_metadata(getattr(self, field_name), field_name),
            )

        request_metadata = self.request_metadata or {}
        reserved = sorted(_RESERVED_REQUEST_METADATA_KEYS.intersection(request_metadata))
        if reserved:
            raise ValueError(
                "scheduled request_metadata cannot override reserved keys: "
                + ", ".join(reserved)
            )


@dataclass(frozen=True)
class SleeperScheduledSyncPlan:
    """Deterministic persistence inputs for one scheduler slot."""

    schedule_name: str
    scheduled_at_ms: int
    batch_id: str
    specs: tuple[SleeperPersistenceLeagueSpec, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "schedule_name",
            _required_text(self.schedule_name, "schedule_name"),
        )
        object.__setattr__(
            self,
            "scheduled_at_ms",
            _javascript_safe_nonnegative_int(
                self.scheduled_at_ms,
                "scheduled_at_ms",
            ),
        )
        object.__setattr__(self, "batch_id", _required_text(self.batch_id, "batch_id"))
        if not self.specs:
            raise ValueError("scheduled sync plan requires at least one league spec")

    @property
    def league_count(self) -> int:
        return len(self.specs)

    @property
    def league_ids(self) -> tuple[str, ...]:
        return tuple(spec.identity.platform_league_id for spec in self.specs)

    @property
    def sync_run_ids(self) -> tuple[str, ...]:
        return tuple(spec.sync_run_id for spec in self.specs)

    @property
    def snapshot_ids(self) -> tuple[str, ...]:
        return tuple(spec.snapshot_id for spec in self.specs)


@dataclass(frozen=True)
class SleeperScheduledSyncRunResult:
    """One scheduler-slot plan plus its multi-league persistence outcome."""

    plan: SleeperScheduledSyncPlan
    result: MultiSleeperPersistenceRunResult

    def __post_init__(self) -> None:
        if self.plan.league_ids != self.result.league_ids:
            raise ValueError("scheduled sync result order does not match its plan")

    @property
    def batch_id(self) -> str:
        return self.plan.batch_id

    @property
    def accepted_count(self) -> int:
        return self.result.accepted_count

    @property
    def no_change_count(self) -> int:
        return self.result.no_change_count

    @property
    def provider_failed_count(self) -> int:
        return self.result.provider_failed_count

    @property
    def persistence_error_count(self) -> int:
        return self.result.persistence_error_count

    @property
    def recovery_required_count(self) -> int:
        return self.result.recovery_required_count


def build_sleeper_scheduled_sync_plan(
    leagues: Sequence[SleeperScheduledLeague],
    *,
    scheduled_at_ms: int,
    schedule_name: str = "fantasy-hq-sleeper",
) -> SleeperScheduledSyncPlan:
    """Build retry-stable per-league IDs and metadata for one scheduler slot.

    The scheduled timestamp is the logical run timestamp for every persistence
    lifecycle field. That is deliberate: duplicate delivery of one scheduler
    slot produces byte-stable IDs and lifecycle timestamps instead of creating a
    second logical sync with a later wall-clock timestamp.
    """

    rows = _validated_scheduled_leagues(leagues)
    scheduled_at_ms = _javascript_safe_nonnegative_int(
        scheduled_at_ms,
        "scheduled_at_ms",
    )
    schedule_name = _required_text(schedule_name, "schedule_name")

    batch_id = _scheduled_identifier(
        "batch",
        scheduled_at_ms=scheduled_at_ms,
        identity=None,
    )

    specs = tuple(
        SleeperPersistenceLeagueSpec(
            identity=row.identity,
            league_family_id=row.league_family_id,
            family_display_name=row.family_display_name,
            season_display_name=row.season_display_name,
            registration_created_at_ms=row.registration_created_at_ms,
            sync_run_id=_scheduled_identifier(
                "sync",
                scheduled_at_ms=scheduled_at_ms,
                identity=row.identity,
            ),
            snapshot_id=_scheduled_identifier(
                "snapshot",
                scheduled_at_ms=scheduled_at_ms,
                identity=row.identity,
            ),
            started_at_ms=scheduled_at_ms,
            observed_at_ms=scheduled_at_ms,
            accepted_at_ms=scheduled_at_ms,
            completed_at_ms=scheduled_at_ms,
            derived_at_ms=scheduled_at_ms,
            family_metadata=row.family_metadata,
            season_metadata=row.season_metadata,
            request_metadata={
                **dict(row.request_metadata or {}),
                "trigger": SLEEPER_SCHEDULE_TRIGGER,
                "schedule_version": SLEEPER_SCHEDULE_VERSION,
                "schedule_name": schedule_name,
                "scheduled_at_ms": scheduled_at_ms,
                "batch_id": batch_id,
            },
        )
        for row in rows
    )

    return SleeperScheduledSyncPlan(
        schedule_name=schedule_name,
        scheduled_at_ms=scheduled_at_ms,
        batch_id=batch_id,
        specs=specs,
    )


def run_scheduled_sleeper_persistence_sync(
    reader: SleeperMultiPersistenceReader,
    transport: SleeperPersistenceTransport,
    leagues: Sequence[SleeperScheduledLeague],
    *,
    scheduled_at_ms: int,
    current_user_id: str | None,
    schedule_name: str = "fantasy-hq-sleeper",
) -> SleeperScheduledSyncRunResult:
    """Execute one scheduler slot through the existing multi-league runner."""

    plan = build_sleeper_scheduled_sync_plan(
        leagues,
        scheduled_at_ms=scheduled_at_ms,
        schedule_name=schedule_name,
    )
    result = run_multi_sleeper_persistence_sync(
        reader,
        transport,
        plan.specs,
        current_user_id=current_user_id,
    )
    return SleeperScheduledSyncRunResult(plan=plan, result=result)


def _validated_scheduled_leagues(
    leagues: Sequence[SleeperScheduledLeague],
) -> tuple[SleeperScheduledLeague, ...]:
    rows = tuple(leagues)
    if not rows:
        raise ValueError("At least one scheduled Sleeper league is required")
    if any(not isinstance(row, SleeperScheduledLeague) for row in rows):
        raise TypeError("leagues must contain SleeperScheduledLeague values")

    seasons = {row.identity.season for row in rows}
    if len(seasons) != 1:
        raise ValueError("scheduled Sleeper sync requires one shared season")

    _require_unique(
        (row.identity.league_season_id for row in rows),
        "league_season_id",
    )
    _require_unique(
        (row.identity.platform_league_id for row in rows),
        "platform_league_id",
    )
    return rows


def _scheduled_identifier(
    kind: str,
    *,
    scheduled_at_ms: int,
    identity: LeagueSeasonIdentity | None,
) -> str:
    payload: dict[str, Any] = {
        "version": SLEEPER_SCHEDULE_VERSION,
        "kind": _required_text(kind, "kind"),
        "scheduled_at_ms": scheduled_at_ms,
    }
    if identity is not None:
        payload.update(
            {
                "league_season_id": identity.league_season_id,
                "platform": identity.platform,
                "platform_league_id": identity.platform_league_id,
                "season": identity.season,
            }
        )
    digest = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
    return f"fhq-sleeper-{kind}-v1-{digest}"


def _require_unique(values: Any, label: str) -> None:
    materialized = tuple(values)
    if len(materialized) != len(set(materialized)):
        raise ValueError(f"scheduled Sleeper {label} values must be unique")


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


def _javascript_safe_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    if value > JAVASCRIPT_MAX_SAFE_INTEGER:
        raise ValueError(f"{label} exceeds JavaScript safe integer range")
    return value
