from dashboard.glitch_radar_action import BET
from dashboard.propwar_today import MARKET, MEDIUM
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



def test_today_recovers_preseason_date_from_matching_snapshot_quote():
    snapshot = {
        "fetched_at": "2026-08-28T13:58:00+00:00",
        "alerts": [],
        "quotes": [
            {
                "book": "FanDuel",
                "event": "Arizona Cardinals @ Green Bay Packers",
                "market": "moneyline",
                "side": "away",
                "odds_american": 450,
                "commence_time": "2026-08-29T00:00:00.000Z",
            }
        ],
        "ev": [
            {
                "away_team": "Arizona Cardinals",
                "home_team": "Green Bay Packers",
                "side": "Arizona Cardinals",
                "selection": "Arizona Cardinals",
                "book": "FanDuel",
                "price": 450,
                "fair_prob_pct": 19.5,
                "market": "moneyline",
            }
        ],
    }

    actions = _market_actions(snapshot)

    assert len(actions) == 1
    assert actions[0].priority == MEDIUM
    assert actions[0].confidence == "MEDIUM"
    assert actions[0].why.startswith("PRESEASON · ")



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

    assert 'st.markdown("## PropWar Today")' not in owner
    assert 'st.markdown("## What Should I Do?")' in owner
    assert "rank_today_actions(actions, limit=6)" in owner
    assert 'href="/glitch-radar"' in owner
    assert '"/fantasy-hq?"' in owner
    assert 'urlencode({"fh_sleeper": username})' in owner
    assert 'href="/margin"' in owner


def test_today_uses_bounded_parallel_sleeper_loading_and_background_catalog() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    owner = (root / "dashboard" / "propwar_today_owner.py").read_text(
        encoding="utf-8"
    )

    assert "client.fetch_normalized_leagues(" in owner
    assert "max_workers=3" in owner
    assert (
        "@st.cache_data(ttl=6 * 60 * 60, show_spinner=False, "
        'refresh_mode="background")\ndef _today_player_catalog()'
    ) in owner
