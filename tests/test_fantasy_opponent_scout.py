from __future__ import annotations

import pytest

from src.fantasy.models import (
    FantasyLeagueState,
    LeagueRules,
    Manager,
    MatchupTeam,
    Roster,
)
from src.fantasy.opponent_scout import build_opponent_scout


CATALOG = {
    "me1": {
        "full_name": "My Quarterback",
        "position": "QB",
        "team": "IND",
        "status": "Active",
    },
    "o1": {
        "full_name": "Opponent Quarterback",
        "position": "QB",
        "team": "BUF",
        "status": "Active",
    },
    "o2": {
        "full_name": "Opponent Runner",
        "position": "RB",
        "team": "DET",
        "injury_status": "Questionable",
    },
    "o3": {
        "full_name": "Opponent Wideout",
        "position": "WR",
        "team": "PHI",
        "status": "Active",
    },
    "o4": {
        "full_name": "Opponent Tight End",
        "position": "TE",
        "team": "KC",
        "injury_status": "Out",
    },
    "o5": {
        "full_name": "Opponent Bench",
        "position": "RB",
        "team": "GB",
        "status": "Active",
    },
    "o6": {
        "full_name": "Opponent IR",
        "position": "WR",
        "team": "SF",
        "injury_status": "IR",
    },
}


def _league() -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-1",
        name="Papa John's",
        season="2026",
        status="in_season",
        team_count=12,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "TE", "BN", "BN", "IR"),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Tuck",
                team_name="My Team",
            ),
            Manager(
                platform_user_id="opp",
                display_name="Opponent",
                team_name="The Villains",
            ),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=("me1",),
                starters=("me1",),
                reserve=(),
                taxi=(),
                settings={
                    "wins": 5,
                    "losses": 1,
                    "fpts": 650,
                    "fpts_decimal": 12,
                },
            ),
            Roster(
                platform_roster_id="2",
                platform_user_id="opp",
                players=("o1", "o2", "o3", "o4", "o5", "o6"),
                starters=("o1", "o2", "o3", "o4"),
                reserve=("o6",),
                taxi=(),
                settings={
                    "wins": 4,
                    "losses": 2,
                    "fpts": 612,
                    "fpts_decimal": 34,
                },
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _matchups(*, opponent_starters=("o1", "o2", "o3", "o4")):
    return (
        MatchupTeam(
            week=1,
            platform_roster_id="1",
            matchup_id="7",
            players=("me1",),
            starters=("me1",),
            points=80.5,
            custom_points=None,
            players_points={"me1": 20.1},
        ),
        MatchupTeam(
            week=1,
            platform_roster_id="2",
            matchup_id="7",
            players=("o1", "o2", "o3", "o4", "o5", "o6"),
            starters=tuple(opponent_starters),
            points=76.25,
            custom_points=None,
            players_points={
                "o1": 22.0,
                "o2": 11.5,
                "o3": 18.75,
                "o4": 0,
                "o5": 4.0,
                "o6": 0,
            },
        ),
    )


def test_opponent_scout_identifies_weekly_opponent_and_facts():
    scout = build_opponent_scout(
        _league(),
        _matchups(),
        week=1,
        player_catalog=CATALOG,
    )

    assert scout is not None
    assert scout.opponent_roster_id == "2"
    assert scout.opponent_name == "The Villains"
    assert scout.opponent_record == "4-2"
    assert scout.opponent_points_for == 612.34
    assert scout.my_matchup_points == 80.5
    assert scout.opponent_matchup_points == 76.25
    assert scout.open_starter_slots == 0
    assert scout.position_counts == {
        "QB": 1,
        "RB": 2,
        "TE": 1,
        "WR": 2,
    }


def test_opponent_scout_marks_starter_status_and_bench_slots():
    scout = build_opponent_scout(
        _league(),
        _matchups(),
        week=1,
        player_catalog=CATALOG,
    )

    assert scout is not None
    assert [row.name for row in scout.starters] == [
        "Opponent Quarterback",
        "Opponent Runner",
        "Opponent Wideout",
        "Opponent Tight End",
    ]
    assert all(row.fantasy_slot == "Starter" for row in scout.starters)
    assert scout.starters[0].points == 22.0
    assert scout.serious_starter_count == 1
    assert scout.questionable_starter_count == 1
    assert scout.starter_alert_count == 2

    bench_by_name = {row.name: row for row in scout.bench}
    assert bench_by_name["Opponent Bench"].fantasy_slot == "Bench"
    assert bench_by_name["Opponent IR"].fantasy_slot == "IR"
    assert bench_by_name["Opponent IR"].serious_status is True


def test_opponent_scout_reports_open_starter_slots():
    scout = build_opponent_scout(
        _league(),
        _matchups(opponent_starters=("o1", "o2", "o3")),
        week=1,
        player_catalog=CATALOG,
    )

    assert scout is not None
    assert scout.open_starter_slots == 1


def test_opponent_scout_returns_none_without_current_pairing():
    rows = (
        MatchupTeam(
            week=1,
            platform_roster_id="1",
            matchup_id=None,
            players=("me1",),
            starters=("me1",),
            points=0,
            custom_points=None,
        ),
    )

    assert (
        build_opponent_scout(
            _league(),
            rows,
            week=1,
            player_catalog=CATALOG,
        )
        is None
    )


def test_opponent_scout_rejects_contradictory_multiple_opponents():
    rows = (
        *_matchups(),
        MatchupTeam(
            week=1,
            platform_roster_id="3",
            matchup_id="7",
            players=(),
            starters=(),
            points=0,
            custom_points=None,
        ),
    )

    with pytest.raises(ValueError, match="multiple opponent"):
        build_opponent_scout(
            _league(),
            rows,
            week=1,
            player_catalog=CATALOG,
        )


def test_opponent_scout_rejects_invalid_week():
    with pytest.raises(ValueError, match="positive integer"):
        build_opponent_scout(
            _league(),
            _matchups(),
            week=0,
            player_catalog=CATALOG,
        )


def test_fantasy_hq_exposes_opponent_scout():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert '"Opponent Scout"' in page
    assert "build_opponent_scout" in page
    assert "Starter availability" in page
    assert "Opponent position depth" in page
