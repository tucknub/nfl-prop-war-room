from __future__ import annotations

from src.fantasy.action_center import build_fantasy_action_center
from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.roster_health import NEEDS_ATTENTION, PRE_DRAFT, READY, WATCH


CATALOG = {
    "qb1": {"full_name": "QB One", "position": "QB", "status": "Active"},
    "rb1": {"full_name": "RB One", "position": "RB", "status": "Active"},
    "rb2": {"full_name": "RB Two", "position": "RB", "status": "Active"},
    "wr1": {"full_name": "WR One", "position": "WR", "status": "Active"},
    "wr2": {"full_name": "WR Two", "position": "WR", "status": "Active"},
    "q1": {
        "full_name": "Questionable WR",
        "position": "WR",
        "injury_status": "Questionable",
    },
}


def _league(
    league_id: str,
    name: str,
    *,
    my_players=(),
    starters=(),
    other_players=(),
    ownership_ready=True,
) -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=league_id,
        name=name,
        season="2026",
        status="in_season",
        team_count=12,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "FLEX", "BN"),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Me",
                team_name=f"{name} Mine",
            ),
            Manager(
                platform_user_id="opp",
                display_name="Opponent",
                team_name=f"{name} Opp",
            ),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=tuple(my_players),
                starters=tuple(starters),
                reserve=(),
                taxi=(),
            ),
            Roster(
                platform_roster_id="2",
                platform_user_id="opp",
                players=tuple(other_players),
                starters=(),
                reserve=(),
                taxi=(),
            ),
        ),
        rules_ready=True,
        draft_ready=False,
        ownership_ready=ownership_ready,
    )


def test_action_center_summarizes_all_leagues_by_priority():
    ready = _league(
        "ready",
        "Ready League",
        my_players=("qb1", "rb1", "rb2", "wr1", "wr2"),
        starters=("qb1", "rb1", "wr1", "rb2"),
    )
    watch = _league(
        "watch",
        "Watch League",
        my_players=("qb1", "rb1", "wr1", "q1"),
        starters=("qb1", "rb1", "wr1", "q1"),
    )
    needs = _league(
        "needs",
        "Needs League",
        my_players=("qb1", "wr1"),
        starters=("qb1", "wr1"),
    )
    pre = _league("pre", "Pre Draft")

    result = build_fantasy_action_center(
        (ready, pre, watch, needs),
        CATALOG,
    )

    assert result.league_count == 4
    assert result.drafted_count == 3
    assert result.pre_draft_count == 1
    assert result.ready_count == 1
    assert result.watch_count == 1
    assert result.needs_attention_count == 1
    assert [row.status for row in result.leagues] == [
        NEEDS_ATTENTION,
        WATCH,
        READY,
        PRE_DRAFT,
    ]
    assert [row.league_name for row in result.action_leagues] == [
        "Needs League",
        "Watch League",
    ]


def test_action_center_includes_cross_league_opportunities():
    mine = _league(
        "mine",
        "My League",
        my_players=("qb1", "rb1", "rb2", "wr1"),
        starters=("qb1", "rb1", "wr1", "rb2"),
    )
    elsewhere = _league(
        "elsewhere",
        "Elsewhere",
        my_players=("wr2",),
        starters=("wr2",),
        other_players=("qb1",),
    )

    result = build_fantasy_action_center((mine, elsewhere), CATALOG)

    opportunity_by_player = {
        row.sleeper_player_id: row
        for row in result.cross_league_opportunities
    }
    assert result.opportunity_count >= 1
    assert "rb1" in opportunity_by_player
    assert opportunity_by_player["rb1"].mine_in == ("My League",)
    assert opportunity_by_player["rb1"].available_in == ("Elsewhere",)


def test_action_center_empty_input_is_safe():
    result = build_fantasy_action_center((), CATALOG)

    assert result.league_count == 0
    assert result.drafted_count == 0
    assert result.pre_draft_count == 0
    assert result.ready_count == 0
    assert result.watch_count == 0
    assert result.needs_attention_count == 0
    assert result.opportunity_count == 0
    assert result.action_leagues == ()


def test_fantasy_hq_exposes_all_leagues_action_center():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "All-Leagues Action Center" in page
    assert "build_fantasy_action_center" in page
    assert "Leagues needing attention" in page
    assert "Cross-league opportunities" in page
