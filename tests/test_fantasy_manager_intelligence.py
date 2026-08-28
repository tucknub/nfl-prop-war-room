from __future__ import annotations

from src.fantasy.manager_intelligence import (
    build_manager_intelligence,
    build_manager_recent_behavior,
)
from src.fantasy.models import (
    FantasyLeagueState,
    LeagueRules,
    LeagueTransaction,
    Manager,
    Roster,
)


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
    "fa_wr": {"full_name": "Free WR", "position": "WR", "team": "SEA", "status": "Active", "active": True},
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


def test_manager_intelligence_consolidates_needs_depth_and_mutual_fit():
    report = build_manager_intelligence(_league(), "2", CATALOG)

    assert report.team_name == "Trade Partner"
    assert "RB" in report.likely_shopping
    assert "WR" in report.depth_positions
    assert report.trade_fit_signal == "TWO_WAY"

    movable = [row.name for row in report.movable_depth_players]
    my_fit = [row.name for row in report.my_players_fit_them]
    their_fit = [row.name for row in report.their_players_fit_me]

    assert "Bench WR" in movable
    assert "Bench RB" in my_fit
    assert "Bench WR" in their_fit
    assert report.mutual_trade_starting_points
    assert report.mutual_trade_starting_points[0].i_give.name == "Bench RB"
    assert report.mutual_trade_starting_points[0].i_receive.name == "Bench WR"


def test_manager_intelligence_does_not_claim_mutual_trade_when_selected_team_is_mine():
    report = build_manager_intelligence(_league(), "1", CATALOG)

    assert report.team_name == "My Team"
    assert report.trade_fit_signal is None
    assert report.mutual_trade_starting_points == ()


def _transaction(
    *,
    transaction_id: str,
    transaction_type: str,
    adds=None,
    drops=None,
    roster_ids=("2",),
    waiver_bid=None,
    timestamp=1000,
):
    return LeagueTransaction(
        platform_transaction_id=transaction_id,
        transaction_type=transaction_type,
        status="complete",
        week=2,
        roster_ids=tuple(roster_ids),
        creator_user_id="partner",
        created_at_ms=timestamp,
        status_updated_at_ms=timestamp,
        consenter_roster_ids=(),
        adds=dict(adds or {}),
        drops=dict(drops or {}),
        traded_picks=(),
        faab_transfers=(),
        waiver_bid=waiver_bid,
    )


def test_manager_recent_behavior_is_roster_specific_and_factual():
    transactions = (
        _transaction(
            transaction_id="waiver-1",
            transaction_type="waiver",
            adds={"fa_wr": "2"},
            drops={"wr2": "2"},
            waiver_bid=17,
            timestamp=3000,
        ),
        _transaction(
            transaction_id="trade-1",
            transaction_type="trade",
            adds={"rb1": "2"},
            drops={"wr3": "2"},
            timestamp=2000,
        ),
        _transaction(
            transaction_id="other",
            transaction_type="free_agent",
            adds={"wr1": "1"},
            roster_ids=("1",),
            timestamp=4000,
        ),
    )

    behavior = build_manager_recent_behavior(
        _league(),
        "2",
        transactions,
        CATALOG,
    )

    assert len(behavior) == 2
    assert behavior[0].kind == "Waiver"
    assert "Added Free WR" in behavior[0].summary
    assert "Dropped WR 2" in behavior[0].summary
    assert "FAAB bid $17" in behavior[0].summary
    assert behavior[1].kind == "Trade"
    assert "Received RB 1" in behavior[1].summary
    assert "Sent WR 3" in behavior[1].summary


def test_manager_intelligence_is_explicitly_exposed_in_fantasy_hq():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert '"Trades"' in page
    assert 'st.markdown("#### Manager Intelligence")' in page
    assert "build_manager_intelligence" in page
    assert "Players they could reasonably move" in page
    assert "My players that fit them" in page
    assert "Their players that fit me" in page
    assert "roster-fit inference" in page
