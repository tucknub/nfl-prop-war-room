from __future__ import annotations

from src.fantasy.league_activity import build_league_activity
from src.fantasy.models import (
    FaabTransfer,
    FantasyLeagueState,
    LeagueRules,
    LeagueTransaction,
    Manager,
    Roster,
    TradedPick,
)


CATALOG = {
    "p1": {
        "full_name": "Added Runner",
        "position": "RB",
        "team": "IND",
    },
    "p2": {
        "full_name": "Dropped Wideout",
        "position": "WR",
        "team": "HOU",
    },
    "p3": {
        "full_name": "Trade Tight End",
        "position": "TE",
        "team": "KC",
    },
}


def _league() -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-1",
        name="Papa John's",
        season="2026",
        status="in_season",
        team_count=3,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "TE", "BN"),
            scoring_settings={"rec": 1},
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Tuck",
                team_name="Revenge Tour",
            ),
            Manager(
                platform_user_id="u2",
                display_name="Bryant",
                team_name="Team Bryant",
            ),
            Manager(
                platform_user_id="u3",
                display_name="Other",
                team_name=None,
            ),
        ),
        rosters=(
            Roster("1", "me", (), (), (), (), {}),
            Roster("2", "u2", (), (), (), (), {}),
            Roster("3", "u3", (), (), (), (), {}),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _transactions():
    return (
        LeagueTransaction(
            platform_transaction_id="waiver-1",
            transaction_type="waiver",
            status="complete",
            week=1,
            roster_ids=("1",),
            creator_user_id="me",
            created_at_ms=1000,
            status_updated_at_ms=1500,
            consenter_roster_ids=(),
            adds={"p1": "1"},
            drops={"p2": "1"},
            traded_picks=(),
            faab_transfers=(),
            waiver_bid=17,
        ),
        LeagueTransaction(
            platform_transaction_id="trade-1",
            transaction_type="trade",
            status="complete",
            week=1,
            roster_ids=("2", "3"),
            creator_user_id="u2",
            created_at_ms=2000,
            status_updated_at_ms=2500,
            consenter_roster_ids=("2", "3"),
            adds={"p3": "2"},
            drops={},
            traded_picks=(
                TradedPick(
                    season="2027",
                    round=2,
                    original_roster_id="3",
                    previous_owner_roster_id="3",
                    owner_roster_id="2",
                ),
            ),
            faab_transfers=(
                FaabTransfer(
                    sender_roster_id="2",
                    receiver_roster_id="3",
                    amount=5,
                ),
            ),
            waiver_bid=None,
        ),
    )


def test_league_activity_maps_players_teams_and_faab():
    feed = build_league_activity(
        _league(),
        _transactions(),
        CATALOG,
    )

    assert feed.transaction_count == 2
    assert feed.add_count == 2
    assert feed.drop_count == 1
    assert feed.trade_count == 1
    assert feed.waiver_count == 1

    trade = feed.transactions[0]
    assert trade.transaction_id == "trade-1"
    assert trade.type_label == "Trade"
    assert trade.teams == ("Team Bryant", "Other")
    assert trade.adds[0].name == "Trade Tight End"
    assert trade.adds[0].team_name == "Team Bryant"
    assert trade.traded_pick_count == 1
    assert trade.faab_transfers[0].sender_team == "Team Bryant"
    assert trade.faab_transfers[0].receiver_team == "Other"
    assert trade.faab_transfers[0].amount == 5

    waiver = feed.transactions[1]
    assert waiver.teams == ("Revenge Tour",)
    assert waiver.adds[0].name == "Added Runner"
    assert waiver.adds[0].position == "RB"
    assert waiver.drops[0].name == "Dropped Wideout"
    assert waiver.waiver_bid == 17


def test_league_activity_sorts_by_latest_status_or_created_time():
    tx = list(_transactions())
    tx.append(
        LeagueTransaction(
            platform_transaction_id="free-agent-1",
            transaction_type="free_agent",
            status="complete",
            week=1,
            roster_ids=("1",),
            creator_user_id="me",
            created_at_ms=5000,
            status_updated_at_ms=None,
            consenter_roster_ids=(),
            adds={"p2": "1"},
            drops={},
            traded_picks=(),
            faab_transfers=(),
            waiver_bid=None,
        )
    )

    feed = build_league_activity(_league(), tx, CATALOG)

    assert [row.transaction_id for row in feed.transactions] == [
        "free-agent-1",
        "trade-1",
        "waiver-1",
    ]
    assert feed.transactions[0].type_label == "Free Agent"


def test_league_activity_unknown_roster_and_player_fallbacks_are_visible():
    transaction = LeagueTransaction(
        platform_transaction_id="unknown-1",
        transaction_type="waiver",
        status="pending",
        week=2,
        roster_ids=("99",),
        creator_user_id=None,
        created_at_ms=None,
        status_updated_at_ms=None,
        consenter_roster_ids=(),
        adds={"missing-player": "99"},
        drops={},
        traded_picks=(),
        faab_transfers=(),
        waiver_bid=3,
    )

    feed = build_league_activity(_league(), (transaction,), CATALOG)
    row = feed.transactions[0]

    assert row.teams == ("Roster 99",)
    assert row.adds[0].name == "missing-player"
    assert row.adds[0].team_name == "Roster 99"
    assert row.status == "pending"


def test_empty_league_activity_is_safe():
    feed = build_league_activity(_league(), (), CATALOG)

    assert feed.transactions == ()
    assert feed.transaction_count == 0
    assert feed.add_count == 0
    assert feed.drop_count == 0
    assert feed.trade_count == 0
    assert feed.waiver_count == 0


def test_fantasy_hq_exposes_league_activity():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert '"League Activity"' in page
    assert "build_league_activity" in page
    assert "Recent adds, drops, waivers and trades" in page
    assert "FAAB / bid" in page
