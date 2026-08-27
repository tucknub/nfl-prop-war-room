from __future__ import annotations

from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.roster_health import (
    NEEDS_ATTENTION,
    PRE_DRAFT,
    READY,
    WATCH,
    analyze_roster_health,
)


def _league(
    *,
    players=(),
    starters=(),
    roster_positions=("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN"),
) -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-1",
        name="Test League",
        season="2026",
        status="in_season",
        team_count=12,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=tuple(roster_positions),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Me",
                team_name="My Team",
            ),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=tuple(players),
                starters=tuple(starters),
                reserve=(),
                taxi=(),
            ),
        ),
        rules_ready=True,
        draft_ready=False,
        ownership_ready=True,
    )


CATALOG = {
    "qb1": {"full_name": "Quarterback One", "position": "QB", "status": "Active"},
    "rb1": {"full_name": "Running Back One", "position": "RB", "status": "Active"},
    "rb2": {"full_name": "Running Back Two", "position": "RB", "status": "Active"},
    "rb3": {"full_name": "Running Back Three", "position": "RB", "status": "Active"},
    "wr1": {"full_name": "Wideout One", "position": "WR", "status": "Active"},
    "wr2": {"full_name": "Wideout Two", "position": "WR", "status": "Active"},
    "wr3": {"full_name": "Wideout Three", "position": "WR", "status": "Active"},
    "te1": {"full_name": "Tight End One", "position": "TE", "status": "Active"},
    "te2": {"full_name": "Tight End Two", "position": "TE", "status": "Active"},
    "q1": {
        "full_name": "Questionable Player",
        "position": "WR",
        "injury_status": "Questionable",
    },
    "out1": {
        "full_name": "Out Player",
        "position": "RB",
        "injury_status": "Out",
    },
}


def test_empty_roster_is_pre_draft():
    summary = analyze_roster_health(_league(), CATALOG)

    assert summary.status == PRE_DRAFT
    assert summary.roster_size == 0
    assert summary.open_starter_slots == 7
    assert summary.issues[0].code == "ROSTER_EMPTY"


def test_complete_roster_with_depth_is_ready():
    players = ("qb1", "rb1", "rb2", "rb3", "wr1", "wr2", "wr3", "te1", "te2")
    starters = ("qb1", "rb1", "rb2", "wr1", "wr2", "te1", "wr3")

    summary = analyze_roster_health(
        _league(players=players, starters=starters),
        CATALOG,
    )

    assert summary.status == READY
    assert summary.open_starter_slots == 0
    assert summary.position_counts == {
        "QB": 1,
        "RB": 3,
        "TE": 2,
        "WR": 3,
    }
    assert summary.critical_count == 0
    assert summary.warning_count == 0


def test_exact_flex_minimum_is_watch():
    players = ("qb1", "rb1", "rb2", "wr1", "wr2", "wr3", "te1")
    starters = players

    summary = analyze_roster_health(
        _league(players=players, starters=starters),
        CATALOG,
    )

    assert summary.status == WATCH
    assert any(row.code == "NO_FLEX_BENCH_DEPTH" for row in summary.issues)


def test_missing_direct_starter_depth_is_critical():
    players = ("qb1", "rb1", "wr1", "wr2", "wr3", "te1", "te2")
    starters = ("qb1", "rb1", "wr1", "wr2", "te1", "wr3")

    summary = analyze_roster_health(
        _league(players=players, starters=starters),
        CATALOG,
    )

    assert summary.status == NEEDS_ATTENTION
    assert any(
        row.code == "MISSING_DIRECT_STARTER_DEPTH" and row.position == "RB"
        for row in summary.issues
    )


def test_open_starter_slot_is_watch_when_otherwise_healthy():
    players = ("qb1", "rb1", "rb2", "rb3", "wr1", "wr2", "wr3", "te1", "te2")
    starters = ("qb1", "rb1", "rb2", "wr1", "wr2", "te1")

    summary = analyze_roster_health(
        _league(players=players, starters=starters),
        CATALOG,
    )

    assert summary.status == WATCH
    assert summary.open_starter_slots == 1
    assert any(row.code == "OPEN_STARTER_SLOTS" for row in summary.issues)


def test_questionable_and_out_players_are_distinguished():
    players = (
        "qb1",
        "rb1",
        "rb2",
        "rb3",
        "wr1",
        "wr2",
        "wr3",
        "te1",
        "te2",
        "q1",
        "out1",
    )
    starters = ("qb1", "rb1", "rb2", "wr1", "wr2", "te1", "wr3")

    summary = analyze_roster_health(
        _league(players=players, starters=starters),
        CATALOG,
    )

    assert summary.status == NEEDS_ATTENTION
    assert any(
        row.code == "PLAYER_QUESTIONABLE"
        and row.player_name == "Questionable Player"
        for row in summary.issues
    )
    assert any(
        row.code == "PLAYER_UNAVAILABLE"
        and row.player_name == "Out Player"
        for row in summary.issues
    )


def test_fantasy_hq_page_exposes_roster_health_tab():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Roster Health" in page
    assert "analyze_roster_health" in page
