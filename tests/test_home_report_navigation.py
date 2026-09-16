from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_home_report_cards_use_native_streamlit_navigation() -> None:
    source = (ROOT / "dashboard" / "app.py").read_text(encoding="utf-8")
    compact = " ".join(source.split())

    assert 'st.switch_page( "pages/04_Reports.py", query_params={"report": title}, )' in compact
    assert 'href="/reports?report=' not in source
    assert "from urllib.parse import quote" not in source
