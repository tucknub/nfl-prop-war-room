from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_home_table_drops_weekly_report_attrs_before_streamlit_serialization() -> None:
    source = (
        ROOT / "dashboard" / "home_page.py"
    ).read_text(encoding="utf-8")

    assert "display.attrs.clear()" in source
    assert source.index("display.attrs.clear()") < source.index(
        "st.dataframe(",
        source.index("display.attrs.clear()"),
    )
