from __future__ import annotations

from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.player_intelligence import build_player_intelligence_card
from src.fantasy.sleeper import SleeperTrendingPlayer


CATALOG = {
    "p1": {
        "full_name": "Player One",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "IND",
        "status": "Active",
        "age": 25,
        "years_exp": 3,
        "depth_chart_order": 1,
        "depth_chart_position": "RB",
        "active": True,
    },
    "p2": {
        "full_name": "Player Two",
        "position": "WR",
        "team": "DET",
        "status": "Active",
        "active": True,
    },
    "p3": {
        "full_name": "Player Three",
        "position": "TE",
        "team": "KC",
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
        team_count=2,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "RB", "WR", "TE", "FLEX", "BN"),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager("me", "Me", f"{name} Mine"),
            Manager("opp", "Opp", f"{name} Opp"),
        ),
        rosters=(
            Roster(
                "1",
                "me",
                tuple(my_players),
                tuple(my_players[:1]),
                (),
                (),
            ),
            Roster(
                "2",
                "opp",
                tuple(other_players),
                tuple(other_players[:1]),
                (),
                (),
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def test_player_intelligence_combines_metadata_trends_and_market_fit():
    selected = _league("l1", "League One")
    other = _league("l2", "League Two", my_players=("p1",))

    card = build_player_intelligence_card(
        selected,
        (selected, other),
        "p1",
        CATALOG,
        add_trends=(SleeperTrendingPlayer("p1", 120),),
        drop_trends=(SleeperTrendingPlayer("p1", 25),),
    )

    assert card.player_name == "Player One"
    assert card.positions == ("RB",)
    assert card.nfl_team == "IND"
    assert card.age == 25
    assert card.years_exp == 3
    assert card.depth_chart_order == 1
    assert card.depth_chart_position == "RB"
    assert card.selected_league_status == "AVAILABLE"
    assert card.is_available_here is True
    assert card.my_league_count == 1
    assert card.available_league_count == 1
    assert card.add_trend_count == 120
    assert card.drop_trend_count == 25
    assert card.trend_delta == 95
    assert card.high_fit_team_count >= 1


def test_player_intelligence_reports_owner_and_roster_slot():
    selected = _league("l1", "League One", other_players=("p1",))

    card = build_player_intelligence_card(
        selected,
        (selected,),
        "p1",
        CATALOG,
    )

    assert card.selected_league_status == "OTHER"
    assert card.selected_league_owner == "League One Opp"
    assert card.selected_league_slot == "Starter"
    assert card.opponent_owned_league_count == 1
    assert card.available_league_count == 0


def test_player_intelligence_tracks_unknown_cross_league_ownership():
    selected = _league("l1", "League One")
    unready = _league("l2", "League Two", ownership_ready=False)

    card = build_player_intelligence_card(
        selected,
        (selected, unready),
        "p1",
        CATALOG,
    )

    assert card.available_league_count == 1
    assert card.unknown_league_count == 1


def test_player_intelligence_fails_closed_when_selected_availability_is_unknown():
    selected = _league("l1", "League One", ownership_ready=False)

    try:
        build_player_intelligence_card(
            selected,
            (selected,),
            "p1",
            CATALOG,
        )
    except ValueError as exc:
        assert "unsafe" in str(exc)
    else:
        raise AssertionError("selected league availability must fail closed")


def test_fantasy_hq_exposes_player_intelligence_card():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Player Intelligence Card" in page
    assert "build_player_intelligence_card" in page
    assert "Sleeper adds · 48h" in page
    assert "Sleeper drops · 48h" in page
    assert "Depth chart" in page
    assert "My Sleeper leagues" in page
