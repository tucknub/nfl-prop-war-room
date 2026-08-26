from __future__ import annotations

import json

import pytest

from src.fantasy.changes import FantasyChangeEvent, FantasySnapshot, derive_fantasy_change_events
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.persistence import LeagueSeasonIdentity, persistence_content_fingerprint
from src.fantasy.persistence_protocol import (
    FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    JAVASCRIPT_MAX_SAFE_INTEGER,
    SYNC_FAILED,
    SYNC_START,
    SYNC_SUCCESS,
    UnsafePersistenceCommand,
    build_failed_sync_command,
    build_successful_sync_command,
    build_sync_start_command,
)


def _identity() -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id="ffl:2026",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
    )


def _state(*, players=("1",), starters=("1",)) -> FantasyLeagueState:
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
            scoring_settings={"rec": 1, "pass_td": 6},
            waiver_budget=100,
            raw_settings={"provider_only": "excluded"},
        ),
        draft=None,
        managers=(),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=tuple(players),
                starters=tuple(starters),
                reserve=(),
                taxi=(),
                settings={"waiver_budget_used": 0},
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _successful_command():
    previous = FantasySnapshot("snap-before", _state(players=("1",)))
    current = FantasySnapshot("snap-after", _state(players=("1", "2")))
    events = derive_fantasy_change_events(previous, current)
    assert len(events) == 1
    return current, events, build_successful_sync_command(
        _identity(),
        sync_run_id="sync-1",
        snapshot=current,
        events=events,
        observed_at_ms=120,
        accepted_at_ms=121,
        completed_at_ms=130,
        derived_at_ms=125,
        provider_status="HEALTHY",
        expected_previous_snapshot_id="snap-before",
        source_metadata={"catalog_status": "HIT"},
    )


def _contains_key(value, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_key(item, key) for item in value)
    return False


def test_start_command_matches_worker_protocol_and_contains_no_sql():
    command = build_sync_start_command(
        _identity(),
        sync_run_id=" sync-1 ",
        started_at_ms=100,
        request_metadata={"trigger": "manual"},
    )

    assert command == {
        "protocol_version": FANTASY_PERSISTENCE_PROTOCOL_VERSION,
        "kind": SYNC_START,
        "identity": {
            "league_season_id": "ffl:2026",
            "platform": "SLEEPER",
            "platform_league_id": "league-2026",
            "season": "2026",
        },
        "sync_run_id": "sync-1",
        "started_at_ms": 100,
        "request_metadata_json": '{"trigger":"manual"}',
    }
    assert not _contains_key(command, "sql")


def test_failed_command_matches_worker_protocol():
    command = build_failed_sync_command(
        _identity(),
        sync_run_id="sync-1",
        completed_at_ms=150,
        error_code="SLEEPER_TIMEOUT",
        error_summary="provider unavailable",
    )

    assert command["protocol_version"] == FANTASY_PERSISTENCE_PROTOCOL_VERSION
    assert command["kind"] == SYNC_FAILED
    assert command["sync_run_id"] == "sync-1"
    assert command["completed_at_ms"] == 150
    assert command["error_code"] == "SLEEPER_TIMEOUT"
    assert command["error_summary"] == "provider unavailable"
    assert not _contains_key(command, "sql")


