from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_history_sync_keeps_popstate_reload_contract() -> None:
    source = (
        ROOT / "dashboard" / "control_state.py"
    ).read_text(encoding="utf-8")

    assert "__propwarHistorySyncHandler" in source
    assert 'removeEventListener("popstate"' in source
    assert 'addEventListener("popstate", handler)' in source
    assert "const target = host.location.href;" in source
    assert "host.location.replace(target)" in source


def test_browser_qa_exercises_back_and_forward_rendered_state() -> None:
    source = (
        ROOT / "scripts" / "run_three_report_launch_browser_qa.py"
    ).read_text(encoding="utf-8")

    assert "def verify_team_history_sync(" in source
    assert 'select_team("DAL")' in source
    assert 'select_team("PHI")' in source
    assert "page.go_back(" in source
    assert "browser Back did not restore DAL content" in source
