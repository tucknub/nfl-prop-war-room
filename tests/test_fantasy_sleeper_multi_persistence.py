from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import src.fantasy.sleeper_multi_persistence as multi
from src.fantasy.persistence import LeagueSeasonIdentity
from src.fantasy.persistence_http import (
    FantasyPersistenceProtocolError,
    FantasyPersistenceRejected,
    FantasyPersistenceTransportError,
)
from src.fantasy.persistence_lifecycle import (
    FantasyPersistenceOutcomeUnknown,
    FantasyPersistenceStateConflict,
)
from src.fantasy.sleeper_current import SleeperNflState, UnsafeSleeperCurrentSnapshot
from src.fantasy.sleeper_multi_persistence import (
    SLEEPER_MULTI_PERSIST_ERROR,
    MultiSleeperPersistenceRunResult,
    SleeperPersistenceLeagueSpec,
    run_multi_sleeper_persistence_sync,
)
from src.fantasy.sleeper_persistence import (
    SLEEPER_PERSIST_ACCEPTED,
    SLEEPER_PERSIST_FAILED,
    SLEEPER_PERSIST_NO_CHANGE,
)


def _identity(index: int, *, season: str = "2026") -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id=f"league-{index}:{season}",
        platform="SLEEPER",
        platform_league_id=f"sleeper-{index}",
        season=season,
    )


def _spec(index: int, *, season: str = "2026") -> SleeperPersistenceLeagueSpec:
    return SleeperPersistenceLeagueSpec(
        identity=_identity(index, season=season),
        league_family_id=f"family-{index}",
        family_display_name=f"League {index}",
        season_display_name=f"League {index} {season}",
        registration_created_at_ms=1,
        sync_run_id=f"sync-{index}",
        snapshot_id=f"snapshot-{index}",
        started_at_ms=10,
        observed_at_ms=20,
        accepted_at_ms=21,
        completed_at_ms=23,
        derived_at_ms=22,
        family_metadata={"index": index},
        season_metadata={"season": season},
        request_metadata={"trigger": "test"},
    )


def _nfl_state(*, season: str = "2026") -> SleeperNflState:
    return SleeperNflState(
        season=season,
        league_season=season,
        season_type="regular",
        week=4,
        leg=4,
        display_week=4,
        season_start_date="2026-09-10",
        previous_season="2025",
        league_create_season=season,
    )


@dataclass
class FakeReader:
    state: SleeperNflState
    nfl_state_calls: int = 0

    def fetch_nfl_state(self) -> SleeperNflState:
        self.nfl_state_calls += 1
        return self.state

    def fetch_normalized_league(self, league_id: str, *, current_user_id=None):
        raise AssertionError("single-league runner should be mocked in orchestration tests")

    def fetch_transactions(self, league_id: str, week: int):
        raise AssertionError("single-league runner should be mocked in orchestration tests")


class FakeTransport:
    pass


def _fake_result(mode: str, snapshot_id: str | None = None):
    return SimpleNamespace(mode=mode, accepted_snapshot_id=snapshot_id)


def test_multi_runner_fetches_shared_nfl_state_once_and_preserves_requested_order(
    monkeypatch,
):
    reader = FakeReader(_nfl_state())
    transport = FakeTransport()
    specs = (_spec(2), _spec(1))
    calls = []

    def fake_single(reader_arg, transport_arg, identity, **kwargs):
        calls.append((reader_arg, transport_arg, identity, kwargs))
        mode = (
            SLEEPER_PERSIST_ACCEPTED
            if identity.platform_league_id == "sleeper-2"
            else SLEEPER_PERSIST_NO_CHANGE
        )
        return _fake_result(mode, kwargs["snapshot_id"])

    monkeypatch.setattr(multi, "run_sleeper_persistence_sync", fake_single)

    result = run_multi_sleeper_persistence_sync(
        reader,
        transport,
        specs,
        current_user_id="me",
    )

    assert isinstance(result, MultiSleeperPersistenceRunResult)
    assert reader.nfl_state_calls == 1
    assert result.league_ids == ("sleeper-2", "sleeper-1")
    assert [row.mode for row in result.leagues] == [
        SLEEPER_PERSIST_ACCEPTED,
        SLEEPER_PERSIST_NO_CHANGE,
    ]
    assert result.accepted_count == 1
    assert result.no_change_count == 1
    assert result.persistence_error_count == 0
    assert [call[2].platform_league_id for call in calls] == [
        "sleeper-2",
        "sleeper-1",
    ]
    assert all(call[3]["nfl_state"] is result.nfl_state for call in calls)


