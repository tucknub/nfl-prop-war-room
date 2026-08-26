from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from src.fantasy.changes import FantasyChangeEvent, FantasySnapshot, derive_fantasy_change_events
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.persistence import (
    LeagueSeasonIdentity,
    UnsafePersistencePlan,
    build_failed_sync_statement,
    build_successful_sync_write_plan,
    build_sync_start_statement,
    canonical_json,
    serialize_fantasy_snapshot,
)


MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "0001_fantasy_hq_persistence.sql"


def _db() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(MIGRATION.read_text(encoding="utf-8"))
    connection.execute(
        "INSERT INTO fantasy_league_families "
        "(league_family_id, display_name, created_at_ms, metadata_json) "
        "VALUES (?, ?, ?, ?)",
        ("ffl", "Franchise Football League", 1, "{}"),
    )
    connection.execute(
        "INSERT INTO fantasy_league_seasons "
        "(league_season_id, league_family_id, platform, platform_league_id, season, "
        "display_name, created_at_ms, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("ffl:2026", "ffl", "SLEEPER", "league-2026", "2026", "FFL 2026", 1, "{}"),
    )
    return connection


def _state(*, players=("1",), starters=("1",), status="in_season") -> FantasyLeagueState:
    roster = Roster(
        platform_roster_id="1",
        platform_user_id="me",
        players=tuple(players),
        starters=tuple(starters),
        reserve=(),
        taxi=(),
        settings={"waiver_budget_used": 0, "waiver_position": 1},
    )
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-2026",
        name="Franchise Football League",
        season="2026",
        status=status,
        team_count=10,
        previous_platform_league_id="league-2025",
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "BN"),
            scoring_settings={"rec": 1, "pass_td": 6},
            waiver_budget=100,
            raw_settings={"provider_only": "must not leak into normalized state"},
        ),
        draft=None,
        managers=(),
        rosters=(roster,),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _identity() -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id="ffl:2026",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
    )


def _execute(connection: sqlite3.Connection, statement) -> int:
    cursor = connection.execute(statement.sql, statement.parameters)
    return cursor.rowcount


def _seed_snapshot(connection: sqlite3.Connection, snapshot: FantasySnapshot, observed_at_ms=10) -> None:
    connection.execute(
        "INSERT INTO fantasy_state_snapshots ("
        "snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, "
        "provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, "
        "source_metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            snapshot.snapshot_id,
            "ffl:2026",
            snapshot.fingerprint,
            observed_at_ms,
            observed_at_ms,
            snapshot.league.status,
            1,
            1,
            1,
            canonical_json(serialize_fantasy_snapshot(snapshot)),
            "{}",
        ),
    )


def test_canonical_json_is_deterministic_and_rejects_non_json_numbers():
    assert canonical_json({"b": 2, "a": 1}) == '{"a":1,"b":2}'
    with pytest.raises(ValueError, match="valid persistence JSON"):
        canonical_json({"bad": float("nan")})


def test_snapshot_serialization_uses_normalized_facts_not_raw_provider_settings():
    payload = serialize_fantasy_snapshot(FantasySnapshot("snap-1", _state()))
    encoded = canonical_json(payload)

    assert payload["league"]["rules"]["rules_fingerprint"]
    assert payload["league"]["rules"]["waiver_budget"] == 100
    assert "raw_settings" not in encoded
    assert "provider_only" not in encoded


def test_success_plan_executes_against_the_actual_migration_and_completes_sync_atomically():
    connection = _db()
    previous = FantasySnapshot("snap-before", _state(players=("1",), starters=("1",)))
    current = FantasySnapshot("snap-after", _state(players=("1", "2"), starters=("1",)))
    events = derive_fantasy_change_events(previous, current)
    assert [event.event_type for event in events] == ["PLAYER_ADDED"]

    _seed_snapshot(connection, previous)
    start = build_sync_start_statement(
        _identity(),
        sync_run_id="sync-1",
        started_at_ms=20,
        request_metadata={"trigger": "manual"},
    )
    assert _execute(connection, start) == 1

    plan = build_successful_sync_write_plan(
        _identity(),
        sync_run_id="sync-1",
        snapshot=current,
        events=events,
        observed_at_ms=30,
        accepted_at_ms=31,
        completed_at_ms=35,
        derived_at_ms=32,
        source_metadata={"catalog_status": "HIT"},
    )

    connection.execute("BEGIN") if not connection.in_transaction else None
    for statement in plan.statements:
        affected = _execute(connection, statement)
        if statement.expected_affected_rows is not None:
            assert affected == statement.expected_affected_rows
    connection.commit()

    snapshot_row = connection.execute(
        "SELECT content_fingerprint, normalized_state_json, source_metadata_json "
        "FROM fantasy_state_snapshots WHERE snapshot_id = ?",
        ("snap-after",),
    ).fetchone()
    assert snapshot_row[0] == current.fingerprint
    stored_state = json.loads(snapshot_row[1])
    assert stored_state["league"]["platform_league_id"] == "league-2026"
    assert stored_state["league"]["rosters"][0]["players"] == ["1", "2"]
    assert json.loads(snapshot_row[2]) == {"catalog_status": "HIT"}

    event_row = connection.execute(
        "SELECT event_type, before_snapshot_id, after_snapshot_id, after_value_json "
        "FROM fantasy_change_events"
    ).fetchone()
    assert event_row[:3] == ("PLAYER_ADDED", "snap-before", "snap-after")
    assert json.loads(event_row[3]) == {"owner_roster_id": "1"}

    sync_row = connection.execute(
        "SELECT status, accepted_snapshot_id, error_code, error_summary "
        "FROM fantasy_sync_runs WHERE sync_run_id = ?",
        ("sync-1",),
    ).fetchone()
    assert sync_row == ("COMPLETED", "snap-after", None, None)


