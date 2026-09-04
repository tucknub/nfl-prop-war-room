from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_deep_prop_market_freshness_fails_closed() -> None:
    cache = _read("dashboard/glitch_radar_props_cache.py")
    feed = _read("dashboard/glitch_radar_props_feed.py")

    assert "PROP_SNAPSHOT_CACHE_SECONDS = 120" in cache
    assert "PROP_MAX_QUOTE_AGE_SECONDS = 120" in cache
    assert 'row.get("age_seconds")' in cache
    assert "No player-prop quotes at or under 120 seconds old" in cache
    assert "max_age_sec: int = 120" in feed


def test_no_key_preview_is_not_promoted_into_today() -> None:
    today = _read("dashboard/propwar_today_owner.py")

    assert "Market preview signals stay inside Markets" in today
    assert "_market_actions(\n                _today_market_snapshot()" not in today


def test_market_actions_are_verification_signals() -> None:
    action = _read("dashboard/glitch_radar_action.py")
    markets = _read("dashboard/pages/09_Glitch_Radar.py")

    assert 'VERIFY = "VERIFY"' in action
    assert "BET = VERIFY" in action
    assert "Highest-priority verification queue" in markets
    assert "every displayed price must be verified in the sportsbook" in markets


def test_unreachable_stale_line_tab_is_removed() -> None:
    deep = _read("dashboard/pages/10_Deep_Prop_Radar.py")

    assert "Stale Lines" not in deep
    assert "stale_tab" not in deep
    assert "quotes older than 120 seconds are rejected" in deep


def test_faab_ui_is_context_not_bid_recommendation() -> None:
    fantasy = _read("dashboard/pages/11_Fantasy_HQ.py")
    action_feed = _read("src/fantasy/action_feed.py")

    assert "FAAB Market Context" in fantasy
    assert "No automated bid recommendation is shown." in fantasy
    assert '"Recommended bid"' not in fantasy
    assert '"Aggressive bid"' not in fantasy
    assert '"Max bid"' not in fantasy
    assert "faab_target = None" in action_feed


def test_current_week_trade_baseline_is_not_auto_promoted() -> None:
    fantasy = _read("dashboard/pages/11_Fantasy_HQ.py")
    action_feed = _read("src/fantasy/action_feed.py")

    assert "not an accept/decline trade verdict" in fantasy
    assert "CURRENT-WEEK FAVORABLE" in fantasy
    assert "A favorable baseline does not mean the trade should be accepted." in fantasy
    assert "def _best_trade_action(" not in action_feed


def test_role_confidence_is_labeled_as_sample_strength() -> None:
    player = _read("dashboard/pages/02_Players.py")
    team = _read("dashboard/pages/01_Teams.py")
    command = _read("dashboard/player_command_owner.py")

    assert "**Sample strength:**" in player
    assert '"Sample strength": row["confidence"]' in team
    assert 'metric("Sample strength", role_change.confidence)' in command


def test_margin_estimates_are_labeled_as_models() -> None:
    margin = _read("dashboard/pages/07_Margin_War_Room.py")

    assert 'metric("nflverse spread"' in margin
    assert 'metric("Model mean margin"' in margin
    assert 'metric("Historical loss-rate est."' in margin
    assert "they are model estimates, not sportsbook probabilities" in margin


def test_knockout_refuses_unvalidated_probability_and_bid_claims() -> None:
    knockout = _read("dashboard/pages/08_Knockout_Fantasy_War_Room.py")

    assert "no fake survival probability or optimal bid" in knockout
    assert "does not claim a weekly survival probability" in knockout
