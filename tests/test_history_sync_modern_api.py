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
    assert "height=0" in source
    assert "tab_index=-1" in source
    assert "__propwarHistorySyncInstalled" in source
    assert 'addEventListener("popstate"' in source
