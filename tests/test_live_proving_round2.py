from __future__ import annotations

from pathlib import Path

from dashboard.propwar_today import MEDIUM
from dashboard.propwar_today_owner import _market_actions


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_august_ev_row_is_medium_priority_on_today() -> None:
    snapshot = {
        "fetched_at": "2026-08-28T12:53:00+00:00",
        "alerts": [],
        "ev": [
            {
                "away_team": "Arizona Cardinals",
                "home_team": "Green Bay Packers",
                "selection": "Arizona Cardinals",
                "side": "Arizona Cardinals",
                "book": "FanDuel",
                "price": 450,
                "fair_prob_pct": 19.5,
                "market": "moneyline",
                "commence_time": "2026-08-29T00:00:00.000Z",
            }
        ],
    }

    actions = _market_actions(snapshot)

    assert len(actions) == 1
    assert actions[0].priority == MEDIUM
    assert actions[0].confidence == "MEDIUM"
    assert actions[0].why.startswith("PRESEASON · ")


def test_fantasy_selector_migrates_saved_demo_choice_to_real_league() -> None:
    source = _source("dashboard/pages/11_Fantasy_HQ.py")

    assert 'saved_label = str(' in source
    assert 'demo_ids = {' in source
    assert 'priority_leagues' in source
    assert 'league_options[saved_label] in demo_ids' in source
    assert 'st.session_state["fantasy_hq_sleeper_league"] = league_labels[0]' in source


def test_player_command_uses_central_durable_sleeper_preference() -> None:
    source = _source("dashboard/player_command_owner.py")
    owner_preferences = _source("dashboard/owner_preferences.py")

    assert "from owner_preferences import remembered_sleeper_username" in source
    assert "return remembered_sleeper_username()" in source
    assert 'st.query_params.get(SLEEPER_USERNAME_QUERY_KEY)' in owner_preferences
    assert "private_sleeper_username()" in owner_preferences


def test_home_and_today_preserve_sleeper_context_in_deep_links() -> None:
    home = _source("dashboard/app.py")
    today = _source("dashboard/propwar_today_owner.py")

    assert "remembered_sleeper_username()" in home
    assert 'sleeper_suffix = (' in home
    assert 'f"/players{sleeper_suffix}"' in home
    assert 'f"/fantasy-hq{sleeper_suffix}"' in home

    assert 'urlencode({"fh_sleeper": username})' in today


def test_arbitrage_is_action_first_and_thin_arbs_are_not_featured() -> None:
    source = _source("dashboard/pages/09_Glitch_Radar.py")

    assert "FEATURED_ARB_MIN_EDGE_PCT = 2.0" in source
    assert 'st.markdown("**BET BOTH SIDES**")' in source
    assert "100-unit equal-payout example" in source
    assert "locked ROI" in source
    assert "THIN ARB" in source
    assert "if edge is None or edge < FEATURED_ARB_MIN_EDGE_PCT:" in source
    assert "_render_arb_card(row, show_evidence=False)" in source
    assert "_render_arb_card(row)" in source


def test_raw_generic_arb_table_is_no_longer_used_for_arbitrage() -> None:
    source = _source("dashboard/pages/09_Glitch_Radar.py")

    assert '_render_generic_opportunity(row, "Arbitrage")' not in source
