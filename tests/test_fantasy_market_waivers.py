from __future__ import annotations

import pytest

from src.fantasy.lineup_check import build_lineup_check
from src.fantasy.market_waivers import (
    HIGH,
    LOW,
    build_market_ranked_waivers,
)
from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.sleeper import SleeperTrendingPlayer


CATALOG = {
    "qb1": {
        "full_name": "Quarter Back",
        "position": "QB",
        "fantasy_positions": ["QB"],
        "team": "IND",
        "status": "Active",
        "active": True,
    },
    "rb1": {
        "full_name": "Roster Running Back",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "IND",
        "status": "Active",
        "active": True,
    },
    "wr1": {
        "full_name": "Roster Wideout",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "IND",
        "status": "Active",
        "active": True,
    },
    "te1": {
        "full_name": "Roster Tight End",
        "position": "TE",
        "fantasy_positions": ["TE"],
        "team": "IND",
        "status": "Active",
        "active": True,
    },
    "rb2": {
        "full_name": "Market Runner",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "DET",
        "status": "Active",
        "active": True,
    },
    "wr2": {
        "full_name": "Market Wideout",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "CIN",
        "status": "Active",
        "active": True,
    },
    "wr3": {
        "full_name": "Volume Wideout",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "BUF",
        "status": "Active",
        "active": True,
    },
}


