from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import pytest

from src.fantasy.changes import FantasySnapshot
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.persistence import LeagueSeasonIdentity
from src.fantasy.persistence_http import (
    FantasyPersistenceProtocolError,
    FantasyPersistenceRejected,
    FantasyPersistenceTransportError,
)
from src.fantasy.persistence_lifecycle import (
    PERSISTENCE_COMPLETED,
    PERSISTENCE_FAILED,
    PERSISTENCE_REGISTERED,
    PERSISTENCE_SOURCE_EXISTING,
    PERSISTENCE_SOURCE_RECOVERY,
    PERSISTENCE_SOURCE_WRITE,
    PERSISTENCE_STARTED,
    FantasyPersistenceCoordinator,
    FantasyPersistenceLifecycleOutcome,
    FantasyPersistenceOutcomeUnknown,
    FantasyPersistenceStateConflict,
    FantasySyncSession,
)


def _identity() -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id="ffl:2026",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
    )


def _league_record(**overrides: Any) -> dict[str, Any]:
    row = {
        "league_season_id": "ffl:2026",
        "league_family_id": "ffl",
        "platform": "SLEEPER",
        "platform_league_id": "league-2026",
        "season": "2026",
        "display_name": "Franchise Football League 2026",
        "created_at_ms": 1,
        "metadata": {},
    }
    row.update(overrides)
    return row


def _sync_record(status: str = "STARTED", **overrides: Any) -> dict[str, Any]:
    row = {
        "sync_run_id": "sync-1",
        "league_season_id": "ffl:2026",
        "platform": "SLEEPER",
        "platform_league_id": "league-2026",
        "season": "2026",
        "started_at_ms": 100,
        "completed_at_ms": None,
        "status": status,
        "accepted_snapshot_id": None,
        "error_code": None,
    }
    row.update(overrides)
    return row


def _read(record: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "found": record is not None,
        "record": record,
    }


def _state() -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-2026",
        name="Franchise Football League",
        season="2026",
        status="in_season",
        team_count=10,
        previous_platform_league_id="league-2025",
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "BN"),
            scoring_settings={"rec": 1},
            waiver_budget=100,
        ),
        draft=None,
        managers=(),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=("1",),
                starters=("1",),
                reserve=(),
                taxi=(),
                settings={},
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _snapshot(snapshot_id: str = "snap-1") -> FantasySnapshot:
    return FantasySnapshot(snapshot_id, _state())


def _session() -> FantasySyncSession:
    return FantasySyncSession(
        identity=_identity(),
        sync_run_id="sync-1",
        registration=FantasyPersistenceLifecycleOutcome(
            stage="REGISTRATION",
            state=PERSISTENCE_REGISTERED,
            source=PERSISTENCE_SOURCE_EXISTING,
            identifier="ffl:2026",
        ),
        sync=FantasyPersistenceLifecycleOutcome(
            stage="SYNC_START",
            state=PERSISTENCE_STARTED,
            source=PERSISTENCE_SOURCE_EXISTING,
            identifier="sync-1",
        ),
    )


@dataclass
class FakeTransport:
    league_reads: list[Any] = field(default_factory=list)
    sync_reads: list[Any] = field(default_factory=list)
    send_effects: list[Any] = field(default_factory=list)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def read_league_season(self, league_season_id: str):
        self.calls.append(("read_league", league_season_id))
        if not self.league_reads:
            raise AssertionError("unexpected league read")
        effect = self.league_reads.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect

    def read_sync_run(self, sync_run_id: str):
        self.calls.append(("read_sync", sync_run_id))
        if not self.sync_reads:
            raise AssertionError("unexpected sync read")
        effect = self.sync_reads.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect

    def send(self, command):
        kind = str(command["kind"])
        self.calls.append(("send", kind))
        if self.send_effects:
            effect = self.send_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect
        return {"ok": True}


def _begin(coordinator: FantasyPersistenceCoordinator) -> FantasySyncSession:
    return coordinator.begin_sync(
        _identity(),
        league_family_id="ffl",
        family_display_name="Franchise Football League",
        season_display_name="Franchise Football League 2026",
        registration_created_at_ms=1,
        sync_run_id="sync-1",
        started_at_ms=100,
        family_metadata={"source": "owner_config"},
        season_metadata={"status": "in_season"},
        request_metadata={"trigger": "manual"},
    )


