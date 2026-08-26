from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .changes import FantasyChangeEvent, FantasySnapshot
from .league_registration_protocol import build_league_season_upsert_command
from .persistence import LeagueSeasonIdentity
from .persistence_http import (
    FantasyPersistenceProtocolError,
    FantasyPersistenceRejected,
    FantasyPersistenceTransportError,
)
from .persistence_protocol import (
    build_failed_sync_command,
    build_successful_sync_command,
    build_sync_start_command,
)


PERSISTENCE_REGISTERED = "REGISTERED"
PERSISTENCE_STARTED = "STARTED"
PERSISTENCE_COMPLETED = "COMPLETED"
PERSISTENCE_FAILED = "FAILED"

PERSISTENCE_SOURCE_WRITE = "WRITE"
PERSISTENCE_SOURCE_RECOVERY = "RECOVERY"
PERSISTENCE_SOURCE_EXISTING = "EXISTING"

_STAGE_REGISTRATION = "REGISTRATION"
_STAGE_SYNC_START = "SYNC_START"
_STAGE_SYNC_SUCCESS = "SYNC_SUCCESS"
_STAGE_SYNC_FAILED = "SYNC_FAILED"
_FINAL_SYNC_STATES = frozenset({PERSISTENCE_COMPLETED, PERSISTENCE_FAILED})
_KNOWN_SYNC_STATES = frozenset(
    {PERSISTENCE_STARTED, PERSISTENCE_COMPLETED, PERSISTENCE_FAILED}
)


class FantasyPersistenceLifecycleError(RuntimeError):
    """Base error for persistence lifecycle sequencing/recovery failures."""


class FantasyPersistenceStateConflict(FantasyPersistenceLifecycleError):
    """Raised when persisted state contradicts the requested lifecycle operation."""


class FantasyPersistenceOutcomeUnknown(FantasyPersistenceLifecycleError):
    """Raised when an ambiguous write cannot be proven committed by recovery reads."""

    def __init__(
        self,
        *,
        stage: str,
        identifier: str,
        write_error_name: str,
        observed_state: str | None = None,
        recovery_error_name: str | None = None,
    ) -> None:
        self.stage = stage
        self.identifier = identifier
        self.write_error_name = write_error_name
        self.observed_state = observed_state
        self.recovery_error_name = recovery_error_name
        super().__init__(
            f"Fantasy persistence outcome remains unknown after {stage}"
        )


