from dashboard.glitch_radar_action import BET
from dashboard.propwar_today import MARKET
from dashboard.propwar_today_owner import (
    _fantasy_actions,
    _market_actions,
)


def test_today_market_actions_promote_good_side_glitch():
    snapshot = {
        "fetched_at": "2026-08-27T19:42:00+00:00",
        "alerts": [
            {
                "severity": "P1",
                "consensus_implied_prob": 0.50,
                "quote": {
                    "book": "DraftKings",
                    "event": "A @ B",
                    "market": "moneyline",
                    "participant": "",
                    "side": "away",
                    "threshold": None,
                    "odds_american": 150,
                },
            }
        ],
        "ev": [],
    }

    actions = _market_actions(snapshot)

    assert len(actions) == 1
    assert actions[0].category == MARKET
    assert actions[0].action == BET
    assert actions[0].priority == "HIGH"
    assert actions[0].href == "/glitch-radar"


def test_today_market_actions_do_not_promote_bad_side_glitch():
    snapshot = {
        "fetched_at": "2026-08-27T19:42:00+00:00",
        "alerts": [
            {
                "severity": "P1",
                "consensus_implied_prob": 0.40,
                "quote": {
                    "book": "DraftKings",
                    "event": "A @ B",
                    "market": "moneyline",
                    "participant": "",
                    "side": "away",
                    "threshold": None,
                    "odds_american": -150,
                },
            }
        ],
        "ev": [],
    }

    assert _market_actions(snapshot) == ()


def test_today_suppresses_market_backed_fantasy_feed_in_preseason_without_network():
    actions, errors = _fantasy_actions(
        username="Tucknub",
        live_season="2026",
        current_week=0,
        parlay_key="not-used",
    )

    assert actions == ()
    assert errors == ()


def test_owner_home_hooks_propwar_today_without_market_copy_in_public_app():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app = (root / "dashboard" / "app.py").read_text(encoding="utf-8")
    owner = (
        root / "dashboard" / "propwar_today_owner.py"
    ).read_text(encoding="utf-8")

    assert "render_propwar_today_if_owner" in app
    assert "render_propwar_today_if_owner()" in app
    assert "sportsbook" not in app.lower()
    assert "betting" not in app.lower()
    assert "odds" not in app.lower()

    assert 'st.markdown("## PropWar Today")' in owner
    assert 'st.markdown("### What Should I Do?")' in owner
    assert "rank_today_actions(actions, limit=6)" in owner
    assert 'href="/glitch-radar"' in owner
    assert 'href="/fantasy-hq"' in owner
    assert 'href="/margin"' in owner
