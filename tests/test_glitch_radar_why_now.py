from __future__ import annotations

import pytest

from dashboard.glitch_radar_action import (
    BET,
    PASS,
    WATCH,
    ev_action,
    glitch_action,
    peer_implied_probability_gap_range,
    peer_price_gap_range,
    peer_prices_for_alert,
)
from dashboard.glitch_radar_live import Quote, detect_price_outliers
from dashboard.glitch_radar_history import (
    BASELINE,
    DISAPPEARED,
    IMPROVED,
    NEW,
    UNCHANGED,
    WORSENED,
    build_market_observations,
    ev_opportunity_key,
    glitch_opportunity_key,
    MarketHistoryStore,
    history_summary,
    update_market_history,
)


def _glitch(price: int, *, book: str = "DraftKings") -> dict:
    return {
        "severity": "P1",
        "consensus_implied_prob": 0.45,
        "quote": {
            "book": book,
            "event": "A @ B",
            "market": "moneyline",
            "participant": "",
            "side": "away",
            "threshold": None,
            "odds_american": price,
        },
    }


def _ev(price: int, *, book: str = "DraftKings", fair_prob_pct: float = 45.0) -> dict:
    return {
        "away_team": "A",
        "home_team": "B",
        "selection": "A",
        "side": "A ML",
        "market": "moneyline",
        "threshold": None,
        "book": book,
        "price": price,
        "fair_prob_pct": fair_prob_pct,
    }


def test_history_first_scan_is_baseline_not_fake_new_signal():
    observations = build_market_observations([_glitch(140)], [_ev(140)])
    state = update_market_history(None, observations, fetched_at="2026-08-27T19:42:00+00:00")

    assert state["scan_count"] == 1
    assert {row["status"] for row in state["active"].values()} == {BASELINE}
    assert history_summary(state) == {
        "new": 0,
        "improved": 0,
        "worsened": 0,
        "disappeared": 0,
    }


def test_history_detects_improved_worsened_new_and_disappeared():
    first = build_market_observations([_glitch(130)], [_ev(130)])
    state = update_market_history(None, first, fetched_at="2026-08-27T19:42:00+00:00")

    second = build_market_observations(
        [_glitch(144)],
        [_ev(120), _ev(125, book="Caesars")],
    )
    state = update_market_history(state, second, fetched_at="2026-08-27T19:47:00+00:00")

    glitch_row = state["active"][glitch_opportunity_key(_glitch(144))]
    dk_ev_row = state["active"][ev_opportunity_key(_ev(120))]
    czr_ev_row = state["active"][ev_opportunity_key(_ev(125, book="Caesars"))]

    assert glitch_row["status"] == IMPROVED
    assert glitch_row["previous_price"] == 130
    assert glitch_row["current_price"] == 144
    assert dk_ev_row["status"] == WORSENED
    assert czr_ev_row["status"] == NEW
    assert history_summary(state)["new"] == 1
    assert history_summary(state)["improved"] == 1
    assert history_summary(state)["worsened"] == 1


def test_same_cached_snapshot_does_not_create_fake_second_scan():
    observations = build_market_observations([_glitch(140)], [])
    state = update_market_history(None, observations, fetched_at="2026-08-27T19:42:00+00:00")
    again = update_market_history(state, observations, fetched_at="2026-08-27T19:42:00+00:00")

    assert again["scan_count"] == 1
    row = again["active"][glitch_opportunity_key(_glitch(140))]
    assert row["status"] == BASELINE


def test_disappeared_signal_is_retained_for_since_last_scan_summary():
    first = build_market_observations([_glitch(140)], [])
    state = update_market_history(None, first, fetched_at="2026-08-27T19:42:00+00:00")
    state = update_market_history(state, {}, fetched_at="2026-08-27T19:47:00+00:00")

    assert state["active"] == {}
    assert len(state["disappeared"]) == 1
    assert state["disappeared"][0]["status"] == DISAPPEARED
    assert history_summary(state)["disappeared"] == 1


def test_glitch_action_passes_outlier_that_is_worse_than_consensus():
    # -140 implies ~58.3%, worse than 45% peer consensus.
    action = glitch_action(_glitch(-140))
    assert action.action == PASS
    assert action.edge_points is not None and action.edge_points < 0