def test_provider_failed_result_is_normal_batch_result_not_persistence_error(monkeypatch):
    reader = FakeReader(_nfl_state())

    monkeypatch.setattr(
        multi,
        "run_sleeper_persistence_sync",
        lambda *args, **kwargs: _fake_result(SLEEPER_PERSIST_FAILED),
    )

    result = run_multi_sleeper_persistence_sync(
        reader,
        FakeTransport(),
        (_spec(1),),
        current_user_id="me",
    )

    assert result.provider_failed_count == 1
    assert result.persistence_error_count == 0
    assert not result.has_persistence_errors


def test_known_state_conflict_is_isolated_and_later_league_still_runs(monkeypatch):
    reader = FakeReader(_nfl_state())
    calls = []

    def fake_single(reader_arg, transport_arg, identity, **kwargs):
        calls.append(identity.platform_league_id)
        if identity.platform_league_id == "sleeper-1":
            raise FantasyPersistenceStateConflict("private persisted-state detail")
        return _fake_result(SLEEPER_PERSIST_ACCEPTED, kwargs["snapshot_id"])

    monkeypatch.setattr(multi, "run_sleeper_persistence_sync", fake_single)

    result = run_multi_sleeper_persistence_sync(
        reader,
        FakeTransport(),
        (_spec(1), _spec(2)),
        current_user_id="me",
    )

    first, second = result.leagues
    assert calls == ["sleeper-1", "sleeper-2"]
    assert first.mode == SLEEPER_MULTI_PERSIST_ERROR
    assert first.error_type == "FantasyPersistenceStateConflict"
    assert first.error_stage is None
    assert not first.recovery_required
    assert second.mode == SLEEPER_PERSIST_ACCEPTED
    assert result.persistence_error_count == 1


def test_unknown_persistence_outcome_is_isolated_and_flagged_for_recovery(monkeypatch):
    reader = FakeReader(_nfl_state())

    def fake_single(*args, **kwargs):
        raise FantasyPersistenceOutcomeUnknown(
            stage="SYNC_SUCCESS",
            identifier="sync-1",
            write_error_name="FantasyPersistenceTransportError",
        )

    monkeypatch.setattr(multi, "run_sleeper_persistence_sync", fake_single)

    result = run_multi_sleeper_persistence_sync(
        reader,
        FakeTransport(),
        (_spec(1),),
        current_user_id="me",
    )

    row = result.leagues[0]
    assert row.mode == SLEEPER_MULTI_PERSIST_ERROR
    assert row.error_type == "FantasyPersistenceOutcomeUnknown"
    assert row.error_stage == "SYNC_SUCCESS"
    assert row.recovery_required
    assert result.recovery_required_count == 1


def test_transport_failure_is_isolated_without_automatic_retry(monkeypatch):
    reader = FakeReader(_nfl_state())
    calls = []

    def fake_single(reader_arg, transport_arg, identity, **kwargs):
        calls.append(identity.platform_league_id)
        if identity.platform_league_id == "sleeper-1":
            raise FantasyPersistenceTransportError("connection detail")
        return _fake_result(SLEEPER_PERSIST_NO_CHANGE, "prior")

    monkeypatch.setattr(multi, "run_sleeper_persistence_sync", fake_single)

    result = run_multi_sleeper_persistence_sync(
        reader,
        FakeTransport(),
        (_spec(1), _spec(2)),
        current_user_id="me",
    )

    assert calls == ["sleeper-1", "sleeper-2"]
    assert result.leagues[0].error_type == "FantasyPersistenceTransportError"
    assert result.leagues[1].mode == SLEEPER_PERSIST_NO_CHANGE


