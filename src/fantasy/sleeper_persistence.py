from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Protocol

import httpx

from .changes import (
    FantasyChangeEvent,
    FantasySnapshot,
    UnsafeSnapshotTransition,
    derive_fantasy_change_events,
)
from .persistence import LeagueSeasonIdentity, persistence_content_fingerprint
from .persistence_lifecycle import (
    FantasyPersistenceCoordinator,
    FantasyPersistenceLifecycleOutcome,
    FantasyPersistenceStateConflict,
    FantasySyncSession,
)
from .persistence_rehydrate import (
    PersistedFantasySnapshot,
    rehydrate_latest_snapshot_read,
)
from .sleeper_current import (
    MAX_NFL_REGULAR_WEEK,
    SleeperCurrentSnapshotReader,
    SleeperCurrentSnapshotResult,
    SleeperNflState,
    UnsafeSleeperCurrentSnapshot,
    build_current_sleeper_snapshot,
)


SLEEPER_PERSIST_ACCEPTED = "ACCEPTED"
SLEEPER_PERSIST_NO_CHANGE = "NO_CHANGE"
SLEEPER_PERSIST_FAILED = "FAILED"
SLEEPER_PERSIST_EXISTING_FINAL = "EXISTING_FINAL"


class SleeperPersistenceTransport(Protocol):
    def send(self, command: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def read_league_season(self, league_season_id: str) -> Mapping[str, Any]: ...

    def read_sync_run(self, sync_run_id: str) -> Mapping[str, Any]: ...

    def read_latest_snapshot(self, league_season_id: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class SleeperPersistenceRunResult:
    """One single-league Sleeper persistence run outcome."""

    mode: str
    session: FantasySyncSession
    outcome: FantasyPersistenceLifecycleOutcome
    previous_snapshot_id: str | None = None
    current_snapshot_id: str | None = None
    events: tuple[FantasyChangeEvent, ...] = ()
    transaction_rounds: tuple[int, ...] = ()
    current_content_fingerprint: str | None = None
    error_code: str | None = None

    @property
    def accepted_snapshot_id(self) -> str | None:
        return self.outcome.accepted_snapshot_id


def run_sleeper_persistence_sync(
    reader: SleeperCurrentSnapshotReader,
    transport: SleeperPersistenceTransport,
    identity: LeagueSeasonIdentity,
    *,
    league_family_id: str,
    family_display_name: str,
    season_display_name: str,
    registration_created_at_ms: int,
    sync_run_id: str,
    snapshot_id: str,
    current_user_id: str | None,
    nfl_state: SleeperNflState,
    started_at_ms: int,
    observed_at_ms: int,
    accepted_at_ms: int,
    completed_at_ms: int,
    derived_at_ms: int,
    family_metadata: Mapping[str, Any] | None = None,
    season_metadata: Mapping[str, Any] | None = None,
    request_metadata: Mapping[str, Any] | None = None,
) -> SleeperPersistenceRunResult:
    """Run one fail-closed Sleeper fetch/compare/persist lifecycle.

    This function composes already-validated provider, diff, persistence, and
    recovery layers. It never retries persistence writes.

    Provider/data-quality failures after a STARTED sync are recorded as FAILED.
    Persistence/recovery failures, corrupted persisted state, and concurrency
    conflicts propagate untouched so they are never mislabeled as provider
    failures.
    """

    _validate_sleeper_identity(identity)
    coordinator = FantasyPersistenceCoordinator(transport)
    session = coordinator.begin_sync(
        identity,
        league_family_id=league_family_id,
        family_display_name=family_display_name,
        season_display_name=season_display_name,
        registration_created_at_ms=registration_created_at_ms,
        sync_run_id=sync_run_id,
        started_at_ms=started_at_ms,
        family_metadata=family_metadata,
        season_metadata=season_metadata,
        request_metadata=request_metadata,
    )

    if session.is_final:
        return SleeperPersistenceRunResult(
            mode=SLEEPER_PERSIST_EXISTING_FINAL,
            session=session,
            outcome=session.sync,
            error_code=session.sync.error_code,
        )

    previous = _load_previous_snapshot(transport, identity)
    previous_round = _previous_transaction_round(previous)

    try:
        current = build_current_sleeper_snapshot(
            reader,
            identity.platform_league_id,
            snapshot_id=snapshot_id,
            current_user_id=current_user_id,
            nfl_state=nfl_state,
            previous_snapshot=(None if previous is None else previous.snapshot),
            previous_transaction_round=previous_round,
        )
    except httpx.HTTPError as exc:
        return _commit_provider_failure(
            coordinator,
            session,
            previous=previous,
            completed_at_ms=completed_at_ms,
            error_code="SLEEPER_PROVIDER_ERROR",
            error=exc,
        )
    except UnsafeSleeperCurrentSnapshot as exc:
        return _commit_provider_failure(
            coordinator,
            session,
            previous=previous,
            completed_at_ms=completed_at_ms,
            error_code="SLEEPER_STATE_UNSAFE",
            error=exc,
        )
    except ValueError as exc:
        return _commit_provider_failure(
            coordinator,
            session,
            previous=previous,
            completed_at_ms=completed_at_ms,
            error_code="SLEEPER_PROVIDER_DATA_INVALID",
            error=exc,
        )

    current = _merge_prior_transaction_history(previous, current)
    current_fingerprint = persistence_content_fingerprint(current.snapshot)
    if (
        previous is not None
        and current_fingerprint == previous.content_fingerprint
        and current.provider_status == previous.provider_status
    ):
        outcome = coordinator.commit_no_change(
            session,
            previous=previous,
            current_snapshot=current.snapshot,
            completed_at_ms=completed_at_ms,
            provider_status=current.provider_status,
        )
        return SleeperPersistenceRunResult(
            mode=SLEEPER_PERSIST_NO_CHANGE,
            session=session,
            outcome=outcome,
            previous_snapshot_id=previous.snapshot.snapshot_id,
            current_snapshot_id=current.snapshot.snapshot_id,
            events=(),
            transaction_rounds=current.transaction_rounds,
            current_content_fingerprint=current_fingerprint,
        )

    try:
        events = (
            ()
            if previous is None
            else derive_fantasy_change_events(previous.snapshot, current.snapshot)
        )
    except UnsafeSnapshotTransition as exc:
        return _commit_provider_failure(
            coordinator,
            session,
            previous=previous,
            current=current,
            completed_at_ms=completed_at_ms,
            error_code="SNAPSHOT_TRANSITION_UNSAFE",
            error=exc,
        )

    outcome = coordinator.commit_success(
        session,
        snapshot=current.snapshot,
        events=events,
        observed_at_ms=observed_at_ms,
        accepted_at_ms=accepted_at_ms,
        completed_at_ms=completed_at_ms,
        derived_at_ms=derived_at_ms,
        provider_status=current.provider_status,
        previous=previous,
        source_metadata=current.source_metadata,
    )
    return SleeperPersistenceRunResult(
        mode=SLEEPER_PERSIST_ACCEPTED,
        session=session,
        outcome=outcome,
        previous_snapshot_id=(
            None if previous is None else previous.snapshot.snapshot_id
        ),
        current_snapshot_id=current.snapshot.snapshot_id,
        events=events,
        transaction_rounds=current.transaction_rounds,
        current_content_fingerprint=current_fingerprint,
    )


def _load_previous_snapshot(
    transport: SleeperPersistenceTransport,
    identity: LeagueSeasonIdentity,
) -> PersistedFantasySnapshot | None:
    payload = transport.read_latest_snapshot(identity.league_season_id)
    previous = rehydrate_latest_snapshot_read(payload)
    if previous is None:
        return None

    if previous.league_season_id != identity.league_season_id:
        raise FantasyPersistenceStateConflict(
            "Latest persisted snapshot belongs to a different league season"
        )
    actual = (
        previous.snapshot.league.platform,
        previous.snapshot.league.platform_league_id,
        previous.snapshot.league.season,
    )
    expected = (
        identity.platform,
        identity.platform_league_id,
        identity.season,
    )
    if actual != expected:
        raise FantasyPersistenceStateConflict(
            "Latest persisted snapshot league identity does not match sync identity"
        )
    return previous


def _previous_transaction_round(
    previous: PersistedFantasySnapshot | None,
) -> int | None:
    if previous is None:
        return None
    metadata = previous.source_metadata
    if "transaction_round" not in metadata or metadata["transaction_round"] is None:
        if previous.snapshot.league.ownership_ready and not any(
            tx.week is not None for tx in previous.snapshot.transactions
        ):
            raise FantasyPersistenceStateConflict(
                "Persisted transaction_round metadata is required for a quiet ownership-ready snapshot"
            )
        return None
    value = metadata["transaction_round"]
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > MAX_NFL_REGULAR_WEEK
    ):
        raise FantasyPersistenceStateConflict(
            "Persisted transaction_round metadata is invalid"
        )
    return value


def _merge_prior_transaction_history(
    previous: PersistedFantasySnapshot | None,
    current: SleeperCurrentSnapshotResult,
) -> SleeperCurrentSnapshotResult:
    """Preserve prior transaction evidence while applying current provider rows."""

    if previous is None:
        return current

    by_id = {}
    for transaction in previous.snapshot.transactions:
        transaction_id = transaction.platform_transaction_id
        if transaction_id in by_id:
            raise FantasyPersistenceStateConflict(
                "Persisted snapshot contains duplicate transaction IDs"
            )
        by_id[transaction_id] = transaction

    for transaction in current.snapshot.transactions:
        by_id[transaction.platform_transaction_id] = transaction

    merged = tuple(
        sorted(
            by_id.values(),
            key=lambda tx: (
                tx.week if tx.week is not None else MAX_NFL_REGULAR_WEEK + 1,
                tx.created_at_ms if tx.created_at_ms is not None else -1,
                tx.platform_transaction_id,
            ),
        )
    )
    if merged == current.snapshot.transactions:
        return current

    return replace(
        current,
        snapshot=FantasySnapshot(
            current.snapshot.snapshot_id,
            current.snapshot.league,
            merged,
        ),
    )


def _commit_provider_failure(
    coordinator: FantasyPersistenceCoordinator,
    session: FantasySyncSession,
    *,
    completed_at_ms: int,
    error_code: str,
    error: Exception,
    previous: PersistedFantasySnapshot | None = None,
    current: SleeperCurrentSnapshotResult | None = None,
) -> SleeperPersistenceRunResult:
    outcome = coordinator.commit_failure(
        session,
        completed_at_ms=completed_at_ms,
        error_code=error_code,
        error_summary=type(error).__name__,
    )
    return SleeperPersistenceRunResult(
        mode=SLEEPER_PERSIST_FAILED,
        session=session,
        outcome=outcome,
        previous_snapshot_id=(
            None if previous is None else previous.snapshot.snapshot_id
        ),
        current_snapshot_id=(
            None if current is None else current.snapshot.snapshot_id
        ),
        transaction_rounds=(
            () if current is None else current.transaction_rounds
        ),
        error_code=error_code,
    )


def _validate_sleeper_identity(identity: LeagueSeasonIdentity) -> None:
    if identity.platform != "SLEEPER":
        raise FantasyPersistenceStateConflict(
            "Sleeper persistence runner requires platform=SLEEPER"
        )
