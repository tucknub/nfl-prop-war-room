from __future__ import annotations

from pathlib import Path

import pytest

from dashboard.glitch_radar_action import peer_implied_probability_gap_range
from dashboard.glitch_radar_live import Quote, detect_price_outliers


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_live_near_even_market_does_not_manufacture_glitch_watches() -> None:
    quotes = [
        Quote("DraftKings", "Houston Texans @ Carolina Panthers", "moneyline", side="home", odds_american=101),
        Quote("Hard Rock Bet", "Houston Texans @ Carolina Panthers", "moneyline", side="home", odds_american=100),
        Quote("Caesars", "Houston Texans @ Carolina Panthers", "moneyline", side="home", odds_american=-105),
        Quote("FanDuel", "Houston Texans @ Carolina Panthers", "moneyline", side="home", odds_american=-108),
    ]

    assert detect_price_outliers(quotes) == []


def test_market_gap_uses_continuous_implied_probability_not_american_odds_subtraction() -> None:
    peers = (
        {"book": "Caesars", "price": -105},
        {"book": "FanDuel", "price": -108},
        {"book": "Hard Rock Bet", "price": 100},
    )
    gap = peer_implied_probability_gap_range(101, peers)

    assert gap is not None
    assert gap[0] == pytest.approx(0.25, abs=0.05)
    assert gap[1] == pytest.approx(2.17, abs=0.05)

    market_page = _source("dashboard/pages/09_Glitch_Radar.py")
    assert "American-odds points better" not in market_page
    assert "lower implied probability" in market_page


def test_today_preserves_rank_order_when_two_columns_stack() -> None:
    source = _source("dashboard/propwar_today_owner.py")

    assert "for row_start in range(0, len(ranked), 2):" in source
    assert "rank = row_start + offset + 1" in source
    assert "left, right = st.columns(2)" not in source


def test_today_downgrades_preseason_ev_from_high_priority() -> None:
    source = _source("dashboard/propwar_today_owner.py")

    assert "event_phase_label" in source
    assert 'is_preseason = phase == "PRESEASON"' in source
    assert "MEDIUM\n                    if is_preseason" in source
    assert "PRESEASON · " in source


def test_player_page_has_one_command_center_identity() -> None:
    page = _source("dashboard/pages/02_Players.py")
    command = _source("dashboard/player_command_owner.py")

    assert '"Player Command Center"' in page
    assert '"Live decision context"' in command
    assert 'section(\n        "Player Command Center"' not in command


def test_fantasy_hides_historical_role_badge_and_demotes_demo_leagues() -> None:
    fantasy = _source("dashboard/pages/11_Fantasy_HQ.py")
    ui = _source("dashboard/research_ui.py")

    assert "show_data_status=False" in fantasy
    assert 'DEMO_LEAGUE_NAMES = {"test league", "mock league", "demo league"}' in fantasy
    assert "scan_leagues = priority_leagues or tuple(leagues)" in fantasy
    assert "for row in scan_leagues" in fantasy
    assert "selector_leagues = (*priority_leagues, *demo_leagues)" in fantasy

    assert "show_data_status: bool = True" in ui
