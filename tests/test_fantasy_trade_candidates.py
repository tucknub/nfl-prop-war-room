from __future__ import annotations

from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.trade_candidates import build_trade_candidate_board


CATALOG = {
    "qb1": {"full_name": "QB 1", "position": "QB", "team": "BUF", "status": "Active"},
    "qb2": {"full_name": "QB 2", "position": "QB", "team": "KC", "status": "Active"},
    "rb1": {"full_name": "RB 1", "position": "RB", "team": "IND", "status": "Active"},
    "rb2": {"full_name": "RB 2", "position": "RB", "team": "DET", "status": "Active"},
    "rb3": {"full_name": "RB 3", "position": "RB", "team": "ATL", "status": "Active"},
    "rb4": {"full_name": "Bench RB", "position": "RB", "team": "CHI", "status": "Active"},
    "rb5": {"full_name": "Partner RB", "position": "RB", "team": "MIA", "status": "Active"},
    "wr1": {"full_name": "WR 1", "position": "WR", "team": "PHI", "status": "Active"},
    "wr2": {"full_name": "WR 2", "position": "WR", "team": "CIN", "status": "Active"},
    "wr3": {"full_name": "WR 3", "position": "WR", "team": "BUF", "status": "Active"},
    "wr4": {"full_name": "WR 4", "position": "WR", "team": "DAL", "status": "Active"},
    "wr5": {"full_name": "Bench WR", "position": "WR", "team": "LAR", "status": "Active"},
    "te1": {"full_name": "TE 1", "position": "TE", "team": "BAL", "status": "Active"},
    "te2": {"full_name": "TE 2", "position": "TE", "team": "ARI", "status": "Active"},
}


def _league() -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league",
        name="League",
        season="2026",
        status="in_season",
        team_count=2,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BN"),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager("me", "Me", "My Team"),
            Manager("partner", "Partner", "Trade Partner"),
        ),
        rosters=(
            Roster(
                "1",
                "me",
                ("qb1", "rb1", "rb2", "rb3", "rb4", "wr1", "te1"),
                ("qb1", "rb1", "rb2", "rb3", "wr1", "te1"),
                (),
                (),
            ),
            Roster(
                "2",
                "partner",
                ("qb2", "rb5", "wr2", "wr3", "wr4", "wr5", "te2"),
                ("qb2", "rb5", "wr2", "wr3", "wr4", "te2"),
                (),
                (),
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def test_trade_candidate_board_turns_two_way_fit_into_specific_names():
    board = build_trade_candidate_board(_league(), CATALOG)

    assert board.two_way_count == 1
    assert len(board.matches) == 1

    match = board.matches[0]
    assert match.partner_team_name == "Trade Partner"
    assert match.two_way is True
    assert match.positions_i_need == ("WR",)
    assert match.positions_they_need == ("RB",)

    target_names = [row.name for row in match.players_i_could_target]
    my_names = [row.name for row in match.my_players_they_could_target]
    assert "Bench WR" in target_names
    assert "Bench RB" in my_names


def test_trade_candidate_board_sorts_bench_candidates_before_starters():
    board = build_trade_candidate_board(_league(), CATALOG)
    match = board.matches[0]

    assert match.players_i_could_target[0].name == "Bench WR"
    assert match.players_i_could_target[0].roster_slot == "Bench"
    assert match.my_players_they_could_target[0].name == "Bench RB"
    assert match.my_players_they_could_target[0].roster_slot == "Bench"


def test_trade_candidate_board_empty_when_my_roster_is_not_populated():
    league = _league()
    empty = FantasyLeagueState(
        platform=league.platform,
        platform_league_id=league.platform_league_id,
        name=league.name,
        season=league.season,
        status="pre_draft",
        team_count=league.team_count,
        previous_platform_league_id=league.previous_platform_league_id,
        current_platform_user_id=league.current_platform_user_id,
        my_platform_roster_id=league.my_platform_roster_id,
        rules=league.rules,
        draft=league.draft,
        managers=league.managers,
        rosters=(
            Roster("1", "me", (), (), (), ()),
            league.rosters[1],
        ),
        rules_ready=league.rules_ready,
        draft_ready=league.draft_ready,
        ownership_ready=False,
    )

    board = build_trade_candidate_board(empty, CATALOG)

    assert board.matches == ()
    assert board.two_way_count == 0


def test_fantasy_hq_exposes_specific_trade_candidates():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "Specific trade candidates" in page
    assert "build_trade_candidate_board" in page
    assert "Players I could target" in page
    assert "My players that fit them" in page
    assert "not a fair-trade verdict" in page
