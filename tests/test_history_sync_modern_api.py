from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_browser_history_sync_uses_current_streamlit_iframe_api() -> None:
    source = (
        ROOT / "dashboard" / "control_state.py"
    ).read_text(encoding="utf-8")

    assert "streamlit.components.v1" not in source
    assert "components.html(" not in source
    assert "st.iframe(" in source
    assert "height=1" in source
    assert "tab_index=-1" in source
    assert "__propwarHistorySyncInstalled" in source
    assert 'addEventListener("popstate"' in source


def test_browser_qa_exercises_history_back_and_forward() -> None:
    source = (
        ROOT / "scripts" / "run_three_report_launch_browser_qa.py"
    ).read_text(encoding="utf-8")

    assert "def verify_team_history_sync(" in source
    assert "page.go_back(" in source
    assert "page.go_forward(" in source
    assert "browser Back did not restore DAL" in source
    assert "browser Forward did not restore PHI" in source
