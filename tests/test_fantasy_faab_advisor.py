from __future__ import annotations

from src.fantasy.faab_advisor import build_faab_advice_board
from src.fantasy.market_waivers import (
    HIGH,
    LOW,
    MEDIUM,
    MarketWaiverBoard,
    MarketWaiverCandidate,
)
from src.fantasy.models import (
    FantasyLeagueState,
    LeagueRules,
    LeagueTransaction,
    Manager,
    Roster,
)


def _league(*, budget=100, used=0, team_count=12):
    settings = {}
    if used is not None:
        settings["waiver_budget_used"] = used
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-1",
        name="Test League",
        season="2026",
        status="in_season",
        team_count=team_count,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "TE", "FLEX", "BN"),
            scoring_settings={"rec": 1.0},
            waiver_budget=budget,
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Me",
                team_name="Mine",
            ),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=("mine",),
                starters=("mine",),
                reserve=(),
                taxi=(),
                settings=settings,
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _candidate(
    player_id,
    *,
    need=HIGH,
    position="WR",
    points=15.0,
    improvement=5.0,
    coverage="FULL",
    trend=500,
):
    return MarketWaiverCandidate(
        sleeper_player_id=player_id,
        player_name=f"Player {player_id}",
        position=position,
        nfl_team="IND",
        status="Active",
        need=need,
        target_slot="FLEX",
        fit_slots=("WR", "FLEX"),
        market_fantasy_points=points,
        coverage=coverage,
        replacement_player="Current Starter",
        replacement_fantasy_points=points - improvement,
        expected_lineup_improvement=improvement,
        trend_count=trend,
        mine_elsewhere=(),
        reason="test",
    )


def _board(*candidates):
    return MarketWaiverBoard(
        available_player_count=len(candidates),
        market_covered_count=len(candidates),
        candidates=tuple(candidates),
    )


def _waiver(transaction_id, bid):
    return LeagueTransaction(
        platform_transaction_id=transaction_id,
        transaction_type="waiver",
        status="complete",
        week=3,
        roster_ids=("2",),
        creator_user_id="other",
        created_at_ms=1,
        status_updated_at_ms=2,
        consenter_roster_ids=(),
        adds={f"add-{transaction_id}": "2"},
        drops={},
        traded_picks=(),
        faab_transfers=(),
        waiver_bid=bid,
        metadata={},
        raw={},
    )


def test_faab_advisor_uses_live_remaining_balance_and_caps_every_bid():
    board = build_faab_advice_board(
        _league(budget=100, used=63),
        _board(
            _candidate(
                "star",
                need=HIGH,
                points=19.0,
                improvement=10.0,
                trend=5000,
            )
        ),
        current_week=6,
    )

    assert board.enabled is True
    assert board.starting_budget == 100
    assert board.budget_used == 63
    assert board.remaining_budget == 37
    assert board.live_balance is True

    advice = board.advice[0]
    assert advice.budget_limited is True
    assert advice.recommended_bid <= 37
    assert advice.range_high_bid <= 37
    assert advice.aggressive_bid <= 37
    assert advice.max_bid <= 37


def test_faab_advisor_disables_when_league_has_no_positive_budget():
    board = build_faab_advice_board(
        _league(budget=None, used=None),
        _board(_candidate("a")),
    )

    assert board.enabled is False
    assert board.advice == ()
    assert "does not expose" in board.reason


def test_high_need_costs_more_than_medium_and_low_for_same_player_profile():
    league = _league()
    high = build_faab_advice_board(
        league,
        _board(_candidate("high", need=HIGH)),
    ).advice[0]
    medium = build_faab_advice_board(
        league,
        _board(_candidate("medium", need=MEDIUM)),
    ).advice[0]
    low = build_faab_advice_board(
        league,
        _board(_candidate("low", need=LOW)),
    ).advice[0]

    assert high.recommended_pct > medium.recommended_pct > low.recommended_pct
    assert high.max_pct > medium.max_pct > low.max_pct


def test_recent_league_winning_bids_raise_pressure_and_recommendation():
    league = _league()
    candidates = _board(
        _candidate("target", need=MEDIUM, trend=800),
        _candidate("alt", need=MEDIUM, points=12.0, trend=50),
    )

    quiet = build_faab_advice_board(
        league,
        candidates,
        current_week=5,
        transactions=(),
    ).advice[0]
    active_board = build_faab_advice_board(
        league,
        candidates,
        current_week=5,
        transactions=(
            _waiver("1", 18),
            _waiver("2", 25),
            _waiver("3", 31),
            _waiver("4", 22),
        ),
    )
    active = active_board.advice[0]

    assert active_board.historical_bid_count == 4
    assert active_board.historical_median_pct is not None
    assert active_board.historical_p75_pct is not None
    assert active.recommended_pct > quiet.recommended_pct
    assert active.competition in {"MEDIUM", "HIGH"}


def test_comparable_supply_reduces_scarcity_premium():
    league = _league()
    target = _candidate(
        "target",
        need=MEDIUM,
        points=15.0,
        improvement=5.0,
        trend=200,
    )

    scarce = build_faab_advice_board(
        league,
        _board(target),
    ).advice[0]
    deep = build_faab_advice_board(
        league,
        _board(
            target,
            _candidate(
                "alt1",
                need=MEDIUM,
                points=14.5,
                improvement=4.0,
                trend=190,
            ),
            _candidate(
                "alt2",
                need=MEDIUM,
                points=14.0,
                improvement=3.5,
                trend=180,
            ),
            _candidate(
                "alt3",
                need=MEDIUM,
                points=13.5,
                improvement=3.0,
                trend=170,
            ),
            _candidate(
                "alt4",
                need=MEDIUM,
                points=13.0,
                improvement=2.5,
                trend=160,
            ),
        ),
    ).advice[0]

    assert scarce.comparable_supply == 0
    assert deep.comparable_supply == 4
    assert scarce.recommended_pct > deep.recommended_pct


def test_missing_live_balance_is_not_assumed_to_be_full_remaining_budget():
    board = build_faab_advice_board(
        _league(budget=150, used=None),
        _board(_candidate("a", need=MEDIUM)),
    )

    assert board.enabled is True
    assert board.starting_budget == 150
    assert board.budget_used is None
    assert board.remaining_budget is None
    assert board.live_balance is False
    assert board.advice[0].recommended_bid > 0
    assert board.advice[0].budget_limited is False


def test_partial_coverage_has_lower_confidence_than_full_when_other_inputs_match():
    league = _league(used=None)
    full = build_faab_advice_board(
        league,
        _board(_candidate("full", coverage="FULL")),
    ).advice[0]
    partial = build_faab_advice_board(
        league,
        _board(_candidate("partial", coverage="PARTIAL")),
    ).advice[0]

    assert full.score > partial.score
    assert full.confidence in {"MEDIUM", "HIGH"}
    assert partial.confidence in {"LOW", "MEDIUM"}


def test_fantasy_hq_exposes_faab_advisor():
    from pathlib import Path

    page = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "11_Fantasy_HQ.py"
    ).read_text(encoding="utf-8")

    assert "FAAB Market Context" in page
    assert "build_faab_advice_board" in page
    assert "No automated bid recommendation is shown." in page
    assert "Recommended bid" not in page
    assert "Aggressive bid" not in page
    assert "Max bid" not in page
    assert "Remaining FAAB" in page
    assert "Recent bid P75" in page