class FantasyPersistenceTransport(Protocol):
    """Narrow transport contract consumed by the lifecycle coordinator."""

    def send(self, command: Mapping[str, Any]) -> Mapping[str, Any]: ...

    def read_league_season(self, league_season_id: str) -> Mapping[str, Any]: ...

    def read_sync_run(self, sync_run_id: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class FantasyPersistenceLifecycleOutcome:
    """One authoritative lifecycle observation without retaining raw payloads."""

    stage: str
    state: str
    source: str
    identifier: str
    accepted_snapshot_id: str | None = None
    error_code: str | None = None

    @property
    def is_final(self) -> bool:
        return self.state in _FINAL_SYNC_STATES


@dataclass(frozen=True)
class FantasySyncSession:
    """Registration + sync-start state returned before provider/domain work proceeds."""

    identity: LeagueSeasonIdentity
    sync_run_id: str
    registration: FantasyPersistenceLifecycleOutcome
    sync: FantasyPersistenceLifecycleOutcome

    @property
    def can_commit(self) -> bool:
        return self.sync.state == PERSISTENCE_STARTED

    @property
    def is_final(self) -> bool:
        return self.sync.is_final


class FantasyPersistenceCoordinator:
    """Fail-closed coordinator for Fantasy HQ persistence lifecycle v1.

    This layer deliberately does not fetch provider data, derive fantasy events,
    generate identifiers, or retry writes. It only guarantees the ordering and
    recovery semantics around already-validated domain state:

        ensure registration -> start sync -> commit success or failure

    A transport/protocol/5xx failure after a write is treated as ambiguous.
    Recovery performs an authoritative read. If that read proves the expected
    committed state, the operation succeeds with source=RECOVERY. Otherwise the
    coordinator raises FantasyPersistenceOutcomeUnknown and never retries the
    write automatically.
    """

    def __init__(self, transport: FantasyPersistenceTransport) -> None:
        self.transport = transport

    def ensure_league_season(
        self,
        identity: LeagueSeasonIdentity,
        *,
        league_family_id: str,
        family_display_name: str,
        season_display_name: str,
        created_at_ms: int,
        family_metadata: Mapping[str, Any] | None = None,
        season_metadata: Mapping[str, Any] | None = None,
    ) -> FantasyPersistenceLifecycleOutcome:
        """Ensure immutable league-season identity exists before any sync starts.

        Existing registration is treated as the prerequisite being satisfied and
        is not rewritten merely to refresh labels/metadata. Metadata refresh can
        remain an explicit administrative operation rather than an implicit sync
        side effect.
        """

        command = build_league_season_upsert_command(
            identity,
            league_family_id=league_family_id,
            family_display_name=family_display_name,
            season_display_name=season_display_name,
            created_at_ms=created_at_ms,
            family_metadata=family_metadata,
            season_metadata=season_metadata,
        )

        existing = self.transport.read_league_season(identity.league_season_id)
        if _found(existing):
            _validate_league_registration_record(
                _record(existing),
                identity=identity,
                league_family_id=command["league_family_id"],
            )
            return FantasyPersistenceLifecycleOutcome(
                stage=_STAGE_REGISTRATION,
                state=PERSISTENCE_REGISTERED,
                source=PERSISTENCE_SOURCE_EXISTING,
                identifier=identity.league_season_id,
            )

        try:
            self.transport.send(command)
        except Exception as exc:
            if not _is_ambiguous_write_error(exc):
                raise
            return self._recover_registration(
                identity,
                league_family_id=command["league_family_id"],
                write_error=exc,
            )

        return FantasyPersistenceLifecycleOutcome(
            stage=_STAGE_REGISTRATION,
            state=PERSISTENCE_REGISTERED,
            source=PERSISTENCE_SOURCE_WRITE,
            identifier=identity.league_season_id,
        )

    def begin_sync(
        self,
        identity: LeagueSeasonIdentity,
        *,
        league_family_id: str,
        family_display_name: str,
        season_display_name: str,
        registration_created_at_ms: int,
        sync_run_id: str,
        started_at_ms: int,
        family_metadata: Mapping[str, Any] | None = None,
        season_metadata: Mapping[str, Any] | None = None,
        request_metadata: Mapping[str, Any] | None = None,
    ) -> FantasySyncSession:
        """Enforce registration-before-start and support safe process re-entry."""

        registration = self.ensure_league_season(
            identity,
            league_family_id=league_family_id,
            family_display_name=family_display_name,
            season_display_name=season_display_name,
            created_at_ms=registration_created_at_ms,
            family_metadata=family_metadata,
            season_metadata=season_metadata,
        )
        sync = self._start_sync(
            identity,
            sync_run_id=sync_run_id,
            started_at_ms=started_at_ms,
            request_metadata=request_metadata,
        )
        return FantasySyncSession(
            identity=identity,
            sync_run_id=sync.identifier,
            registration=registration,
            sync=sync,
        )

    def commit_success(
        self,
        session: FantasySyncSession,
        *,
        snapshot: FantasySnapshot,
        events: Sequence[FantasyChangeEvent],
        observed_at_ms: int,
        accepted_at_ms: int,
        completed_at_ms: int,
        derived_at_ms: int,
        provider_status: str,
        source_metadata: Mapping[str, Any] | None = None,
    ) -> FantasyPersistenceLifecycleOutcome:
        """Commit a validated snapshot/events only while the sync is STARTED."""

        live = self.transport.read_sync_run(session.sync_run_id)
        if not _found(live):
            raise FantasyPersistenceStateConflict(
                "Cannot commit sync success because the STARTED sync run is absent"
            )
        record = _record(live)
        _validate_sync_record_identity(record, session.identity, session.sync_run_id)
        state = _sync_state(record)

        if state == PERSISTENCE_COMPLETED:
            accepted = _optional_text(record.get("accepted_snapshot_id"))
            if accepted != snapshot.snapshot_id:
                raise FantasyPersistenceStateConflict(
                    "Sync is already completed with a different accepted snapshot"
                )
            return _sync_outcome(
                stage=_STAGE_SYNC_SUCCESS,
                state=state,
                source=PERSISTENCE_SOURCE_EXISTING,
                sync_run_id=session.sync_run_id,
                record=record,
            )
        if state == PERSISTENCE_FAILED:
            raise FantasyPersistenceStateConflict(
                "Cannot commit sync success because the sync is already FAILED"
            )
        if state != PERSISTENCE_STARTED:
            raise FantasyPersistenceStateConflict("Sync is not in a committable STARTED state")

        command = build_successful_sync_command(
            session.identity,
            sync_run_id=session.sync_run_id,
            snapshot=snapshot,
            events=events,
            observed_at_ms=observed_at_ms,
            accepted_at_ms=accepted_at_ms,
            completed_at_ms=completed_at_ms,
            derived_at_ms=derived_at_ms,
            provider_status=provider_status,
            source_metadata=source_metadata,
        )

        try:
            self.transport.send(command)
        except Exception as exc:
            if not _is_ambiguous_write_error(exc):
                raise
            return self._recover_success(
                session,
                expected_snapshot_id=snapshot.snapshot_id,
                write_error=exc,
            )

        return FantasyPersistenceLifecycleOutcome(
            stage=_STAGE_SYNC_SUCCESS,
            state=PERSISTENCE_COMPLETED,
            source=PERSISTENCE_SOURCE_WRITE,
            identifier=session.sync_run_id,
            accepted_snapshot_id=snapshot.snapshot_id,
        )

    def commit_failure(
        self,
        session: FantasySyncSession,
        *,
        completed_at_ms: int,
        error_code: str,
        error_summary: str,
    ) -> FantasyPersistenceLifecycleOutcome:
        """Finish a STARTED sync as FAILED without retrying an ambiguous write."""

        live = self.transport.read_sync_run(session.sync_run_id)
        if not _found(live):
            raise FantasyPersistenceStateConflict(
                "Cannot commit sync failure because the STARTED sync run is absent"
            )
        record = _record(live)
        _validate_sync_record_identity(record, session.identity, session.sync_run_id)
        state = _sync_state(record)

        if state == PERSISTENCE_FAILED:
            persisted_code = _optional_text(record.get("error_code"))
            expected_code = _required_text(error_code, "error_code")
            if persisted_code != expected_code:
                raise FantasyPersistenceStateConflict(
                    "Sync is already FAILED with a different error code"
                )
            return _sync_outcome(
                stage=_STAGE_SYNC_FAILED,
                state=state,
                source=PERSISTENCE_SOURCE_EXISTING,
                sync_run_id=session.sync_run_id,
                record=record,
            )
        if state == PERSISTENCE_COMPLETED:
            raise FantasyPersistenceStateConflict(
                "Cannot commit sync failure because the sync is already COMPLETED"
            )
        if state != PERSISTENCE_STARTED:
            raise FantasyPersistenceStateConflict("Sync is not in a fail-able STARTED state")

        command = build_failed_sync_command(
            session.identity,
            sync_run_id=session.sync_run_id,
            completed_at_ms=completed_at_ms,
            error_code=error_code,
            error_summary=error_summary,
        )

        try:
            self.transport.send(command)
        except Exception as exc:
            if not _is_ambiguous_write_error(exc):
                raise
            return self._recover_failure(
                session,
                expected_error_code=command["error_code"],
                write_error=exc,
            )

        return FantasyPersistenceLifecycleOutcome(
            stage=_STAGE_SYNC_FAILED,
            state=PERSISTENCE_FAILED,
            source=PERSISTENCE_SOURCE_WRITE,
            identifier=session.sync_run_id,
            error_code=command["error_code"],
        )

    def _start_sync(
        self,
        identity: LeagueSeasonIdentity,
        *,
        sync_run_id: str,
        started_at_ms: int,
        request_metadata: Mapping[str, Any] | None,
    ) -> FantasyPersistenceLifecycleOutcome:
        command = build_sync_start_command(
            identity,
            sync_run_id=sync_run_id,
            started_at_ms=started_at_ms,
            request_metadata=request_metadata,
        )
        normalized_sync_run_id = command["sync_run_id"]

        existing = self.transport.read_sync_run(normalized_sync_run_id)
        if _found(existing):
            record = _record(existing)
            _validate_sync_record_identity(record, identity, normalized_sync_run_id)
            return _sync_outcome(
                stage=_STAGE_SYNC_START,
                state=_sync_state(record),
                source=PERSISTENCE_SOURCE_EXISTING,
                sync_run_id=normalized_sync_run_id,
                record=record,
            )

        try:
            self.transport.send(command)
        except Exception as exc:
            if not _is_ambiguous_write_error(exc):
                raise
            return self._recover_start(
                identity,
                sync_run_id=normalized_sync_run_id,
                write_error=exc,
            )

        return FantasyPersistenceLifecycleOutcome(
            stage=_STAGE_SYNC_START,
            state=PERSISTENCE_STARTED,
            source=PERSISTENCE_SOURCE_WRITE,
            identifier=normalized_sync_run_id,
        )

    def _recover_registration(
        self,
        identity: LeagueSeasonIdentity,
        *,
        league_family_id: str,
        write_error: Exception,
    ) -> FantasyPersistenceLifecycleOutcome:
        try:
            observed = self.transport.read_league_season(identity.league_season_id)
        except Exception as recovery_error:
            raise _unknown(
                stage=_STAGE_REGISTRATION,
                identifier=identity.league_season_id,
                write_error=write_error,
                recovery_error=recovery_error,
            ) from recovery_error

        if not _found(observed):
            raise _unknown(
                stage=_STAGE_REGISTRATION,
                identifier=identity.league_season_id,
                write_error=write_error,
            ) from write_error

        _validate_league_registration_record(
            _record(observed),
            identity=identity,
            league_family_id=league_family_id,
        )
        return FantasyPersistenceLifecycleOutcome(
            stage=_STAGE_REGISTRATION,
            state=PERSISTENCE_REGISTERED,
            source=PERSISTENCE_SOURCE_RECOVERY,
            identifier=identity.league_season_id,
        )

    def _recover_start(
        self,
        identity: LeagueSeasonIdentity,
        *,
        sync_run_id: str,
        write_error: Exception,
    ) -> FantasyPersistenceLifecycleOutcome:
        try:
            observed = self.transport.read_sync_run(sync_run_id)
        except Exception as recovery_error:
            raise _unknown(
                stage=_STAGE_SYNC_START,
                identifier=sync_run_id,
                write_error=write_error,
                recovery_error=recovery_error,
            ) from recovery_error

        if not _found(observed):
            raise _unknown(
                stage=_STAGE_SYNC_START,
                identifier=sync_run_id,
                write_error=write_error,
            ) from write_error

        record = _record(observed)
        _validate_sync_record_identity(record, identity, sync_run_id)
        return _sync_outcome(
            stage=_STAGE_SYNC_START,
            state=_sync_state(record),
            source=PERSISTENCE_SOURCE_RECOVERY,
            sync_run_id=sync_run_id,
            record=record,
        )

    def _recover_success(
        self,
        session: FantasySyncSession,
        *,
        expected_snapshot_id: str,
        write_error: Exception,
    ) -> FantasyPersistenceLifecycleOutcome:
        try:
            observed = self.transport.read_sync_run(session.sync_run_id)
        except Exception as recovery_error:
            raise _unknown(
                stage=_STAGE_SYNC_SUCCESS,
                identifier=session.sync_run_id,
                write_error=write_error,
                recovery_error=recovery_error,
            ) from recovery_error

        if not _found(observed):
            raise _unknown(
                stage=_STAGE_SYNC_SUCCESS,
                identifier=session.sync_run_id,
                write_error=write_error,
            ) from write_error

        record = _record(observed)
        _validate_sync_record_identity(record, session.identity, session.sync_run_id)
        state = _sync_state(record)
        if state == PERSISTENCE_COMPLETED:
            accepted = _optional_text(record.get("accepted_snapshot_id"))
            if accepted != expected_snapshot_id:
                raise FantasyPersistenceStateConflict(
                    "Recovered COMPLETED sync references a different snapshot"
                )
            return _sync_outcome(
                stage=_STAGE_SYNC_SUCCESS,
                state=state,
                source=PERSISTENCE_SOURCE_RECOVERY,
                sync_run_id=session.sync_run_id,
                record=record,
            )
        if state == PERSISTENCE_FAILED:
            raise FantasyPersistenceStateConflict(
                "Recovered sync is FAILED while success was being committed"
            )

        raise _unknown(
            stage=_STAGE_SYNC_SUCCESS,
            identifier=session.sync_run_id,
            write_error=write_error,
            observed_state=state,
        ) from write_error

    def _recover_failure(
        self,
        session: FantasySyncSession,
        *,
        expected_error_code: str,
        write_error: Exception,
    ) -> FantasyPersistenceLifecycleOutcome:
        try:
            observed = self.transport.read_sync_run(session.sync_run_id)
        except Exception as recovery_error:
            raise _unknown(
                stage=_STAGE_SYNC_FAILED,
                identifier=session.sync_run_id,
                write_error=write_error,
                recovery_error=recovery_error,
            ) from recovery_error

        if not _found(observed):
            raise _unknown(
                stage=_STAGE_SYNC_FAILED,
                identifier=session.sync_run_id,
                write_error=write_error,
            ) from write_error

        record = _record(observed)
        _validate_sync_record_identity(record, session.identity, session.sync_run_id)
        state = _sync_state(record)
        if state == PERSISTENCE_FAILED:
            persisted_code = _optional_text(record.get("error_code"))
            if persisted_code != expected_error_code:
                raise FantasyPersistenceStateConflict(
                    "Recovered FAILED sync has a different error code"
                )
            return _sync_outcome(
                stage=_STAGE_SYNC_FAILED,
                state=state,
                source=PERSISTENCE_SOURCE_RECOVERY,
                sync_run_id=session.sync_run_id,
                record=record,
            )
        if state == PERSISTENCE_COMPLETED:
            raise FantasyPersistenceStateConflict(
                "Recovered sync is COMPLETED while failure was being committed"
            )

        raise _unknown(
            stage=_STAGE_SYNC_FAILED,
            identifier=session.sync_run_id,
            write_error=write_error,
            observed_state=state,
        ) from write_error


def _sync_outcome(
    *,
    stage: str,
    state: str,
    source: str,
    sync_run_id: str,
    record: Mapping[str, Any],
) -> FantasyPersistenceLifecycleOutcome:
    return FantasyPersistenceLifecycleOutcome(
        stage=stage,
        state=state,
        source=source,
        identifier=sync_run_id,
        accepted_snapshot_id=_optional_text(record.get("accepted_snapshot_id")),
        error_code=_optional_text(record.get("error_code")),
    )


def _validate_league_registration_record(
    record: Mapping[str, Any],
    *,
    identity: LeagueSeasonIdentity,
    league_family_id: str,
) -> None:
    expected = {
        "league_season_id": identity.league_season_id,
        "league_family_id": league_family_id,
        "platform": identity.platform,
        "platform_league_id": identity.platform_league_id,
        "season": identity.season,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise FantasyPersistenceStateConflict(
                f"Persisted league registration conflicts on {key}"
            )


def _validate_sync_record_identity(
    record: Mapping[str, Any],
    identity: LeagueSeasonIdentity,
    sync_run_id: str,
) -> None:
    expected = {
        "sync_run_id": sync_run_id,
        "league_season_id": identity.league_season_id,
        "platform": identity.platform,
        "platform_league_id": identity.platform_league_id,
        "season": identity.season,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise FantasyPersistenceStateConflict(
                f"Persisted sync run conflicts on {key}"
            )


def _sync_state(record: Mapping[str, Any]) -> str:
    value = record.get("status")
    if value not in _KNOWN_SYNC_STATES:
        raise FantasyPersistenceStateConflict(
            "Persisted sync run has an unsupported lifecycle status"
        )
    return str(value)


def _found(payload: Mapping[str, Any]) -> bool:
    found = payload.get("found")
    if not isinstance(found, bool):
        raise FantasyPersistenceStateConflict("Persistence read did not return boolean found")
    return found


def _record(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    record = payload.get("record")
    if not isinstance(record, Mapping):
        raise FantasyPersistenceStateConflict("Persistence read did not return a record object")
    return record


def _is_ambiguous_write_error(exc: Exception) -> bool:
    if isinstance(
        exc,
        (FantasyPersistenceTransportError, FantasyPersistenceProtocolError),
    ):
        return True
    return isinstance(exc, FantasyPersistenceRejected) and exc.status_code >= 500


def _unknown(
    *,
    stage: str,
    identifier: str,
    write_error: Exception,
    observed_state: str | None = None,
    recovery_error: Exception | None = None,
) -> FantasyPersistenceOutcomeUnknown:
    return FantasyPersistenceOutcomeUnknown(
        stage=stage,
        identifier=identifier,
        write_error_name=type(write_error).__name__,
        observed_state=observed_state,
        recovery_error_name=(
            None if recovery_error is None else type(recovery_error).__name__
        ),
    )


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise FantasyPersistenceStateConflict(
            "Persisted optional text field is malformed"
        )
    return value.strip()
