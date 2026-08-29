from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_teams_uses_native_query_binding_for_filter_url_state() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "01_Teams.py"
    ).read_text(encoding="utf-8")

    assert "enable_browser_history_sync()" not in source
    assert source.count('bind="query-params"') == 3


def test_browser_qa_keeps_bound_filters_out_of_back_history() -> None:
    source = (
        ROOT / "scripts" / "run_three_report_launch_browser_qa.py"
    ).read_text(encoding="utf-8")

    assert "def verify_team_history_sync(" in source
    assert 'select_team("DAL")' in source
    assert 'select_team("PHI")' in source
    assert "page.go_back(" in source
    assert "browser Back remained trapped in Teams filter history" in source
    assert "browser Back leaked Teams filter state onto the previous page" in source