def test_failed_sync_update_records_failure_without_creating_snapshot():
    connection = _db()
    assert _execute(
        connection,
        build_sync_start_statement(_identity(), sync_run_id="sync-fail", started_at_ms=20),
    ) == 1
    assert _execute(
        connection,
        build_failed_sync_statement(
            _identity(),
            sync_run_id="sync-fail",
            completed_at_ms=25,
            error_code="SLEEPER_TIMEOUT",
            error_summary="provider unavailable",
        ),
    ) == 1

    row = connection.execute(
        "SELECT status, accepted_snapshot_id, error_code, error_summary FROM fantasy_sync_runs"
    ).fetchone()
    assert row == ("FAILED", None, "SLEEPER_TIMEOUT", "provider unavailable")
    assert connection.execute("SELECT COUNT(*) FROM fantasy_state_snapshots").fetchone()[0] == 0


def test_success_plan_rejects_wrong_league_identity_before_generating_sql():
    wrong_identity = LeagueSeasonIdentity(
        league_season_id="ffl:2026",
        platform="SLEEPER",
        platform_league_id="other-league",
        season="2026",
    )

    with pytest.raises(UnsafePersistencePlan, match="does not match"):
        build_successful_sync_write_plan(
            wrong_identity,
            sync_run_id="sync-1",
            snapshot=FantasySnapshot("snap", _state()),
            events=(),
            observed_at_ms=1,
            accepted_at_ms=1,
            completed_at_ms=1,
            derived_at_ms=1,
        )


def test_success_plan_rejects_event_not_bound_to_the_accepted_snapshot():
    snapshot = FantasySnapshot("snap-after", _state())
    event = FantasyChangeEvent(
        event_type="TEST_EVENT",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
        before_snapshot_id="snap-before",
        after_snapshot_id="different-after",
    )

    with pytest.raises(UnsafePersistencePlan, match="after_snapshot_id"):
        build_successful_sync_write_plan(
            _identity(),
            sync_run_id="sync-1",
            snapshot=snapshot,
            events=(event,),
            observed_at_ms=1,
            accepted_at_ms=1,
            completed_at_ms=1,
            derived_at_ms=1,
        )


def test_success_plan_rejects_duplicate_event_fingerprints():
    previous = FantasySnapshot("before", _state(players=("1",)))
    current = FantasySnapshot("after", _state(players=("1", "2")))
    event = derive_fantasy_change_events(previous, current)[0]

    with pytest.raises(UnsafePersistencePlan, match="duplicate event fingerprints"):
        build_successful_sync_write_plan(
            _identity(),
            sync_run_id="sync-1",
            snapshot=current,
            events=(event, event),
            observed_at_ms=1,
            accepted_at_ms=1,
            completed_at_ms=1,
            derived_at_ms=1,
        )


def test_schema_foreign_keys_reject_success_plan_when_sync_run_was_never_started():
    connection = _db()
    previous = FantasySnapshot("before", _state(players=("1",)))
    current = FantasySnapshot("after", _state(players=("1", "2")))
    _seed_snapshot(connection, previous)
    plan = build_successful_sync_write_plan(
        _identity(),
        sync_run_id="missing-sync",
        snapshot=current,
        events=derive_fantasy_change_events(previous, current),
        observed_at_ms=20,
        accepted_at_ms=20,
        completed_at_ms=21,
        derived_at_ms=20,
    )

    # Snapshot/event statements themselves are valid. The final completion update
    # affects zero rows, which the future D1 executor must treat as a failed batch.
    for statement in plan.statements[:-1]:
        assert _execute(connection, statement) == 1
    assert _execute(connection, plan.statements[-1]) == 0
    assert plan.statements[-1].expected_affected_rows == 1
