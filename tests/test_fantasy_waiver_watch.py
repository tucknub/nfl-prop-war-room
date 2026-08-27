from __future__ import annotations

from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.sleeper import SleeperTrendingPlayer
from src.fantasy.waiver_watch import build_sleeper_waiver_watch


def _league(
    league_id: str,
    name: str,
    *,
    my_players=(),
    other_players=(),
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
                starters=(),
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
        ownership_ready=True,
    )


CATALOG = {
    "p1": {
        "full_name": "Trending Free Agent",
        "position": "WR",
        "team": "IND",
        "status": "Active",
    },
    "p2": {
        "full_name": "Opponent Player",
        "position": "RB",
        "team": "HOU",
        "status": "Active",
    },
    "p3": {
        "full_name": "My Other Player",
        "position": "TE",
        "team": "DET",
        "injury_status": "Questionable",
    },
}


def test_waiver_watch_filters_to_selected_league_availability():
    leagues = (
        _league("l1", "Papa John's", other_players=("p2",)),
        _league("l2", "Franchise", my_players=("p3",)),
    )
    trends = (
        SleeperTrendingPlayer(player_id="p2", count=100),
        SleeperTrendingPlayer(player_id="p1", count=80),
        SleeperTrendingPlayer(player_id="p3", count=60),
    )

    rows = build_sleeper_waiver_watch(
        leagues,
        selected_league_id="l1",
        trends=trends,
        player_catalog=CATALOG,
    )

    assert [row.sleeper_player_id for row in rows] == ["p1", "p3"]
    assert rows[0].trend_count == 80
    assert rows[1].mine_elsewhere == ("Franchise",)
    assert rows[1].injury_status == "Questionable"


def test_waiver_watch_sorts_by_trending_add_count():
    leagues = (_league("l1", "Papa John's"),)
    trends = (
        SleeperTrendingPlayer(player_id="p1", count=10),
        SleeperTrendingPlayer(player_id="p3", count=50),
    )

    rows = build_sleeper_waiver_watch(
        leagues,
        selected_league_id="l1",
        trends=trends,
        player_catalog=CATALOG,
    )

    assert [row.sleeper_player_id for row in rows] == ["p3", "p1"]


def test_waiver_watch_requires_selected_league_in_scan():
    leagues = (_league("l1", "Papa John's"),)

    try:
        build_sleeper_waiver_watch(
            leagues,
            selected_league_id="missing",
            trends=(),
            player_catalog=CATALOG,
        )
    except ValueError as exc:
        assert "not present" in str(exc)
    else:
        raise AssertionError("missing selected league must fail")


def test_fantasy_hq_page_exposes_waiver_watch():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Waiver Watch" in page
    assert "build_sleeper_waiver_watch" in page
    assert "Trending data provided by Sleeper" in page
