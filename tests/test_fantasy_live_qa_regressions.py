import ast
from pathlib import Path


PAGE = (
    Path(__file__).resolve().parents[1]
    / "dashboard"
    / "pages"
    / "11_Fantasy_HQ.py"
)


def _page_source() -> str:
    return PAGE.read_text(encoding="utf-8")


def test_fantasy_hq_gates_preseason_out_of_regular_week_features():
    source = _page_source()

    assert "_fantasy_regular_week(nfl_state)" in source
    assert "from src.fantasy.sleeper_current import fantasy_regular_week" not in source
    assert "nfl_state.week or nfl_state.display_week or 0" not in source


def test_market_start_sit_keeps_filled_uncovered_starters_visible():
    source = _page_source()

    assert "OPEN / UNCOVERED" not in source
    assert 'starter_name = starter_fact.name' in source
    assert '"UNSUPPORTED"' in source
    assert '"MISSING"' in source


def test_action_center_watch_metric_matches_watch_rows():
    source = _page_source()

    assert '"Watch / action leagues"' in source
    assert "len(action_center.action_leagues)" in source


def test_fantasy_hq_parallelizes_global_scan_without_blocking_selected_league():
    source = _page_source()

    assert "client.fetch_normalized_leagues(" in source
    assert "max_workers=3" in source
    assert "@st.fragment(parallel=True)" in source
    assert "def _render_all_league_decision_center(" in source

    render_source = source[source.index("def _render_sleeper()") :]
    selector = render_source.index("selector_leagues =")
    tabs = render_source.index('key="fantasy_primary_tabs"')
    selected_league_shell = render_source[selector:tabs]

    assert "_load_sleeper_league(" in selected_league_shell
    assert "for state in all_states" not in selected_league_shell
    assert 'with st.spinner("Loading league and roster..."):' in selected_league_shell


def test_background_refresh_is_limited_to_heavy_pure_fantasy_caches():
    source = _page_source()

    assert (
        '@st.cache_data(ttl=120, show_spinner=False, refresh_mode="background")\n'
        'def _load_all_sleeper_states('
    ) in source
    assert (
        '@st.cache_data(ttl=6 * 60 * 60, show_spinner=False, refresh_mode="background")\n'
        'def _load_player_catalog()'
    ) in source

    # Keep the composite action-feed cache foreground-only in this pass.
    assert (
        '@st.cache_data(ttl=5 * 60, show_spinner=False)\n'
        'def _load_weekly_action_feed('
    ) in source

    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for function_name in (
        "_load_all_sleeper_states",
        "_load_player_catalog",
    ):
        node = functions[function_name]
        body_nodes = (
            child
            for statement in node.body
            for child in ast.walk(statement)
        )
        assert not any(
            isinstance(child, ast.Name) and child.id == "st"
            for child in body_nodes
        )



def test_action_feed_uses_shared_bounded_weekly_context_loader():
    source = _page_source()

    assert "fetch_league_weekly_contexts(" in source
    assert "transaction_weeks=tuple(" in source
    assert "max_workers=3" in source

    start = source.index("def _load_weekly_action_feed(")
    end = source.index("\ndef _secret_default(", start)
    feed_source = source[start:end]

    assert "_load_matchups(" not in feed_source
    assert "_load_transactions(" not in feed_source
