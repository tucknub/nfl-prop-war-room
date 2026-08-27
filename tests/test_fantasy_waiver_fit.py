from __future__ import annotations

import pytest

from src.fantasy.lineup_check import build_lineup_check
from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.sleeper import SleeperTrendingPlayer
from src.fantasy.waiver_fit import build_roster_need_waiver_board


CATALOG = {
    "qb1": {
        "full_name": "QB One",
        "position": "QB",
        "fantasy_positions": ["QB"],
        "team": "IND",
        "status": "Active",
        "active": True,
    },
    "qb2": {
        "full_name": "QB Two",
        "position": "QB",
        "fantasy_positions": ["QB"],
        "team": "BUF",
        "status": "Active",
        "active": True,
    },
    "out_rb": {
        "full_name": "Out RB",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "MIA",
        "injury_status": "Out",
        "active": True,
    },
    "rb2": {
        "full_name": "Available RB",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "DET",
        "status": "Active",
        "active": True,
    },
    "rb_out": {
        "full_name": "Unavailable Free RB",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "NYJ",
        "injury_status": "Doubtful",
        "active": True,
    },
    "wr1": {
        "full_name": "WR One",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "PHI",
        "status": "Active",
        "active": True,
    },
    "wr2": {
        "full_name": "Available WR",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "CIN",
        "status": "Active",
        "active": True,
    },
    "q_wr": {
        "full_name": "Questionable Starter",
        "position": "WR",
        "fantasy_positions": ["WR"],
        "team": "LAR",
        "injury_status": "Questionable",
        "active": True,
    },
    "te1": {
        "full_name": "Available TE",
        "position": "TE",
        "fantasy_positions": ["TE"],
        "team": "KC",
        "status": "Active",
        "active": True,
    },
    "retired": {
        "full_name": "Retired RB",
        "position": "RB",
        "fantasy_positions": ["RB"],
        "team": "FA",
        "status": "Retired",
    },
    "hunter": {
        "full_name": "Dual Eligible",
        "position": "WR",
        "fantasy_positions": ["WR", "DB"],
        "team": "JAX",
        "status": "Active",
        "active": True,
    },
}


def _league(
    league_id: str,
    name: str,
    *,
    roster_positions=("QB", "RB", "WR", "FLEX", "BN"),
    my_players=("qb1", "out_rb", "wr1"),
    starters=("qb1", "out_rb", "wr1", "0"),
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
            roster_positions=tuple(roster_positions),
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
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def test_need_matches_prioritize_players_covering_more_action_slots():
    selected = _league("selected", "Selected")
    other = _league(
        "other",
        "Franchise",
        my_players=("rb2",),
        starters=("0", "rb2", "0", "0"),
    )
    lineup = build_lineup_check(selected, CATALOG)
    assert lineup is not None

    board = build_roster_need_waiver_board(
        selected,
        lineup,
        CATALOG,
        all_leagues=(selected, other),
        trends=(
            SleeperTrendingPlayer(player_id="te1", count=300),
            SleeperTrendingPlayer(player_id="rb2", count=100),
        ),
    )

    assert board.action_need_count == 2
    assert [row.label for row in board.needs] == ["RB", "FLEX"]
    assert board.matches[0].sleeper_player_id == "rb2"
    assert board.matches[0].action_slots == ("RB", "FLEX")
    assert board.matches[0].mine_elsewhere == ("Franchise",)
    assert board.matches[0].trend_count == 100

    te = next(row for row in board.matches if row.sleeper_player_id == "te1")
    assert te.action_slots == ("FLEX",)
    assert te.trend_count == 300


def test_questionable_starter_creates_watch_coverage_not_action_need():
    selected = _league(
        "selected",
        "Selected",
        my_players=("qb1", "rb2", "q_wr", "te1"),
        starters=("qb1", "rb2", "q_wr", "te1"),
    )
    lineup = build_lineup_check(selected, CATALOG)
    assert lineup is not None

    board = build_roster_need_waiver_board(
        selected,
        lineup,
        CATALOG,
    )

    assert board.action_need_count == 0
    assert board.watch_need_count == 1
    assert board.needs[0].label == "WR"
    wr = next(row for row in board.matches if row.sleeper_player_id == "wr2")
    assert wr.action_slots == ()
    assert wr.watch_slots == ("WR",)


def test_selected_league_rostered_and_serious_free_agents_are_excluded():
    selected = _league(
        "selected",
        "Selected",
        other_players=("rb2",),
    )
    lineup = build_lineup_check(selected, CATALOG)
    assert lineup is not None

    board = build_roster_need_waiver_board(
        selected,
        lineup,
        CATALOG,
    )

    ids = {row.sleeper_player_id for row in board.matches}
    assert "rb2" not in ids
    assert "rb_out" not in ids
    assert "retired" not in ids


def test_duplicate_need_slots_receive_stable_labels():
    selected = _league(
        "selected",
        "Selected",
        roster_positions=("QB", "RB", "RB", "BN"),
        my_players=("qb1",),
        starters=("qb1", "0", "0"),
    )
    lineup = build_lineup_check(selected, CATALOG)
    assert lineup is not None

    board = build_roster_need_waiver_board(
        selected,
        lineup,
        CATALOG,
    )

    assert [row.label for row in board.needs] == ["RB 1", "RB 2"]
    rb = next(row for row in board.matches if row.sleeper_player_id == "rb2")
    assert rb.action_slots == ("RB 1", "RB 2")


def test_multi_position_player_can_match_idp_flex_need():
    selected = _league(
        "selected",
        "Selected",
        roster_positions=("QB", "IDP_FLEX", "BN"),
        my_players=("qb1",),
        starters=("qb1", "0"),
    )
    lineup = build_lineup_check(selected, CATALOG)
    assert lineup is not None

    board = build_roster_need_waiver_board(
        selected,
        lineup,
        CATALOG,
    )

    hunter = next(
        row
        for row in board.matches
        if row.sleeper_player_id == "hunter"
    )
    assert hunter.action_slots == ("IDP_FLEX",)


def test_no_lineup_need_returns_empty_board():
    selected = _league(
        "selected",
        "Selected",
        my_players=("qb1", "rb2", "wr1", "te1"),
        starters=("qb1", "rb2", "wr1", "te1"),
    )
    lineup = build_lineup_check(selected, CATALOG)
    assert lineup is not None

    board = build_roster_need_waiver_board(
        selected,
        lineup,
        CATALOG,
    )

    assert board.needs == ()
    assert board.matches == ()


def test_waiver_need_matching_fails_closed_when_ownership_not_ready():
    selected = _league(
        "selected",
        "Selected",
        ownership_ready=False,
    )
    lineup = build_lineup_check(selected, CATALOG)
    assert lineup is not None

    with pytest.raises(ValueError, match="unsafe"):
        build_roster_need_waiver_board(
            selected,
            lineup,
            CATALOG,
        )


def test_waiver_need_match_limit_is_bounded():
    selected = _league("selected", "Selected")
    lineup = build_lineup_check(selected, CATALOG)
    assert lineup is not None

    with pytest.raises(ValueError, match="1 to 200"):
        build_roster_need_waiver_board(
            selected,
            lineup,
            CATALOG,
            limit=0,
        )


def test_fantasy_hq_exposes_roster_need_waiver_matches():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Roster Need Matches" in page
    assert "build_roster_need_waiver_board" in page
    assert "Fits action slots" in page
    assert "not a player-value ranking" in page
