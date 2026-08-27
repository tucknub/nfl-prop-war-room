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
