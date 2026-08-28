from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_today_has_one_decision_heading_and_required_action_metadata() -> None:
    source = _source("dashboard/propwar_today_owner.py")

    assert 'st.markdown("## What Should I Do?")' in source
    assert 'st.markdown("## PropWar Today")' not in source
    assert "Confidence:" in source
    assert "Freshness:" in source
    assert "row.action" in source
    assert "row.why" in source


def test_owner_players_is_command_first_with_detail_evidence_collapsed() -> None:
    source = _source("dashboard/pages/02_Players.py")

    assert '"Player Command Center"' in source
    assert '"Player Role Profile"' in source
    assert 'st.expander("Detailed role evidence", expanded=False)' in source
    assert "owner_command_mode = owner_player_command_available()" in source
    assert "render_owner_player_command_center(" in source


def test_markets_has_four_decision_tabs_plus_one_secondary_tab() -> None:
    source = _source("dashboard/pages/09_Glitch_Radar.py")

    assert (
        '["Glitches", "Arbs", "Middles", "+EV Prices", "More"]'
        in source
    )
    assert "boost_tab = more_tab" in source
    assert "source_tab = more_tab" in source
    assert '"Boost Lab", "Coverage"' not in source


def test_fantasy_has_seven_decision_tabs_not_eleven_feature_tabs() -> None:
    source = _source("dashboard/pages/11_Fantasy_HQ.py")

    expected = """[
            "Team",
            "Start / Sit",
            "Waivers",
            "Matchup",
            "Trades",
            "League",
            "Across leagues",
        ]"""
    assert expected in source

    assert "roster_tab = team_tab" in source
    assert "health_tab = team_tab" in source
    assert "opponent_tab = matchup_tab" in source
    assert "team_explorer_tab = trade_tab" in source
    assert "activity_tab = league_tab" in source
    assert "standings_tab = league_tab" in source
    assert "rules_tab = league_tab" in source

def test_fantasy_keeps_one_primary_priority_system() -> None:
    source = _source("dashboard/pages/11_Fantasy_HQ.py")

    assert 'st.markdown("### What Should I Do?")' in source
    assert 'st.expander("All-league health & coverage", expanded=False)' in source
    assert 'st.markdown("#### All-league status")' in source
    assert 'st.markdown("### All-Leagues Action Center")' not in source


def test_yahoo_is_secondary_not_a_primary_provider_tab() -> None:
    source = _source("dashboard/pages/11_Fantasy_HQ.py")

    assert 'page_intro(\n    "Fantasy",' in source
    assert "_render_sleeper()" in source
    assert 'st.expander("Optional Yahoo · parked", expanded=False)' in source
    assert 'st.tabs(["Sleeper leagues", "Yahoo leagues"])' not in source


def test_core_internal_deep_links_target_registered_routes() -> None:
    app = _source("dashboard/app.py")
    sources = "\n".join(
        [
            app,
            _source("dashboard/propwar_today_owner.py"),
        ]
    )

    registered = set(re.findall(r'url_path="([^"]*)"', app))
    internal_paths = set(re.findall(r'href="(/[^"? ]+)', sources))
    internal_paths.update(
        re.findall(r'href="(/[^"? ]+)', _source("dashboard/app.py"))
    )
    internal_paths.update(
        re.findall(
            r'href="/([a-z0-9-]+)',
            _source("dashboard/propwar_today_owner.py"),
        )
    )

    normalized = {path.lstrip("/") for path in internal_paths}
    normalized.discard("")

    assert {"reports", "glitch-radar", "fantasy-hq", "margin"} <= registered
    assert normalized <= registered


def test_owner_navigation_hides_deep_research_but_keeps_context_links() -> None:
    app = _source("dashboard/app.py")
    markets = _source("dashboard/pages/09_Glitch_Radar.py")
    reports = _source("dashboard/pages/04_Reports.py")

    owner_more = app[app.index('"More": [') :]
    assert (
        'title="Advanced Research", icon=":material/search:", '
        'url_path="explorer", visibility="hidden"'
    ) in owner_more
    assert (
        'title="Market Research", icon=":material/query_stats:", '
        'url_path="deep-prop-radar", visibility="hidden"'
    ) in owner_more
    assert 'title="Margin"' in owner_more
    assert 'title="Knockout"' in owner_more

    assert "/deep-prop-radar" in markets
    assert "/explorer" in reports
