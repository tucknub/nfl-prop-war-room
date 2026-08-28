from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


def test_home_routes_directly_to_each_report() -> None:
    source = (DASHBOARD / "app.py").read_text(encoding="utf-8")
    copy_source = (DASHBOARD / "public_copy.py").read_text(encoding="utf-8")
    assert "role_home_copy" in source
    assert "Latest NFL role research" in copy_source
    assert "What changed in NFL roles?" in copy_source
    assert 'href="/reports?report={quote(title)}"' in source
    assert "View {title}</a>" in source
    assert "Open Reports" not in source


def test_reports_default_to_answers_before_advanced_controls() -> None:
    source = (DASHBOARD / "pages" / "04_Reports.py").read_text(encoding="utf-8")
    assert 'with st.expander("Customize report")' in source
    assert "expanded=True" not in source
    assert 'section("Top findings"' in source
    assert '"Time period"' in source
    assert '"Minimum opportunities to appear"' in source
    assert '"Team share"' in source
    assert 'st.query_params.get("report"' in source


def test_complete_report_uses_compact_default_and_optional_evidence() -> None:
    source = (DASHBOARD / "pages" / "04_Reports.py").read_text(encoding="utf-8")
    assert "compact_columns = [" in source
    assert 'with st.expander("Show all evidence columns")' in source
    assert '"Opportunities"' in source
    assert '"Team total"' in source
    assert '"Typical-game share"' in source


def test_methodology_is_scannable_without_a_wide_contract_table() -> None:
    source = (DASHBOARD / "pages" / "06_Methodology.py").read_text(encoding="utf-8")
    assert 'section("How to read a report"' in source
    assert 'section("Plain-language terms"' in source
    assert 'with st.expander("Calculation details")' in source
    assert "st.dataframe" not in source
    assert "overview(" in source


def test_native_top_navigation_and_hosted_chrome_cleanup_are_present() -> None:
    source = (DASHBOARD / "app.py").read_text(encoding="utf-8")
    assert '[data-testid="stHeader"]' in source
    assert '[data-testid="stToolbar"]' in source
    assert "#viewerBadge_link" in source
    assert 'st.navigation(pages, position="top").run()' in source
    assert '"PropWar"' in source
    assert '"More"' in source
    assert '"Role Intelligence"' in source
    assert "with st.sidebar" not in source
    assert ".pw-home-hero" in source
    assert ".pw-status-line" in source
