from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import dashboard.league_selector_compat as compat
from dashboard.propwar_today import MEDIUM
from dashboard.propwar_today_owner import _market_actions


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_selector_compat_survives_cached_module_without_new_helper(monkeypatch) -> None:
    stale_module = SimpleNamespace(
        build_sleeper_league_options=compat.build_sleeper_league_options,
    )
    monkeypatch.setattr(compat, "_league_selector", stale_module)

    options = {
        "Franchise Football League · 10 teams": "real-1",
        "TEST LEAGUE · 10 teams": "demo-1",
    }
    selected = compat.choose_sleeper_league_label(
        options,
        demo_league_ids={"demo-1"},
        legacy_label="TEST LEAGUE · 10 teams",
        prefer_real=True,
    )

    assert selected == "Franchise Football League · 10 teams"


def test_fantasy_and_player_pages_use_reload_safe_selector_compat() -> None:
    fantasy = _source("dashboard/pages/11_Fantasy_HQ.py")
    player = _source("dashboard/player_command_owner.py")

    assert "from league_selector_compat import (" in fantasy
    assert "from src.fantasy.league_selector import (" not in fantasy
    assert "from league_selector_compat import (" in player
    assert "from dashboard.league_selector_compat import (" in player


def test_today_can_classify_live_preseason_even_when_event_date_is_missing() -> None:
    snapshot = {
        "fetched_at": "2026-08-28T18:50:00+00:00",
        "alerts": [],
        "quotes": [],
        "ev": [
            {
                "side": "Arizona Cardinals",
                "selection": "Arizona Cardinals",
                "book": "FanDuel",
                "price": 450,
                "fair_prob_pct": 19.5,
                "market": "moneyline",
            }
        ],
    }

    actions = _market_actions(snapshot, force_preseason=True)

    assert len(actions) == 1
    assert actions[0].priority == MEDIUM
    assert actions[0].confidence == "MEDIUM"
    assert actions[0].why.startswith("PRESEASON · ")


def test_today_recovers_event_date_without_away_home_pair() -> None:
    snapshot = {
        "fetched_at": "2026-08-28T18:50:00+00:00",
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
    assert actions[0].why.startswith("PRESEASON · ")


def test_home_routes_today_through_source_mtime_runtime_loader() -> None:
    app = _source("dashboard/app.py")
    runtime = _source("dashboard/propwar_today_runtime.py")

    assert "from propwar_today_runtime import render_propwar_today_if_owner" in app
    assert "importlib.reload(_owner_module)" in runtime
    assert "st_mtime_ns" in runtime