def test_glitch_action_bets_material_better_than_consensus_price():
    # +144 implies ~41.0%, materially below 45% consensus.
    action = glitch_action(_glitch(144))
    assert action.action == BET
    assert action.edge_points is not None and action.edge_points >= 3


def test_ev_action_thresholds_are_explicit():
    assert ev_action(_ev(150, fair_prob_pct=45.0)).action == BET
    assert ev_action(_ev(125, fair_prob_pct=45.0)).action in {BET, WATCH}
    assert ev_action(_ev(100, fair_prob_pct=45.0)).action == PASS


def test_peer_prices_match_exact_market_identity_and_user_books():
    alert = _glitch(144)
    quotes = [
        alert["quote"],
        {**alert["quote"], "book": "FanDuel", "odds_american": 124},
        {**alert["quote"], "book": "Caesars", "odds_american": 126},
        {**alert["quote"], "book": "Hard Rock Bet", "odds_american": 120},
        {**alert["quote"], "book": "Pinnacle", "odds_american": 122},
        {**alert["quote"], "book": "bet365", "side": "home", "odds_american": 130},
    ]

    peers = peer_prices_for_alert(alert, quotes)
    assert [(row["book"], row["price"]) for row in peers] == [
        ("Caesars", 126),
        ("FanDuel", 124),
        ("Hard Rock Bet", 120),
    ]
    gap = peer_implied_probability_gap_range(144, peers)
    assert gap is not None
    assert gap[0] == pytest.approx(3.27, abs=0.05)
    assert gap[1] == pytest.approx(4.48, abs=0.05)
    assert peer_price_gap_range(144, peers) == gap


def test_glitch_radar_page_surfaces_temporal_state_and_keeps_pass_off_top_board():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "09_Glitch_Radar.py"
    ).read_text(encoding="utf-8")

    assert "def _market_history_store() -> MarketHistoryStore:" in source
    assert "market_history = _market_history_store().update(" in source
    assert 'st.markdown("### Since last scan")' in source
    assert '**WHY NOW:**' in source
    assert 'First detected:' in source
    assert 'Last confirmed:' in source
    assert 'ACTION: {action.action}' in source
    assert 'if glitch_action(alert).action == PASS:' in source
    assert 'if ev_action(row).action == PASS:' in source



def test_near_even_sign_crossing_is_not_a_glitch_by_itself():
    quotes = [
        Quote("DraftKings", "A @ B", "moneyline", side="home", odds_american=101),
        Quote("Hard Rock Bet", "A @ B", "moneyline", side="home", odds_american=100),
        Quote("Caesars", "A @ B", "moneyline", side="home", odds_american=-105),
        Quote("FanDuel", "A @ B", "moneyline", side="home", odds_american=-108),
    ]

    assert detect_price_outliers(quotes) == []


def test_large_sign_crossing_can_still_trigger_a_real_outlier():
    quotes = [
        Quote("DraftKings", "A @ B", "moneyline", side="home", odds_american=300),
        Quote("Hard Rock Bet", "A @ B", "moneyline", side="home", odds_american=-180),
        Quote("Caesars", "A @ B", "moneyline", side="home", odds_american=-200),
        Quote("FanDuel", "A @ B", "moneyline", side="home", odds_american=-190),
    ]

    alerts = detect_price_outliers(quotes)
    dk = next(row for row in alerts if row["quote"]["book"] == "DraftKings")
    assert dk["sign_mismatch"] is True
    assert dk["absolute_prob_gap_points"] >= 20
    assert dk["severity"] == "P0"

def test_process_store_preserves_history_across_calls():
    store = MarketHistoryStore()
    first = build_market_observations([_glitch(130)], [])
    second = build_market_observations([_glitch(144)], [])

    state1 = store.update(first, fetched_at="2026-08-27T19:42:00+00:00")
    state2 = store.update(second, fetched_at="2026-08-27T19:47:00+00:00")

    key = glitch_opportunity_key(_glitch(144))
    assert state1["active"][key]["status"] == BASELINE
    assert state2["active"][key]["status"] == IMPROVED
    assert state2["active"][key]["first_seen"] == "2026-08-27T19:42:00+00:00"