def test_begin_sync_enforces_registration_before_start_in_exact_order():
    transport = FakeTransport(
        league_reads=[_read(None)],
        sync_reads=[_read(None)],
    )
    session = _begin(FantasyPersistenceCoordinator(transport))

    assert transport.calls == [
        ("read_league", "ffl:2026"),
        ("send", "LEAGUE_SEASON_UPSERT"),
        ("read_sync", "sync-1"),
        ("send", "SYNC_START"),
    ]
    assert session.registration.state == PERSISTENCE_REGISTERED
    assert session.registration.source == PERSISTENCE_SOURCE_WRITE
    assert session.sync.state == PERSISTENCE_STARTED
    assert session.sync.source == PERSISTENCE_SOURCE_WRITE
    assert session.can_commit is True


def test_begin_sync_reuses_matching_registration_and_started_run_without_writes():
    transport = FakeTransport(
        league_reads=[_read(_league_record())],
        sync_reads=[_read(_sync_record())],
    )
    session = _begin(FantasyPersistenceCoordinator(transport))

    assert transport.calls == [
        ("read_league", "ffl:2026"),
        ("read_sync", "sync-1"),
    ]
    assert session.registration.source == PERSISTENCE_SOURCE_EXISTING
    assert session.sync.source == PERSISTENCE_SOURCE_EXISTING


def test_begin_sync_returns_existing_final_state_for_safe_process_reentry():
    transport = FakeTransport(
        league_reads=[_read(_league_record())],
        sync_reads=[
            _read(
                _sync_record(
                    PERSISTENCE_COMPLETED,
                    completed_at_ms=150,
                    accepted_snapshot_id="snap-1",
                )
            )
        ],
    )
    session = _begin(FantasyPersistenceCoordinator(transport))

    assert session.is_final is True
    assert session.can_commit is False
    assert session.sync.state == PERSISTENCE_COMPLETED
    assert session.sync.accepted_snapshot_id == "snap-1"


def test_ambiguous_registration_is_recovered_by_exact_record_without_retry():
    secret = "do-not-leak-registration-detail"
    transport = FakeTransport(
        league_reads=[_read(None), _read(_league_record())],
        sync_reads=[_read(None)],
        send_effects=[
            FantasyPersistenceTransportError(secret),
            {"ok": True},
        ],
    )
    session = _begin(FantasyPersistenceCoordinator(transport))

    assert session.registration.source == PERSISTENCE_SOURCE_RECOVERY
    assert [call for call in transport.calls if call[0] == "send"] == [
        ("send", "LEAGUE_SEASON_UPSERT"),
        ("send", "SYNC_START"),
    ]


def test_ambiguous_start_is_recovered_by_exact_started_record_without_retry():
    transport = FakeTransport(
        league_reads=[_read(_league_record())],
        sync_reads=[_read(None), _read(_sync_record())],
        send_effects=[FantasyPersistenceProtocolError("bad upstream response")],
    )
    session = _begin(FantasyPersistenceCoordinator(transport))

    assert session.sync.state == PERSISTENCE_STARTED
    assert session.sync.source == PERSISTENCE_SOURCE_RECOVERY
    assert transport.calls.count(("send", "SYNC_START")) == 1


def test_ambiguous_start_not_observed_remains_unknown_and_never_retries():
    secret = "upstream-secret-detail"
    transport = FakeTransport(
        league_reads=[_read(_league_record())],
        sync_reads=[_read(None), _read(None)],
        send_effects=[FantasyPersistenceTransportError(secret)],
    )

    with pytest.raises(FantasyPersistenceOutcomeUnknown) as captured:
        _begin(FantasyPersistenceCoordinator(transport))

    assert captured.value.stage == "SYNC_START"
    assert captured.value.write_error_name == "FantasyPersistenceTransportError"
    assert secret not in str(captured.value)
    assert transport.calls.count(("send", "SYNC_START")) == 1


def test_nonrecoverable_write_rejection_propagates_without_recovery_read():
    transport = FakeTransport(
        league_reads=[_read(_league_record())],
        sync_reads=[_read(None)],
        send_effects=[FantasyPersistenceRejected(401, "UNAUTHORIZED", "no")],
    )

    with pytest.raises(FantasyPersistenceRejected):
        _begin(FantasyPersistenceCoordinator(transport))

    assert transport.calls == [
        ("read_league", "ffl:2026"),
        ("read_sync", "sync-1"),
        ("send", "SYNC_START"),
    ]


def test_registration_identity_conflict_fails_before_any_write():
    transport = FakeTransport(
        league_reads=[_read(_league_record(platform_league_id="different"))],
    )

    with pytest.raises(FantasyPersistenceStateConflict, match="platform_league_id"):
        _begin(FantasyPersistenceCoordinator(transport))

    assert not any(call[0] == "send" for call in transport.calls)