def _league(
    *,
    scoring=None,
    starters=("qb1", "0", "wr1", "0"),
    my_players=("qb1", "rb1", "wr1"),
    other_players=(),
    ownership_ready=True,
):
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="selected",
        name="Papa John's",
        season="2026",
        status="in_season",
        team_count=12,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "FLEX", "BN"),
            scoring_settings=scoring
            or {
                "pass_yd": 0.04,
                "pass_td": 4.0,
                "pass_int": -2.0,
                "rush_yd": 0.1,
                "rush_td": 6.0,
                "rec": 1.0,
                "rec_yd": 0.1,
                "rec_td": 6.0,
            },
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Me",
                team_name="Mine",
            ),
            Manager(
                platform_user_id="opp",
                display_name="Opponent",
                team_name="Other",
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
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def _row(player, market, line, *, book="DK", event_id="e1"):
    return {
        "event_id": event_id,
        "commence_time": "2026-09-13T17:00:00Z",
        "away_team": "IND",
        "home_team": "HOU",
        "book": book,
        "player": player,
        "market": market,
        "market_key": f"player_{market}",
        "line": line,
        "over_price": -110,
        "under_price": -110,
        "over_implied_prob": None,
        "under_implied_prob": None,
    }


def _wr_rows(player, *, rec=5.5, rec_yd=65.5, td=True):
    rows = [
        _row(player, "receptions", rec, book="DK"),
        _row(player, "receptions", rec, book="FD"),
        _row(player, "receiving_yards", rec_yd, book="DK"),
        _row(player, "receiving_yards", rec_yd, book="FD"),
    ]
    if td:
        rows.extend(
            [
                _row(player, "anytime_td", 0.5, book="DK"),
                _row(player, "anytime_td", 0.5, book="FD"),
            ]
        )
    return rows


def _rb_rows(player, *, rush_yd=65.5, rec=2.5, rec_yd=20.5):
    return [
        _row(player, "rushing_yards", rush_yd, book="DK"),
        _row(player, "rushing_yards", rush_yd, book="FD"),
        _row(player, "receptions", rec, book="DK"),
        _row(player, "receptions", rec, book="FD"),
        _row(player, "receiving_yards", rec_yd, book="DK"),
        _row(player, "receiving_yards", rec_yd, book="FD"),
    ]


def test_market_ranked_waivers_prioritize_high_need_and_open_slot_gain():
    league = _league()
    lineup = build_lineup_check(league, CATALOG)
    assert lineup is not None

    board = build_market_ranked_waivers(
        league,
        lineup,
        CATALOG,
        [
            *_rb_rows("Market Runner", rush_yd=72.5, rec=3.5, rec_yd=24.5),
            *_wr_rows("Market Wideout", rec=6.5, rec_yd=80.5),
        ],
        trends=(
            SleeperTrendingPlayer(player_id="rb2", count=40),
            SleeperTrendingPlayer(player_id="wr2", count=500),
        ),
    )

    assert board.candidates
    assert all(row.need == HIGH for row in board.candidates)
    runner = next(row for row in board.candidates if row.sleeper_player_id == "rb2")
    assert runner.target_slot == "RB"
    assert runner.replacement_player == "Open slot"
    assert runner.replacement_fantasy_points == 0.0
    assert runner.expected_lineup_improvement == runner.market_fantasy_points
    assert runner.trend_count == 40


def test_market_ranked_waivers_find_real_upgrade_on_healthy_lineup():
    league = _league(
        starters=("qb1", "rb1", "wr1", "te1"),
        my_players=("qb1", "rb1", "wr1", "te1"),
    )
    lineup = build_lineup_check(league, CATALOG)
    assert lineup is not None

    board = build_market_ranked_waivers(
        league,
        lineup,
        CATALOG,
        [
            *_rb_rows("Roster Running Back", rush_yd=55.5, rec=2.0, rec_yd=15.5),
            *_wr_rows("Roster Wideout", rec=4.0, rec_yd=48.5),
            *_wr_rows("Market Wideout", rec=7.0, rec_yd=88.5),
            *_wr_rows("Roster Tight End", rec=3.0, rec_yd=34.5),
        ],
    )

    candidate = next(
        row for row in board.candidates if row.sleeper_player_id == "wr2"
    )
    assert candidate.need == LOW
    assert candidate.expected_lineup_improvement is not None
    assert candidate.expected_lineup_improvement >= 1.0
    assert candidate.replacement_fantasy_points is not None
    assert candidate.target_slot in {"WR", "FLEX"}


def test_market_ranked_waivers_use_league_ppr_scoring_for_ordering():
    standard = _league(
        scoring={"rec": 0.0, "rec_yd": 0.1},
        starters=("qb1", "rb1", "0", "te1"),
        my_players=("qb1", "rb1", "te1"),
    )
    ppr = _league(
        scoring={"rec": 1.0, "rec_yd": 0.1},
        starters=("qb1", "rb1", "0", "te1"),
        my_players=("qb1", "rb1", "te1"),
    )
    rows = [
        *_wr_rows("Market Wideout", rec=2.0, rec_yd=70.0),
        *_wr_rows("Volume Wideout", rec=5.0, rec_yd=50.0),
    ]

    standard_lineup = build_lineup_check(standard, CATALOG)
    ppr_lineup = build_lineup_check(ppr, CATALOG)
    assert standard_lineup is not None
    assert ppr_lineup is not None

    standard_board = build_market_ranked_waivers(
        standard,
        standard_lineup,
        CATALOG,
        rows,
    )
    ppr_board = build_market_ranked_waivers(
        ppr,
        ppr_lineup,
        CATALOG,
        rows,
    )

    assert standard_board.candidates[0].sleeper_player_id == "wr2"
    assert ppr_board.candidates[0].sleeper_player_id == "wr3"


def test_market_ranked_waivers_exclude_thin_market_coverage():
    league = _league()
    lineup = build_lineup_check(league, CATALOG)
    assert lineup is not None

    board = build_market_ranked_waivers(
        league,
        lineup,
        CATALOG,
        [
            _row("Market Wideout", "receiving_yards", 75.5, book="DK"),
            _row("Market Wideout", "receiving_yards", 76.5, book="FD"),
        ],
    )

    assert all(row.sleeper_player_id != "wr2" for row in board.candidates)


def test_market_ranked_waivers_only_include_actual_selected_league_free_agents():
    league = _league(other_players=("wr2",))
    lineup = build_lineup_check(league, CATALOG)
    assert lineup is not None

    board = build_market_ranked_waivers(
        league,
        lineup,
        CATALOG,
        _wr_rows("Market Wideout", rec=7.0, rec_yd=90.0),
    )

    assert all(row.sleeper_player_id != "wr2" for row in board.candidates)


def test_market_ranked_waivers_fail_closed_without_ownership():
    league = _league(ownership_ready=False)
    lineup = build_lineup_check(league, CATALOG)
    assert lineup is not None

    with pytest.raises(ValueError, match="unsafe"):
        build_market_ranked_waivers(
            league,
            lineup,
            CATALOG,
            _wr_rows("Market Wideout"),
        )


def test_fantasy_hq_exposes_market_ranked_waivers():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Market-Ranked Waivers" in page
    assert "build_market_ranked_waivers" in page
    assert "Expected lineup improvement" in page
    assert "Market baseline" in page
    assert "Need" in page
