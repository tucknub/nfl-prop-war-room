from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_fantasy_primary_tabs_use_lazy_execution() -> None:
    source = _source("dashboard/pages/11_Fantasy_HQ.py")

    assert 'key="fantasy_primary_tabs"' in source
    assert 'on_change="rerun"' in source

    for tab_name in (
        "roster_tab",
        "health_tab",
        "lineup_tab",
        "waiver_tab",
        "activity_tab",
        "matchup_tab",
        "opponent_tab",
        "team_explorer_tab",
        "standings_tab",
        "rules_tab",
        "cross_tab",
    ):
        assert f"if {tab_name}.open:" in source

    assert 'key="fantasy_yahoo_tabs"' in source
    assert "if settings_tab.open:" in source


def test_markets_primary_tabs_use_lazy_execution() -> None:
    source = _source("dashboard/pages/09_Glitch_Radar.py")

    assert 'key="markets_primary_tabs"' in source
    assert 'on_change="rerun"' in source

    for tab_name in (
        "glitch_tab",
        "arb_tab",
        "middle_tab",
        "ev_tab",
        "boost_tab",
        "source_tab",
    ):
        assert f"if {tab_name}.open:" in source


def test_fantasy_global_intelligence_does_not_block_league_shell() -> None:
    source = _source("dashboard/pages/11_Fantasy_HQ.py")

    assert "@st.fragment(parallel=True)\ndef _render_all_league_decision_center(" in source
    assert "_render_all_league_decision_center(" in source
    assert "needs_catalog = any(" in source
    assert "needs_all_states = any(" in source

    render_source = source[source.index("def _render_sleeper()") :]
    selector = render_source.index("selector_leagues =")
    tabs = render_source.index('key="fantasy_primary_tabs"')
    before_tabs = render_source[selector:tabs]

    assert "_load_sleeper_league(" in before_tabs
    assert "for state in all_states" not in before_tabs
