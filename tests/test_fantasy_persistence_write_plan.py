from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

import pytest

from src.fantasy.changes import (
    FantasyChangeEvent,
    FantasySnapshot,
    derive_fantasy_change_events,
)
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.persistence import (
    LeagueSeasonIdentity,
    UnsafePersistencePlan,
    build_failed_sync_statement,
    build_successful_sync_write_plan,
    build_sync_start_statement,
    canonical_json,
    persistence_content_fingerprint,
    serialize_fantasy_snapshot,
)


MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "0001_fantasy_hq_persistence.sql"
)


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
        (
            "ffl:2026",
            "ffl",
            "SLEEPER",
            "league-2026",
            "2026",
            "FFL 2026",
            1,
            "{}",
        ),
    )
    return connection


def _state(
    *,
    players=("1",),
    starters=("1",),
    status="in_season",
) -> FantasyLeagueState:
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
            raw_settings={
                "provider_only": "must not leak into normalized state",
            },
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
    return connection.execute(statement.sql, statement.parameters).rowcount


def _seed_snapshot(
    connection: sqlite3.Connection,
    snapshot: FantasySnapshot,
    observed_at_ms=10,
) -> None:
    connection.execute(
        "INSERT INTO fantasy_state_snapshots ("
        "snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, "
        "provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, "
        "source_metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            snapshot.snapshot_id,
            "ffl:2026",
            persistence_content_fingerprint(snapshot),
            observed_at_ms,
            observed_at_ms,
            "HEALTHY",
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


def test_persistence_fingerprint_hashes_exact_stored_normalized_content():
    first = FantasySnapshot("snap-a", _state())
    renamed = FantasySnapshot(
        "snap-b",
        replace(_state(), name="Franchise Football League Renamed"),
    )

    # Change detection intentionally ignores display-name churn.
    assert first.fingerprint == renamed.fingerprint

    # Persistence must still fingerprint the exact JSON stored in the row.
    first_json = canonical_json(serialize_fantasy_snapshot(first))
    expected = sha256(first_json.encode("utf-8")).hexdigest()
    assert persistence_content_fingerprint(first) == expected
    assert persistence_content_fingerprint(first) != persistence_content_fingerprint(renamed)


def test_success_plan_executes_against_actual_migration_and_completes_sync():
    connection = _db()
    previous = FantasySnapshot(
        "snap-before",
        _state(players=("1",), starters=("1",)),
    )
    current = FantasySnapshot(
        "snap-after",
        _state(players=("1", "2"), starters=("1",)),
    )
    events = derive_fantasy_change_events(previous, current)
    assert [event.event_type for event in events] == ["PLAYER_ADDED"]

    _seed_snapshot(connection, previous)
    assert _execute(
        connection,
        build_sync_start_statement(
            _identity(),
            sync_run_id="sync-1",
            started_at_ms=20,
            request_metadata={"trigger": "manual"},
        ),
    ) == 1

    plan = build_successful_sync_write_plan(
        _identity(),
        sync_run_id="sync-1",
        snapshot=current,
        events=events,
        observed_at_ms=30,
        accepted_at_ms=31,
        completed_at_ms=35,
        derived_at_ms=32,
        provider_status="HEALTHY",
        expected_previous_snapshot_id="snap-before",
        source_metadata={"catalog_status": "HIT"},
    )
    for statement in plan.statements:
        affected = _execute(connection, statement)
        if statement.expected_affected_rows is not None:
            assert affected == statement.expected_affected_rows
    connection.commit()

    snapshot_row = connection.execute(
        "SELECT content_fingerprint, provider_status, normalized_state_json, "
        "source_metadata_json FROM fantasy_state_snapshots WHERE snapshot_id = ?",
        ("snap-after",),
    ).fetchone()
    assert snapshot_row[0] == persistence_content_fingerprint(current)
    assert snapshot_row[1] == "HEALTHY"
    stored_state = json.loads(snapshot_row[2])
    assert stored_state["league"]["platform_league_id"] == "league-2026"
    assert stored_state["league"]["status"] == "in_season"
    assert stored_state["league"]["rosters"][0]["players"] == ["1", "2"]
    assert json.loads(snapshot_row[3]) == {"catalog_status": "HIT"}

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
        build_sync_start_statement(
            _identity(),
            sync_run_id="sync-fail",
            started_at_ms=20,
        ),
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
        "SELECT status, accepted_snapshot_id, error_code, error_summary "
        "FROM fantasy_sync_runs"
    ).fetchone()
    assert row == (
        "FAILED",
        None,
        "SLEEPER_TIMEOUT",
        "provider unavailable",
    )
    assert (
        connection.execute(
            "SELECT COUNT(*) FROM fantasy_state_snapshots"
        ).fetchone()[0]
        == 0
    )


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
            provider_status="HEALTHY",
            expected_previous_snapshot_id="snap-before",
        )


