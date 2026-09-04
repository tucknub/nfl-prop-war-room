from __future__ import annotations

import pytest

from src.fantasy.market_trade import (
    ACCEPT,
    GOOD_FOR_BOTH,
    HARD_SELL,
    INCOMPLETE,
    analyze_market_trade,
)
from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster


def _league(*, mine, partner, starter_positions=("QB", "RB", "WR")):
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-1",
        name="Trade Test",
        season="2026",
        status="in_season",
        team_count=10,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=(*starter_positions, "BN", "BN", "BN"),
            scoring_settings={
                "pass_yd": 0.04,
                "pass_td": 4.0,
                "pass_int": -2.0,
                "rush_yd": 0.1,
                "rush_td": 6.0,
                "rec_yd": 0.1,
                "rec": 1.0,
                "rec_td": 6.0,
            },
            waiver_budget=100,
        ),
        draft=None,
        managers=(
            Manager("me", "Me", "My Team"),
            Manager("other", "Other", "Partner Team"),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=tuple(mine),
                starters=tuple(mine[: len(starter_positions)]),
                reserve=(),
                taxi=(),
                settings={},
            ),
            Roster(
                platform_roster_id="2",
                platform_user_id="other",
                players=tuple(partner),
                starters=tuple(partner[: len(starter_positions)]),
                reserve=(),
                taxi=(),
                settings={},
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _catalog(specs):
    return {
        player_id: {
            "full_name": name,
            "position": position,
            "fantasy_positions": [position],
            "team": "IND",
            "active": True,
        }
        for player_id, name, position, _points in specs
    }


def _row(*, player, market, line, book="DK", over=-110, under=-110):
    return {
        "event_id": "week1",
        "commence_time": "2026-09-13T17:00:00Z",
        "away_team": "IND",
        "home_team": "HOU",
        "book": book,
        "player": player,
        "market": market,
        "market_key": f"player_{market}",
        "line": line,
        "over_price": over,
        "under_price": under,
        "over_implied_prob": None,
        "under_implied_prob": None,
    }


def _full_rows(name, position, target_points):
    # Use four market families so coverage is FULL. Yardage is adjusted to
    # make the aggregate baseline approximately the requested target.
    if position == "QB":
        pass_yards = max(0.0, (target_points - 5.5) / 0.04)
        markets = (
            ("passing_yards", pass_yards),
            ("passing_tds", 1.0),
            ("interceptions", 0.5),
            ("rushing_yards", 25.0),
        )
    elif position == "RB":
        rush_yards = max(0.0, (target_points - 5.5) / 0.1)
        markets = (
            ("rushing_yards", rush_yards),
            ("receiving_yards", 10.0),
            ("receptions", 1.5),
            ("anytime_td", 0.5),
        )
    else:
        rec_yards = max(0.0, (target_points - 7.0) / 0.1)
        markets = (
            ("receiving_yards", rec_yards),
            ("receptions", 3.0),
            ("rushing_yards", 10.0),
            ("anytime_td", 0.5),
        )

    rows = []
    for market, line in markets:
        rows.append(_row(player=name, market=market, line=line, book="DK"))
        rows.append(_row(player=name, market=market, line=line, book="FD"))
    return rows


def _thin_rows(name):
    return [
        _row(player=name, market="receiving_yards", line=65.5, book="DK"),
        _row(player=name, market="receiving_yards", line=65.5, book="FD"),
    ]


def _fixture(specs):
    catalog = _catalog(specs)
    rows = []
    for _player_id, name, position, points in specs:
        rows.extend(_full_rows(name, position, points))
    return catalog, rows


def test_trade_analyzer_finds_true_two_way_lineup_improvement():
    specs = [
        ("mq", "My QB", "QB", 18.0),
        ("mr1", "My RB One", "RB", 13.0),
        ("mr2", "My RB Two", "RB", 12.0),
        ("mw", "My WR", "WR", 8.0),
        ("pq", "Partner QB", "QB", 17.0),
        ("pr", "Partner RB", "RB", 7.0),
        ("pw1", "Partner WR One", "WR", 15.0),
        ("pw2", "Partner WR Two", "WR", 14.0),
    ]
    catalog, rows = _fixture(specs)
    league = _league(
        mine=("mq", "mr1", "mw", "mr2"),
        partner=("pq", "pr", "pw1", "pw2"),
    )

    result = analyze_market_trade(
        league,
        catalog,
        rows,
        partner_roster_id="2",
        give_player_ids=("mr2",),
        receive_player_ids=("pw2",),
    )

    assert result.verdict == ACCEPT
    assert result.partner_fit == GOOD_FOR_BOTH
    assert result.my_team.lineup_delta > 5.0
    assert result.partner_team.lineup_delta > 4.0
    assert result.raw_asset_delta is not None
    assert result.raw_asset_delta > 1.0
    assert result.mutual_lineup_gain is True


def test_trade_analyzer_flags_a_good_deal_for_me_as_hard_sell_for_partner():
    specs = [
        ("mq", "My QB", "QB", 18.0),
        ("mr", "My RB", "RB", 12.0),
        ("mw", "My WR", "WR", 8.0),
        ("pq", "Partner QB", "QB", 17.0),
        ("pr", "Partner RB", "RB", 9.0),
        ("pw", "Partner WR", "WR", 15.0),
    ]
    catalog, rows = _fixture(specs)
    league = _league(
        mine=("mq", "mr", "mw"),
        partner=("pq", "pr", "pw"),
    )

    result = analyze_market_trade(
        league,
        catalog,
        rows,
        partner_roster_id="2",
        give_player_ids=("mw",),
        receive_player_ids=("pw",),
    )

    assert result.verdict == ACCEPT
    assert result.partner_fit == HARD_SELL
    assert result.my_team.lineup_delta > 6.0
    assert result.partner_team.lineup_delta < -6.0


def test_trade_analyzer_supports_two_for_one_and_accounts_for_roster_consolidation():
    specs = [
        ("mq", "My QB", "QB", 18.0),
        ("mr", "My RB", "RB", 12.0),
        ("mw1", "My WR One", "WR", 10.0),
        ("mw2", "My WR Two", "WR", 9.0),
        ("pq", "Partner QB", "QB", 17.0),
        ("pr", "Partner RB", "RB", 10.0),
        ("pw", "Partner WR Star", "WR", 16.0),
    ]
    catalog, rows = _fixture(specs)
    league = _league(
        mine=("mq", "mr", "mw1", "mw2"),
        partner=("pq", "pr", "pw"),
    )

    result = analyze_market_trade(
        league,
        catalog,
        rows,
        partner_roster_id="2",
        give_player_ids=("mw1", "mw2"),
        receive_player_ids=("pw",),
    )

    assert len(result.give_players) == 2
    assert len(result.receive_players) == 1
    assert result.my_team.roster_size_after == result.my_team.roster_size_before - 1
    assert result.partner_team.roster_size_after == result.partner_team.roster_size_before + 1
    # The optimizer correctly uses only one WR starter slot, so consolidation
    # can improve the starting lineup despite sending two assets.
    assert result.my_team.lineup_delta > 5.0


def test_trade_analyzer_refuses_verdict_when_a_traded_asset_is_thin():
    specs = [
        ("mq", "My QB", "QB", 18.0),
        ("mr", "My RB", "RB", 12.0),
        ("mw", "My WR", "WR", 10.0),
        ("pq", "Partner QB", "QB", 17.0),
        ("pr", "Partner RB", "RB", 10.0),
        ("pw", "Partner WR", "WR", 15.0),
    ]
    catalog, rows = _fixture(specs)
    rows = [row for row in rows if row["player"] != "Partner WR"]
    rows.extend(_thin_rows("Partner WR"))
    league = _league(
        mine=("mq", "mr", "mw"),
        partner=("pq", "pr", "pw"),
    )

    result = analyze_market_trade(
        league,
        catalog,
        rows,
        partner_roster_id="2",
        give_player_ids=("mw",),
        receive_player_ids=("pw",),
    )

    assert result.verdict == INCOMPLETE
    assert result.traded_assets_fully_usable is False
    assert "Partner WR" in result.reason


def test_trade_analyzer_enforces_live_ownership():
    specs = [
        ("mq", "My QB", "QB", 18.0),
        ("mw", "My WR", "WR", 10.0),
        ("pq", "Partner QB", "QB", 17.0),
        ("pw", "Partner WR", "WR", 15.0),
    ]
    catalog, rows = _fixture(specs)
    league = _league(
        mine=("mq", "mw"),
        partner=("pq", "pw"),
        starter_positions=("QB", "WR"),
    )

    with pytest.raises(ValueError, match="give player"):
        analyze_market_trade(
            league,
            catalog,
            rows,
            partner_roster_id="2",
            give_player_ids=("pw",),
            receive_player_ids=("mw",),
        )


def test_trade_analyzer_obeys_flex_eligibility_in_post_trade_lineup():
    specs = [
        ("mq", "My QB", "QB", 18.0),
        ("mr", "My RB", "RB", 12.0),
        ("mw", "My WR", "WR", 10.0),
        ("pq", "Partner QB", "QB", 17.0),
        ("pr", "Partner RB", "RB", 9.0),
        ("pw", "Partner WR", "WR", 14.0),
    ]
    catalog, rows = _fixture(specs)
    league = _league(
        mine=("mq", "mr", "mw"),
        partner=("pq", "pr", "pw"),
        starter_positions=("QB", "FLEX"),
    )

    result = analyze_market_trade(
        league,
        catalog,
        rows,
        partner_roster_id="2",
        give_player_ids=("mr",),
        receive_player_ids=("pw",),
    )

    assert result.my_team.post_trade.covered_starters == 2
    assert any(
        slot == "FLEX" and name == "Partner WR"
        for slot, name, _points in result.my_team.post_trade.assignments
    )


def test_fantasy_hq_exposes_market_assisted_trade_analyzer():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Market-Assisted Trade Analyzer" in page
    assert "analyze_market_trade" in page
    assert "Analyze trade" in page
    assert "My baseline delta" in page
    assert "Partner baseline delta" in page
    assert "Current-week partner fit" in page
    assert "not an accept/decline trade verdict" in page
