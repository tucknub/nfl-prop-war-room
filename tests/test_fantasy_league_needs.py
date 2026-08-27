from __future__ import annotations

from src.fantasy.league_needs import ONE_WAY, TWO_WAY, build_league_needs_board
from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster


CATALOG = {
    "qb1": {"full_name": "QB 1", "position": "QB", "status": "Active"},
    "qb2": {"full_name": "QB 2", "position": "QB", "status": "Active"},
    "qb3": {"full_name": "QB 3", "position": "QB", "status": "Active"},
    "rb1": {"full_name": "RB 1", "position": "RB", "status": "Active"},
    "rb2": {"full_name": "RB 2", "position": "RB", "status": "Active"},
    "rb3": {"full_name": "RB 3", "position": "RB", "status": "Active"},
    "rb4": {"full_name": "RB 4", "position": "RB", "status": "Active"},
    "rb5": {"full_name": "RB 5", "position": "RB", "status": "Active"},
    "rb6": {"full_name": "RB 6", "position": "RB", "status": "Active"},
    "wr1": {"full_name": "WR 1", "position": "WR", "status": "Active"},
    "wr2": {"full_name": "WR 2", "position": "WR", "status": "Active"},
    "wr3": {"full_name": "WR 3", "position": "WR", "status": "Active"},
    "wr4": {"full_name": "WR 4", "position": "WR", "status": "Active"},
    "wr5": {"full_name": "WR 5", "position": "WR", "status": "Active"},
    "wr6": {"full_name": "WR 6", "position": "WR", "status": "Active"},
    "te1": {"full_name": "TE 1", "position": "TE", "status": "Active"},
    "te2": {"full_name": "TE 2", "position": "TE", "status": "Active"},
    "te3": {"full_name": "TE 3", "position": "TE", "status": "Active"},
}


def _league() -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league",
        name="League",
        season="2026",
        status="in_season",
        team_count=3,
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
            Manager("other", "Other", "Other Team"),
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
            Roster(
                "3",
                "other",
                ("qb3", "rb5", "rb6", "wr5", "wr6", "te3"),
                ("qb3", "rb5", "rb6", "wr5", "wr6", "te3"),
                (),
                (),
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def test_league_needs_board_summarizes_every_team():
    board = build_league_needs_board(_league(), CATALOG)

    assert board.team_count == 3
    assert board.rows[0].team_name == "My Team"
    assert board.rows[0].is_mine is True
    assert "WR" in board.rows[0].high_needs
    assert "RB" in board.rows[0].depth_positions
    assert board.high_need_team_count >= 2


def test_league_needs_board_finds_two_way_trade_fit():
    board = build_league_needs_board(_league(), CATALOG)

    partner = next(
        row for row in board.trade_fits
        if row.team_name == "Trade Partner"
    )

    assert partner.signal == TWO_WAY
    assert "WR" in partner.they_can_help_me_at
    assert "RB" in partner.i_can_help_them_at
    assert "WR" in partner.my_needs
    assert "RB" in partner.their_needs
    assert board.two_way_trade_fit_count >= 1


def test_flex_depth_is_conservative_not_fake_surplus():
    league = _league()
    board = build_league_needs_board(league, CATALOG)

    other = next(row for row in board.rows if row.team_name == "Other Team")

    # Two RB starters + one flex means three RBs would only equal maximum
    # all-RB starter demand; depth is not labeled above that minimum.
    assert "RB" not in other.depth_positions


def test_trade_fit_rows_rank_two_way_before_one_way():
    board = build_league_needs_board(_league(), CATALOG)

    signals = [row.signal for row in board.trade_fits]
    if ONE_WAY in signals:
        assert signals.index(TWO_WAY) < signals.index(ONE_WAY)


def test_fantasy_hq_exposes_league_needs_board():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "League Needs Board" in page
    assert "Potential trade-fit teams" in page
    assert "build_league_needs_board" in page
    assert "Two-way fit" in page
    assert "Depth above starter demand" in page
