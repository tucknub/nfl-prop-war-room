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


def _configured_owner_secrets() -> dict:
    return {
        "PROPWAR_OWNER_EMAIL": "owner@example.com",
        "auth": {
            "redirect_uri": "https://propwar.streamlit.app/oauth2callback",
            "cookie_secret": "test-cookie-secret",
            "client_id": "test-client",
            "client_secret": "test-secret",
            "server_metadata_url": "https://accounts.google.com/.well-known/openid-configuration",
        },
    }


def test_owner_access_requires_matching_verified_oidc_email() -> None:
    from dashboard.access_control import access_mode, owner_authenticated

    secrets = _configured_owner_secrets()

    assert access_mode(secrets, {"is_logged_in": False}) == "ANONYMOUS"
    assert access_mode(
        secrets,
        {
            "is_logged_in": True,
            "email": "owner@example.com",
            "email_verified": True,
        },
    ) == "OWNER"
    assert access_mode(
        secrets,
        {
            "is_logged_in": True,
            "email": "someone-else@example.com",
            "email_verified": True,
        },
    ) == "NON_OWNER"
    assert not owner_authenticated(
        secrets,
        {
            "is_logged_in": True,
            "email": "owner@example.com",
            "email_verified": False,
        },
    )


def test_owner_navigation_registers_all_private_routes_only_in_owner_mode() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app = (root / "dashboard" / "app.py").read_text(encoding="utf-8")
    owner_block = app.index('if mode == "OWNER":', app.index("def main()"))

    private_routes = {
        "glitch-radar": "pages/09_Glitch_Radar.py",
        "fantasy-hq": "pages/11_Fantasy_HQ.py",
        "deep-prop-radar": "pages/10_Deep_Prop_Radar.py",
        "margin": "pages/07_Margin_War_Room.py",
        "knockout": "pages/08_Knockout_Fantasy_War_Room.py",
    }
    for route, page in private_routes.items():
        route_marker = f'url_path="{route}"'
        page_marker = f'st.Page("{page}"'
        assert route_marker in app
        assert page_marker in app
        assert app.index(route_marker) > owner_block
        assert app.index(page_marker) > owner_block


def test_sensitive_owner_pages_keep_defense_in_depth_guards() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    deep_prop = (root / "dashboard" / "pages" / "10_Deep_Prop_Radar.py").read_text(
        encoding="utf-8"
    )
    knockout = (
        root / "dashboard" / "pages" / "08_Knockout_Fantasy_War_Room.py"
    ).read_text(encoding="utf-8")

    assert "def _require_owner()" in deep_prop
    assert deep_prop.index("_require_owner()") < deep_prop.index('st.markdown("## Market Research")')

    assert "state_store.owner_write_authorized(config)" in knockout
    assert knockout.index("state_store.owner_write_authorized(config)") < knockout.index(
        'section(\n    "What Should I Do?"'
    )