def test_success_plan_rejects_event_not_bound_to_accepted_snapshot():
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
            provider_status="HEALTHY",
            expected_previous_snapshot_id="snap-before",
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
            provider_status="HEALTHY",
            expected_previous_snapshot_id="before",
        )


def test_missing_started_sync_fails_sql_and_cannot_create_orphan_snapshot():
    connection = _db()
    snapshot = FantasySnapshot("orphan-candidate", _state())
    plan = build_successful_sync_write_plan(
        _identity(),
        sync_run_id="missing-sync",
        snapshot=snapshot,
        events=(),
        observed_at_ms=20,
        accepted_at_ms=20,
        completed_at_ms=21,
        derived_at_ms=20,
        provider_status="HEALTHY",
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="fantasy_state_snapshots.league_season_id",
    ):
        _execute(connection, plan.statements[0])

    assert (
        connection.execute(
            "SELECT COUNT(*) FROM fantasy_state_snapshots"
        ).fetchone()[0]
        == 0
    )


def test_finished_sync_fails_sql_and_cannot_accept_later_snapshot():
    connection = _db()
    assert _execute(
        connection,
        build_sync_start_statement(
            _identity(),
            sync_run_id="sync-finished",
            started_at_ms=20,
        ),
    ) == 1
    assert _execute(
        connection,
        build_failed_sync_statement(
            _identity(),
            sync_run_id="sync-finished",
            completed_at_ms=21,
            error_code="PROVIDER_FAILED",
            error_summary="failed before normalization",
        ),
    ) == 1

    plan = build_successful_sync_write_plan(
        _identity(),
        sync_run_id="sync-finished",
        snapshot=FantasySnapshot("too-late", _state()),
        events=(),
        observed_at_ms=22,
        accepted_at_ms=22,
        completed_at_ms=23,
        derived_at_ms=22,
        provider_status="HEALTHY",
    )

    with pytest.raises(
        sqlite3.IntegrityError,
        match="fantasy_state_snapshots.league_season_id",
    ):
        _execute(connection, plan.statements[0])

    assert (
        connection.execute(
            "SELECT COUNT(*) FROM fantasy_state_snapshots"
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    ("observed", "accepted", "derived", "completed", "message"),
    [
        (10, 9, 10, 11, "accepted_at_ms"),
        (10, 10, 9, 11, "derived_at_ms"),
        (10, 11, 10, 10, "completed_at_ms"),
        (10, 10, 12, 11, "completed_at_ms"),
    ],
)
def test_success_plan_rejects_impossible_timestamp_ordering(
    observed,
    accepted,
    derived,
    completed,
    message,
):
    with pytest.raises(UnsafePersistencePlan, match=message):
        build_successful_sync_write_plan(
            _identity(),
            sync_run_id="sync-time",
            snapshot=FantasySnapshot("snap", _state()),
            events=(),
            observed_at_ms=observed,
            accepted_at_ms=accepted,
            completed_at_ms=completed,
            derived_at_ms=derived,
            provider_status="HEALTHY",
        )


def test_success_plan_requires_explicit_provider_health_status():
    with pytest.raises(ValueError, match="provider_status"):
        build_successful_sync_write_plan(
            _identity(),
            sync_run_id="sync-health",
            snapshot=FantasySnapshot("snap", _state()),
            events=(),
            observed_at_ms=1,
            accepted_at_ms=1,
            completed_at_ms=1,
            derived_at_ms=1,
            provider_status=" ",
        )