def test_success_command_uses_exact_persisted_snapshot_content_and_event_contract():
    snapshot, events, command = _successful_command()

    assert command["protocol_version"] == FANTASY_PERSISTENCE_PROTOCOL_VERSION
    assert command["kind"] == SYNC_SUCCESS
    assert command["sync_run_id"] == "sync-1"
    assert command["expected_previous_snapshot_id"] == "snap-before"
    assert command["completed_at_ms"] == 130
    assert not _contains_key(command, "sql")

    stored = command["snapshot"]
    assert stored["snapshot_id"] == "snap-after"
    assert stored["content_fingerprint"] == persistence_content_fingerprint(snapshot)
    assert stored["provider_status"] == "HEALTHY"
    assert stored["rules_ready"] is True
    assert stored["draft_ready"] is True
    assert stored["ownership_ready"] is True
    normalized = json.loads(stored["normalized_state_json"])
    assert normalized["league"]["platform"] == "SLEEPER"
    assert normalized["league"]["platform_league_id"] == "league-2026"
    assert normalized["league"]["season"] == "2026"
    assert "raw_settings" not in stored["normalized_state_json"]
    assert json.loads(stored["source_metadata_json"]) == {"catalog_status": "HIT"}

    exported_event = command["events"][0]
    source_event = events[0]
    assert exported_event["event_fingerprint"] == source_event.event_fingerprint
    assert exported_event["event_type"] == "PLAYER_ADDED"
    assert exported_event["before_snapshot_id"] == "snap-before"
    assert exported_event["after_snapshot_id"] == "snap-after"
    assert json.loads(exported_event["after_value_json"]) == {"owner_roster_id": "1"}
    assert json.loads(exported_event["source_transaction_ids_json"]) == []
    assert json.loads(exported_event["reason_codes_json"]) == ["OWNERSHIP_CHANGED"]
    assert exported_event["derived_at_ms"] == 125


def test_exported_commands_round_trip_as_strict_json():
    _, _, command = _successful_command()
    encoded = json.dumps(command, allow_nan=False, separators=(",", ":"))
    decoded = json.loads(encoded)

    assert decoded == command
    assert isinstance(decoded["events"], list)
    assert decoded["snapshot"]["normalized_state_json"].startswith("{")


@pytest.mark.parametrize(
    "builder",
    [
        lambda: build_sync_start_command(
            _identity(),
            sync_run_id="sync-unsafe",
            started_at_ms=JAVASCRIPT_MAX_SAFE_INTEGER + 1,
        ),
        lambda: build_failed_sync_command(
            _identity(),
            sync_run_id="sync-unsafe",
            completed_at_ms=JAVASCRIPT_MAX_SAFE_INTEGER + 1,
            error_code="ERR",
            error_summary="unsafe timestamp",
        ),
    ],
)
def test_exporter_rejects_timestamps_outside_javascript_safe_integer_range(builder):
    with pytest.raises(UnsafePersistenceCommand, match="JavaScript safe integer"):
        builder()


def test_success_export_rejects_unsafe_transport_timestamp_before_building_command():
    snapshot = FantasySnapshot("snap", _state())
    with pytest.raises(UnsafePersistenceCommand, match="JavaScript safe integer"):
        build_successful_sync_command(
            _identity(),
            sync_run_id="sync-unsafe",
            snapshot=snapshot,
            events=(),
            observed_at_ms=JAVASCRIPT_MAX_SAFE_INTEGER + 1,
            accepted_at_ms=JAVASCRIPT_MAX_SAFE_INTEGER + 1,
            completed_at_ms=JAVASCRIPT_MAX_SAFE_INTEGER + 1,
            derived_at_ms=JAVASCRIPT_MAX_SAFE_INTEGER + 1,
            provider_status="HEALTHY",
            expected_previous_snapshot_id="snap-before",
        )


def test_exporter_rejects_non_string_event_reason_codes_before_worker_transport():
    snapshot = FantasySnapshot("snap-after", _state())
    event = FantasyChangeEvent(
        event_type="TEST_EVENT",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
        before_snapshot_id="snap-before",
        after_snapshot_id="snap-after",
        reason_codes=("OK", 3),
    )

    with pytest.raises(UnsafePersistenceCommand, match=r"reason_codes\[1\] must be a string"):
        build_successful_sync_command(
            _identity(),
            sync_run_id="sync-1",
            snapshot=snapshot,
            events=(event,),
            observed_at_ms=120,
            accepted_at_ms=121,
            completed_at_ms=130,
            derived_at_ms=125,
            provider_status="HEALTHY",
            expected_previous_snapshot_id="snap-before",
        )
