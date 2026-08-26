from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.fantasy.scheduled_sync as scheduled
from src.fantasy.persistence import LeagueSeasonIdentity
from src.fantasy.persistence_protocol import JAVASCRIPT_MAX_SAFE_INTEGER
from src.fantasy.scheduled_sync import (
    SLEEPER_SCHEDULE_TRIGGER,
    SLEEPER_SCHEDULE_VERSION,
    SleeperScheduledLeague,
    SleeperScheduledSyncPlan,
    SleeperScheduledSyncRunResult,
    build_sleeper_scheduled_sync_plan,
    run_scheduled_sleeper_persistence_sync,
)


def _identity(index: int, *, season: str = "2026") -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id=f"league-{index}:{season}",
        platform="SLEEPER",
        platform_league_id=f"sleeper-{index}",
        season=season,
    )


def _league(index: int, *, season: str = "2026") -> SleeperScheduledLeague:
    return SleeperScheduledLeague(
        identity=_identity(index, season=season),
        league_family_id=f"family-{index}",
        family_display_name=f"League {index}",
        season_display_name=f"League {index} {season}",
        registration_created_at_ms=1_000,
        family_metadata={"family": index},
        season_metadata={"season": season},
        request_metadata={"source": "test"},
    )


def _fake_multi_result(*league_ids: str):
    return SimpleNamespace(
        league_ids=tuple(league_ids),
        accepted_count=1,
        no_change_count=1,
        provider_failed_count=0,
        persistence_error_count=0,
        recovery_required_count=0,
    )


def test_plan_is_deterministic_for_same_scheduler_slot():
    leagues = (_league(1), _league(2))

    first = build_sleeper_scheduled_sync_plan(
        leagues,
        scheduled_at_ms=2_000,
        schedule_name="primary",
    )
    second = build_sleeper_scheduled_sync_plan(
        leagues,
        scheduled_at_ms=2_000,
        schedule_name="primary",
    )

    assert first == second
    assert first.batch_id == second.batch_id
    assert first.sync_run_ids == second.sync_run_ids
    assert first.snapshot_ids == second.snapshot_ids


def test_duplicate_delivery_under_renamed_schedule_keeps_per_league_ids_stable():
    leagues = (_league(1), _league(2))

    first = build_sleeper_scheduled_sync_plan(
        leagues,
        scheduled_at_ms=2_000,
        schedule_name="old-name",
    )
    second = build_sleeper_scheduled_sync_plan(
        leagues,
        scheduled_at_ms=2_000,
        schedule_name="new-name",
    )

    assert first.sync_run_ids == second.sync_run_ids
    assert first.snapshot_ids == second.snapshot_ids
    assert first.batch_id == second.batch_id
    assert first.specs[0].request_metadata["schedule_name"] == "old-name"
    assert second.specs[0].request_metadata["schedule_name"] == "new-name"


def test_new_scheduler_slot_produces_new_sync_and_snapshot_ids():
    leagues = (_league(1),)

    first = build_sleeper_scheduled_sync_plan(
        leagues,
        scheduled_at_ms=2_000,
    )
    second = build_sleeper_scheduled_sync_plan(
        leagues,
        scheduled_at_ms=3_000,
    )

    assert first.batch_id != second.batch_id
    assert first.sync_run_ids != second.sync_run_ids
    assert first.snapshot_ids != second.snapshot_ids


def test_same_slot_produces_unique_ids_for_each_league():
    plan = build_sleeper_scheduled_sync_plan(
        (_league(1), _league(2), _league(3)),
        scheduled_at_ms=2_000,
    )

    assert len(set(plan.sync_run_ids)) == 3
    assert len(set(plan.snapshot_ids)) == 3
    assert plan.league_ids == ("sleeper-1", "sleeper-2", "sleeper-3")


def test_plan_uses_scheduled_slot_as_retry_stable_logical_timestamp():
    plan = build_sleeper_scheduled_sync_plan(
        (_league(1),),
        scheduled_at_ms=2_000,
        schedule_name="fantasy-hourly",
    )
    spec = plan.specs[0]

    assert spec.started_at_ms == 2_000
    assert spec.observed_at_ms == 2_000
    assert spec.accepted_at_ms == 2_000
    assert spec.derived_at_ms == 2_000
    assert spec.completed_at_ms == 2_000
    assert spec.request_metadata == {
        "source": "test",
        "trigger": SLEEPER_SCHEDULE_TRIGGER,
        "schedule_version": SLEEPER_SCHEDULE_VERSION,
        "schedule_name": "fantasy-hourly",
        "scheduled_at_ms": 2_000,
        "batch_id": plan.batch_id,
    }


def test_batch_id_changes_when_ordered_league_set_changes():
    first = build_sleeper_scheduled_sync_plan(
        (_league(1), _league(2)),
        scheduled_at_ms=2_000,
    )
    second = build_sleeper_scheduled_sync_plan(
        (_league(1), _league(3)),
        scheduled_at_ms=2_000,
    )

    assert first.batch_id != second.batch_id


