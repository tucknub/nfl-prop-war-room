from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import pytest

from src.fantasy.changes import FantasySnapshot, derive_fantasy_change_events
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.persistence import (
    LeagueSeasonIdentity,
    UnsafePersistencePlan,
    build_successful_sync_write_plan,
    persistence_content_fingerprint,
)
from src.fantasy.persistence_lifecycle import (
    PERSISTENCE_REGISTERED,
    PERSISTENCE_SOURCE_EXISTING,
    PERSISTENCE_STARTED,
    FantasyPersistenceCoordinator,
    FantasyPersistenceLifecycleOutcome,
    FantasyPersistenceStateConflict,
    FantasySyncSession,
)
from src.fantasy.persistence_protocol import (
    SYNC_SUCCESS,
    build_successful_sync_command,
)
from src.fantasy.persistence_rehydrate import PersistedFantasySnapshot


def _identity() -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id="ffl:2026",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
    )


def _state(*, players=("1",)) -> FantasyLeagueState:
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
                players=tuple(players),
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


def _previous() -> PersistedFantasySnapshot:
    snapshot = FantasySnapshot("snapshot-old", _state(players=("1",)))
    return PersistedFantasySnapshot(
        snapshot=snapshot,
        league_season_id="ffl:2026",
        content_fingerprint=persistence_content_fingerprint(snapshot),
        observed_at_ms=100,
        accepted_at_ms=110,
        provider_status="HEALTHY",
        source_metadata={},
    )


def _current() -> FantasySnapshot:
    return FantasySnapshot("snapshot-new", _state(players=("1", "2")))


def _session() -> FantasySyncSession:
    return FantasySyncSession(
        identity=_identity(),
        sync_run_id="sync-current",
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
            identifier="sync-current",
        ),
    )


def _sync_record():
    return {
        "sync_run_id": "sync-current",
        "league_season_id": "ffl:2026",
        "platform": "SLEEPER",
        "platform_league_id": "league-2026",
        "season": "2026",
        "started_at_ms": 200,
        "completed_at_ms": None,
        "status": "STARTED",
        "accepted_snapshot_id": None,
        "error_code": None,
    }


@dataclass
class FakeTransport:
    sync_reads: list[Any] = field(default_factory=list)
    calls: list[tuple[str, Any]] = field(default_factory=list)

    def read_sync_run(self, sync_run_id: str):
        self.calls.append(("read_sync", sync_run_id))
        value = self.sync_reads.pop(0)
        return {"found": value is not None, "record": value}

    def read_league_season(self, league_season_id: str):
        raise AssertionError("unexpected league read")

    def send(self, command):
        self.calls.append(("send", command))
        return {"ok": True}


def test_success_command_carries_exact_previous_snapshot_id():
    previous = _previous()
    current = _current()
    events = derive_fantasy_change_events(previous.snapshot, current)

    command = build_successful_sync_command(
        _identity(),
        sync_run_id="sync-current",
        snapshot=current,
        events=events,
        observed_at_ms=210,
        accepted_at_ms=215,
        completed_at_ms=230,
        derived_at_ms=220,
        provider_status="HEALTHY",
        expected_previous_snapshot_id=previous.snapshot.snapshot_id,
    )

    assert command["kind"] == SYNC_SUCCESS
    assert command["expected_previous_snapshot_id"] == "snapshot-old"
    assert command["events"][0]["before_snapshot_id"] == "snapshot-old"


def test_first_success_command_uses_explicit_null_previous_and_no_events():
    current = FantasySnapshot("snapshot-first", _state())
    command = build_successful_sync_command(
        _identity(),
        sync_run_id="sync-current",
        snapshot=current,
        events=(),
        observed_at_ms=210,
        accepted_at_ms=215,
        completed_at_ms=230,
        derived_at_ms=220,
        provider_status="HEALTHY",
        expected_previous_snapshot_id=None,
    )
    assert command["expected_previous_snapshot_id"] is None
    assert command["events"] == []


def test_initial_success_cannot_export_change_events_without_previous_snapshot():
    previous = FantasySnapshot("snapshot-before", _state(players=("1",)))
    current = _current()
    events = derive_fantasy_change_events(previous, current)

    with pytest.raises(
        UnsafePersistencePlan,
        match="initial accepted snapshot cannot contain change events",
    ):
        build_successful_sync_write_plan(
            _identity(),
            sync_run_id="sync-current",
            snapshot=current,
            events=events,
            observed_at_ms=210,
            accepted_at_ms=215,
            completed_at_ms=230,
            derived_at_ms=220,
            provider_status="HEALTHY",
            expected_previous_snapshot_id=None,
        )


def test_event_before_snapshot_must_match_expected_previous_snapshot():
    previous = FantasySnapshot("snapshot-before", _state(players=("1",)))
    current = _current()
    events = derive_fantasy_change_events(previous, current)

    with pytest.raises(
        UnsafePersistencePlan,
        match="before_snapshot_id must equal expected_previous_snapshot_id",
    ):
        build_successful_sync_write_plan(
            _identity(),
            sync_run_id="sync-current",
            snapshot=current,
            events=events,
            observed_at_ms=210,
            accepted_at_ms=215,
            completed_at_ms=230,
            derived_at_ms=220,
            provider_status="HEALTHY",
            expected_previous_snapshot_id="different-previous",
        )


def test_lifecycle_passes_verified_previous_snapshot_to_success_command():
    previous = _previous()
    current = _current()
    events = derive_fantasy_change_events(previous.snapshot, current)
    transport = FakeTransport(sync_reads=[_sync_record()])

    outcome = FantasyPersistenceCoordinator(transport).commit_success(
        _session(),
        snapshot=current,
        events=events,
        observed_at_ms=210,
        accepted_at_ms=215,
        completed_at_ms=230,
        derived_at_ms=220,
        provider_status="HEALTHY",
        previous=previous,
    )

    assert outcome.accepted_snapshot_id == "snapshot-new"
    sent = [value for kind, value in transport.calls if kind == "send"]
    assert len(sent) == 1
    assert sent[0]["expected_previous_snapshot_id"] == "snapshot-old"


def test_lifecycle_rejects_tampered_previous_wrapper_before_network():
    previous = replace(_previous(), content_fingerprint="a" * 64)
    transport = FakeTransport()

    with pytest.raises(
        FantasyPersistenceStateConflict,
        match="internally inconsistent",
    ):
        FantasyPersistenceCoordinator(transport).commit_success(
            _session(),
            snapshot=_current(),
            events=(),
            observed_at_ms=210,
            accepted_at_ms=215,
            completed_at_ms=230,
            derived_at_ms=220,
            provider_status="HEALTHY",
            previous=previous,
        )
    assert transport.calls == []


def test_lifecycle_rejects_previous_snapshot_from_other_league_before_network():
    previous = _previous()
    other_state = replace(
        previous.snapshot.league,
        platform_league_id="other-league",
    )
    other_snapshot = FantasySnapshot(previous.snapshot.snapshot_id, other_state)
    other = replace(
        previous,
        snapshot=other_snapshot,
        content_fingerprint=persistence_content_fingerprint(other_snapshot),
    )
    transport = FakeTransport()

    with pytest.raises(
        FantasyPersistenceStateConflict,
        match="league identity does not match",
    ):
        FantasyPersistenceCoordinator(transport).commit_success(
            _session(),
            snapshot=_current(),
            events=(),
            observed_at_ms=210,
            accepted_at_ms=215,
            completed_at_ms=230,
            derived_at_ms=220,
            provider_status="HEALTHY",
            previous=other,
        )
    assert transport.calls == []