def test_auth_rejection_is_batch_fatal_and_does_not_continue(monkeypatch):
    reader = FakeReader(_nfl_state())
    calls = []

    def fake_single(reader_arg, transport_arg, identity, **kwargs):
        calls.append(identity.platform_league_id)
        raise FantasyPersistenceRejected(401, "UNAUTHORIZED", "private worker message")

    monkeypatch.setattr(multi, "run_sleeper_persistence_sync", fake_single)

    with pytest.raises(FantasyPersistenceRejected):
        run_multi_sleeper_persistence_sync(
            reader,
            FakeTransport(),
            (_spec(1), _spec(2)),
            current_user_id="me",
        )

    assert calls == ["sleeper-1"]


def test_protocol_failure_is_batch_fatal(monkeypatch):
    reader = FakeReader(_nfl_state())

    monkeypatch.setattr(
        multi,
        "run_sleeper_persistence_sync",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            FantasyPersistenceProtocolError("unsupported response")
        ),
    )

    with pytest.raises(FantasyPersistenceProtocolError):
        run_multi_sleeper_persistence_sync(
            reader,
            FakeTransport(),
            (_spec(1), _spec(2)),
            current_user_id="me",
        )


def test_unexpected_programming_error_propagates_instead_of_being_hidden(monkeypatch):
    reader = FakeReader(_nfl_state())

    monkeypatch.setattr(
        multi,
        "run_sleeper_persistence_sync",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("bug")),
    )

    with pytest.raises(RuntimeError, match="bug"):
        run_multi_sleeper_persistence_sync(
            reader,
            FakeTransport(),
            (_spec(1), _spec(2)),
            current_user_id="me",
        )


def test_duplicate_identifiers_fail_before_shared_provider_io():
    reader = FakeReader(_nfl_state())
    one = _spec(1)
    duplicate = SleeperPersistenceLeagueSpec(
        **{
            **one.__dict__,
            "identity": _identity(2),
            "sync_run_id": one.sync_run_id,
            "snapshot_id": "snapshot-2",
        }
    )

    with pytest.raises(ValueError, match="sync_run_id"):
        run_multi_sleeper_persistence_sync(
            reader,
            FakeTransport(),
            (one, duplicate),
            current_user_id="me",
        )

    assert reader.nfl_state_calls == 0


def test_mixed_seasons_fail_before_shared_provider_io():
    reader = FakeReader(_nfl_state())

    with pytest.raises(ValueError, match="shared current season"):
        run_multi_sleeper_persistence_sync(
            reader,
            FakeTransport(),
            (_spec(1, season="2026"), _spec(2, season="2025")),
            current_user_id="me",
        )

    assert reader.nfl_state_calls == 0


def test_shared_nfl_state_mismatch_fails_before_any_league_lifecycle(monkeypatch):
    reader = FakeReader(_nfl_state(season="2025"))
    called = False

    def fake_single(*args, **kwargs):
        nonlocal called
        called = True
        return _fake_result(SLEEPER_PERSIST_ACCEPTED)

    monkeypatch.setattr(multi, "run_sleeper_persistence_sync", fake_single)

    with pytest.raises(UnsafeSleeperCurrentSnapshot, match="does not match"):
        run_multi_sleeper_persistence_sync(
            reader,
            FakeTransport(),
            (_spec(1),),
            current_user_id="me",
        )

    assert reader.nfl_state_calls == 1
    assert not called


def test_spec_rejects_invalid_timestamp_order():
    with pytest.raises(ValueError, match="accepted_at_ms"):
        SleeperPersistenceLeagueSpec(
            identity=_identity(1),
            league_family_id="family",
            family_display_name="League",
            season_display_name="League 2026",
            registration_created_at_ms=1,
            sync_run_id="sync",
            snapshot_id="snapshot",
            started_at_ms=10,
            observed_at_ms=20,
            accepted_at_ms=19,
            completed_at_ms=23,
            derived_at_ms=22,
        )


def test_public_package_exports_multi_league_persistence_contract():
    import src.fantasy as fantasy

    assert fantasy.SLEEPER_MULTI_PERSIST_ERROR == SLEEPER_MULTI_PERSIST_ERROR
    assert fantasy.SleeperPersistenceLeagueSpec is SleeperPersistenceLeagueSpec
    assert fantasy.MultiSleeperPersistenceRunResult is MultiSleeperPersistenceRunResult
    assert (
        fantasy.run_multi_sleeper_persistence_sync
        is run_multi_sleeper_persistence_sync
    )