def test_reserved_request_metadata_cannot_be_overridden():
    with pytest.raises(ValueError, match="reserved keys"):
        SleeperScheduledLeague(
            identity=_identity(1),
            league_family_id="family",
            family_display_name="League",
            season_display_name="League 2026",
            registration_created_at_ms=1,
            request_metadata={"scheduled_at_ms": 123},
        )


def test_duplicate_league_identifiers_fail_before_plan_creation():
    one = _league(1)
    duplicate = SleeperScheduledLeague(
        identity=LeagueSeasonIdentity(
            league_season_id=one.identity.league_season_id,
            platform="SLEEPER",
            platform_league_id="other-platform-id",
            season="2026",
        ),
        league_family_id="other-family",
        family_display_name="Other League",
        season_display_name="Other League 2026",
        registration_created_at_ms=1_000,
    )

    with pytest.raises(ValueError, match="league_season_id"):
        build_sleeper_scheduled_sync_plan(
            (one, duplicate),
            scheduled_at_ms=2_000,
        )


def test_mixed_seasons_fail_before_plan_creation():
    with pytest.raises(ValueError, match="shared season"):
        build_sleeper_scheduled_sync_plan(
            (_league(1, season="2026"), _league(2, season="2025")),
            scheduled_at_ms=2_000,
        )


def test_registration_timestamp_cannot_be_after_schedule_slot():
    with pytest.raises(ValueError, match="registration_created_at_ms"):
        build_sleeper_scheduled_sync_plan(
            (_league(1),),
            scheduled_at_ms=999,
        )


def test_schedule_timestamp_must_be_javascript_safe():
    with pytest.raises(ValueError, match="JavaScript safe integer"):
        build_sleeper_scheduled_sync_plan(
            (_league(1),),
            scheduled_at_ms=JAVASCRIPT_MAX_SAFE_INTEGER + 1,
        )


def test_runner_builds_plan_then_calls_multi_runner_once(monkeypatch):
    captured = {}

    def fake_multi(reader, transport, specs, *, current_user_id):
        captured["reader"] = reader
        captured["transport"] = transport
        captured["specs"] = tuple(specs)
        captured["current_user_id"] = current_user_id
        return _fake_multi_result("sleeper-2", "sleeper-1")

    monkeypatch.setattr(
        scheduled,
        "run_multi_sleeper_persistence_sync",
        fake_multi,
    )

    reader = object()
    transport = object()
    result = run_scheduled_sleeper_persistence_sync(
        reader,
        transport,
        (_league(2), _league(1)),
        scheduled_at_ms=2_000,
        current_user_id="me",
        schedule_name="fantasy-hourly",
    )

    assert isinstance(result, SleeperScheduledSyncRunResult)
    assert isinstance(result.plan, SleeperScheduledSyncPlan)
    assert captured["reader"] is reader
    assert captured["transport"] is transport
    assert captured["specs"] == result.plan.specs
    assert captured["current_user_id"] == "me"
    assert result.plan.league_ids == ("sleeper-2", "sleeper-1")
    assert result.accepted_count == 1
    assert result.no_change_count == 1


def test_runner_propagates_multi_runner_failure(monkeypatch):
    def fake_multi(*args, **kwargs):
        raise RuntimeError("batch failure")

    monkeypatch.setattr(
        scheduled,
        "run_multi_sleeper_persistence_sync",
        fake_multi,
    )

    with pytest.raises(RuntimeError, match="batch failure"):
        run_scheduled_sleeper_persistence_sync(
            object(),
            object(),
            (_league(1),),
            scheduled_at_ms=2_000,
            current_user_id="me",
        )


def test_scheduled_result_rejects_mismatched_league_order():
    plan = build_sleeper_scheduled_sync_plan(
        (_league(1), _league(2)),
        scheduled_at_ms=2_000,
    )

    with pytest.raises(ValueError, match="order"):
        SleeperScheduledSyncRunResult(
            plan=plan,
            result=_fake_multi_result("sleeper-2", "sleeper-1"),
        )


def test_public_package_exports_scheduled_sync_contract():
    import src.fantasy as fantasy

    assert fantasy.SLEEPER_SCHEDULE_VERSION == SLEEPER_SCHEDULE_VERSION
    assert fantasy.SLEEPER_SCHEDULE_TRIGGER == SLEEPER_SCHEDULE_TRIGGER
    assert fantasy.SleeperScheduledLeague is SleeperScheduledLeague
    assert fantasy.SleeperScheduledSyncPlan is SleeperScheduledSyncPlan
    assert fantasy.SleeperScheduledSyncRunResult is SleeperScheduledSyncRunResult
    assert (
        fantasy.build_sleeper_scheduled_sync_plan
        is build_sleeper_scheduled_sync_plan
    )
    assert (
        fantasy.run_scheduled_sleeper_persistence_sync
        is run_scheduled_sleeper_persistence_sync
    )
