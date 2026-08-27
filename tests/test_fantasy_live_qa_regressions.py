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


def test_fantasy_hq_parallelizes_all_leagues_and_reuses_selected_state():
    source = _page_source()

    assert "client.fetch_normalized_leagues(" in source
    assert "max_workers=3" in source
    assert "for state in all_states" in source
    assert "if league is None:" in source
    assert 'with st.spinner("Loading league and roster..."):' in source


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
        assert not any(
            isinstance(child, ast.Name) and child.id == "st"
            for child in ast.walk(node)
        )