def test_sync_identity_conflict_fails_before_any_sync_write():
    transport = FakeTransport(
        league_reads=[_read(_league_record())],
        sync_reads=[_read(_sync_record(season="2025"))],
    )

    with pytest.raises(FantasyPersistenceStateConflict, match="season"):
        _begin(FantasyPersistenceCoordinator(transport))

    assert not any(call == ("send", "SYNC_START") for call in transport.calls)


def test_commit_success_writes_only_from_started_and_returns_direct_commit():
    transport = FakeTransport(sync_reads=[_read(_sync_record())])
    outcome = FantasyPersistenceCoordinator(transport).commit_success(
        _session(),
        snapshot=_snapshot(),
        events=(),
        observed_at_ms=110,
        accepted_at_ms=111,
        completed_at_ms=120,
        derived_at_ms=115,
        provider_status="HEALTHY",
        source_metadata={"source": "test"},
    )

    assert outcome.state == PERSISTENCE_COMPLETED
    assert outcome.source == PERSISTENCE_SOURCE_WRITE
    assert outcome.accepted_snapshot_id == "snap-1"
    assert transport.calls == [
        ("read_sync", "sync-1"),
        ("send", "SYNC_SUCCESS"),
    ]


def test_commit_success_is_idempotent_when_same_snapshot_already_completed():
    transport = FakeTransport(
        sync_reads=[
            _read(
                _sync_record(
                    PERSISTENCE_COMPLETED,
                    completed_at_ms=120,
                    accepted_snapshot_id="snap-1",
                )
            )
        ]
    )
    outcome = FantasyPersistenceCoordinator(transport).commit_success(
        _session(),
        snapshot=_snapshot(),
        events=(),
        observed_at_ms=110,
        accepted_at_ms=111,
        completed_at_ms=120,
        derived_at_ms=115,
        provider_status="HEALTHY",
    )

    assert outcome.source == PERSISTENCE_SOURCE_EXISTING
    assert outcome.state == PERSISTENCE_COMPLETED
    assert not any(call[0] == "send" for call in transport.calls)


def test_commit_success_refuses_existing_different_snapshot():
    transport = FakeTransport(
        sync_reads=[
            _read(
                _sync_record(
                    PERSISTENCE_COMPLETED,
                    completed_at_ms=120,
                    accepted_snapshot_id="other-snapshot",
                )
            )
        ]
    )

    with pytest.raises(FantasyPersistenceStateConflict, match="different accepted snapshot"):
        FantasyPersistenceCoordinator(transport).commit_success(
            _session(),
            snapshot=_snapshot(),
            events=(),
            observed_at_ms=110,
            accepted_at_ms=111,
            completed_at_ms=120,
            derived_at_ms=115,
            provider_status="HEALTHY",
        )


def test_ambiguous_success_recovers_only_matching_completed_snapshot():
    transport = FakeTransport(
        sync_reads=[
            _read(_sync_record()),
            _read(
                _sync_record(
                    PERSISTENCE_COMPLETED,
                    completed_at_ms=120,
                    accepted_snapshot_id="snap-1",
                )
            ),
        ],
        send_effects=[
            FantasyPersistenceRejected(500, "PERSISTENCE_FAILED", "internal"),
        ],
    )
    outcome = FantasyPersistenceCoordinator(transport).commit_success(
        _session(),
        snapshot=_snapshot(),
        events=(),
        observed_at_ms=110,
        accepted_at_ms=111,
        completed_at_ms=120,
        derived_at_ms=115,
        provider_status="HEALTHY",
    )

    assert outcome.state == PERSISTENCE_COMPLETED
    assert outcome.source == PERSISTENCE_SOURCE_RECOVERY
    assert transport.calls.count(("send", "SYNC_SUCCESS")) == 1


def test_ambiguous_success_still_started_is_unknown_without_retry():
    transport = FakeTransport(
        sync_reads=[_read(_sync_record()), _read(_sync_record())],
        send_effects=[FantasyPersistenceTransportError("reset")],
    )

    with pytest.raises(FantasyPersistenceOutcomeUnknown) as captured:
        FantasyPersistenceCoordinator(transport).commit_success(
            _session(),
            snapshot=_snapshot(),
            events=(),
            observed_at_ms=110,
            accepted_at_ms=111,
            completed_at_ms=120,
            derived_at_ms=115,
            provider_status="HEALTHY",
        )

    assert captured.value.observed_state == PERSISTENCE_STARTED
    assert transport.calls.count(("send", "SYNC_SUCCESS")) == 1


