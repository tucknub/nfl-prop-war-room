from __future__ import annotations

import pytest

from src.fantasy.free_agents import find_live_free_agents
from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster


CATALOG = {
    "p1": {
        "full_name": "Rostered Runner",
        "position": "RB",
        "team": "IND",
        "status": "Active",
        "active": True,
    },
    "p2": {
        "full_name": "Opponent Wideout",
        "position": "WR",
        "team": "HOU",
        "status": "Active",
        "active": True,
    },
    "p3": {
        "full_name": "Available Runner",
        "position": "RB",
        "team": "DET",
        "status": "Active",
        "active": True,
    },
    "p4": {
        "full_name": "Available Tight End",
        "position": "TE",
        "team": "KC",
        "injury_status": "Questionable",
        "active": True,
    },
    "p5": {
        "full_name": "Inactive Wideout",
        "position": "WR",
        "team": "FA",
        "status": "Inactive",
        "active": False,
    },
    "p6": {
        "full_name": "Retired Quarterback",
        "position": "QB",
        "team": "FA",
        "status": "Retired",
    },
    "p7": {
        "full_name": "Stale Inactive Runner",
        "position": "RB",
        "team": "FA",
        "status": "Inactive",
        "active": True,
    },
    "coach": {
        "full_name": "Not A Fantasy Player",
        "position": "HC",
        "team": "IND",
        "status": "Active",
        "active": True,
    },
}


def _league(
    league_id: str,
    name: str,
    *,
    my_players=(),
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
            roster_positions=("QB", "RB", "WR", "TE", "FLEX", "BN"),
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
                starters=tuple(my_players[:1]),
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
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def test_free_agents_exclude_any_rostered_player():
    selected = _league(
        "selected",
        "Selected",
        my_players=("p1",),
        other_players=("p2",),
    )

    rows = find_live_free_agents(selected, CATALOG)

    assert [row.sleeper_player_id for row in rows] == ["p3", "p4"]
    assert all(row.sleeper_player_id not in {"p1", "p2"} for row in rows)
    assert all(row.sleeper_player_id not in {"p5", "p6", "p7", "coach"} for row in rows)


def test_free_agents_flag_players_rostered_by_me_elsewhere_first():
    selected = _league(
        "selected",
        "Selected",
        my_players=("p1",),
        other_players=("p2",),
    )
    other = _league(
        "other",
        "Franchise",
        my_players=("p3",),
    )

    rows = find_live_free_agents(
        selected,
        CATALOG,
        all_leagues=(selected, other),
    )

    assert rows[0].sleeper_player_id == "p3"
    assert rows[0].mine_elsewhere == ("Franchise",)
    assert rows[0].familiar is True
    assert rows[1].mine_elsewhere == ()


def test_free_agent_position_query_and_familiar_only_filters():
    selected = _league("selected", "Selected")
    other = _league("other", "Other", my_players=("p3",))

    rb_rows = find_live_free_agents(
        selected,
        CATALOG,
        all_leagues=(selected, other),
        position="RB",
    )
    assert [row.sleeper_player_id for row in rb_rows] == ["p3", "p1"]

    search_rows = find_live_free_agents(
        selected,
        CATALOG,
        query="tight",
    )
    assert [row.sleeper_player_id for row in search_rows] == ["p4"]
    assert search_rows[0].status == "Questionable"

    familiar = find_live_free_agents(
        selected,
        CATALOG,
        all_leagues=(selected, other),
        mine_elsewhere_only=True,
    )
    assert [row.sleeper_player_id for row in familiar] == ["p3"]


def test_free_agent_availability_fails_closed_when_ownership_not_ready():
    league = _league(
        "predraft",
        "Pre Draft",
        ownership_ready=False,
    )

    with pytest.raises(ValueError, match="unsafe"):
        find_live_free_agents(league, CATALOG)


@pytest.mark.parametrize("position", ["DL", "SUPERFLEX"])
def test_free_agent_position_rejects_unsupported_filter(position):
    league = _league("selected", "Selected")

    with pytest.raises(ValueError, match="supported"):
        find_live_free_agents(league, CATALOG, position=position)


def test_free_agent_limit_is_bounded():
    league = _league("selected", "Selected")

    with pytest.raises(ValueError, match="1 to 500"):
        find_live_free_agents(league, CATALOG, limit=0)
    with pytest.raises(ValueError, match="1 to 500"):
        find_live_free_agents(league, CATALOG, limit=501)


def test_fantasy_hq_exposes_free_agent_explorer():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert '"Waiver Watch"' in page
    assert "Search all available players" in page
    assert "Only players I roster elsewhere" in page
    assert "find_live_free_agents" in page