def test_commit_failure_direct_existing_and_recovery_paths():
    direct_transport = FakeTransport(sync_reads=[_read(_sync_record())])
    direct = FantasyPersistenceCoordinator(direct_transport).commit_failure(
        _session(),
        completed_at_ms=120,
        error_code="SLEEPER_TIMEOUT",
        error_summary="provider timed out",
    )
    assert direct.state == PERSISTENCE_FAILED
    assert direct.source == PERSISTENCE_SOURCE_WRITE
    assert direct.error_code == "SLEEPER_TIMEOUT"

    existing_transport = FakeTransport(
        sync_reads=[
            _read(
                _sync_record(
                    PERSISTENCE_FAILED,
                    completed_at_ms=120,
                    error_code="SLEEPER_TIMEOUT",
                )
            )
        ]
    )
    existing = FantasyPersistenceCoordinator(existing_transport).commit_failure(
        _session(),
        completed_at_ms=120,
        error_code="SLEEPER_TIMEOUT",
        error_summary="provider timed out",
    )
    assert existing.source == PERSISTENCE_SOURCE_EXISTING
    assert not any(call[0] == "send" for call in existing_transport.calls)

    recovery_transport = FakeTransport(
        sync_reads=[
            _read(_sync_record()),
            _read(
                _sync_record(
                    PERSISTENCE_FAILED,
                    completed_at_ms=120,
                    error_code="SLEEPER_TIMEOUT",
                )
            ),
        ],
        send_effects=[FantasyPersistenceTransportError("reset")],
    )
    recovered = FantasyPersistenceCoordinator(recovery_transport).commit_failure(
        _session(),
        completed_at_ms=120,
        error_code="SLEEPER_TIMEOUT",
        error_summary="provider timed out",
    )
    assert recovered.source == PERSISTENCE_SOURCE_RECOVERY
    assert recovery_transport.calls.count(("send", "SYNC_FAILED")) == 1


def test_commit_failure_refuses_completed_or_different_failure_code():
    completed_transport = FakeTransport(
        sync_reads=[
            _read(
                _sync_record(
                    PERSISTENCE_COMPLETED,
                    completed_at_ms=120,
                    accepted_snapshot_id="snap-1",
                )
            )
        ]
    )
    with pytest.raises(FantasyPersistenceStateConflict, match="already COMPLETED"):
        FantasyPersistenceCoordinator(completed_transport).commit_failure(
            _session(),
            completed_at_ms=121,
            error_code="ERR",
            error_summary="bad",
        )

    failed_transport = FakeTransport(
        sync_reads=[
            _read(
                _sync_record(
                    PERSISTENCE_FAILED,
                    completed_at_ms=120,
                    error_code="OTHER",
                )
            )
        ]
    )
    with pytest.raises(FantasyPersistenceStateConflict, match="different error code"):
        FantasyPersistenceCoordinator(failed_transport).commit_failure(
            _session(),
            completed_at_ms=121,
            error_code="ERR",
            error_summary="bad",
        )


def test_recovery_read_failure_preserves_only_error_type_names():
    secret = "secret-from-write"
    recovery_secret = "secret-from-recovery"
    transport = FakeTransport(
        league_reads=[
            _read(None),
            FantasyPersistenceProtocolError(recovery_secret),
        ],
        send_effects=[FantasyPersistenceTransportError(secret)],
    )

    with pytest.raises(FantasyPersistenceOutcomeUnknown) as captured:
        _begin(FantasyPersistenceCoordinator(transport))

    error = captured.value
    assert error.write_error_name == "FantasyPersistenceTransportError"
    assert error.recovery_error_name == "FantasyPersistenceProtocolError"
    assert secret not in str(error)
    assert recovery_secret not in str(error)


@pytest.mark.parametrize(
    "record",
    [
        _sync_record(PERSISTENCE_STARTED, completed_at_ms=120),
        _sync_record(PERSISTENCE_COMPLETED, completed_at_ms=120, accepted_snapshot_id=None),
        _sync_record(PERSISTENCE_FAILED, completed_at_ms=120, error_code=None),
    ],
)
def test_impossible_persisted_sync_state_shapes_fail_closed(record):
    transport = FakeTransport(
        league_reads=[_read(_league_record())],
        sync_reads=[_read(record)],
    )

    with pytest.raises(FantasyPersistenceStateConflict):
        _begin(FantasyPersistenceCoordinator(transport))


def test_public_package_exports_lifecycle_contract():
    import src.fantasy as fantasy

    assert fantasy.FantasyPersistenceCoordinator is FantasyPersistenceCoordinator
    assert fantasy.FantasySyncSession is FantasySyncSession
    assert fantasy.PERSISTENCE_STARTED == PERSISTENCE_STARTED
    assert fantasy.PERSISTENCE_COMPLETED == PERSISTENCE_COMPLETED
