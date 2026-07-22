from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
if str(DASHBOARD) not in sys.path:
    sys.path.insert(0, str(DASHBOARD))

from launch_contract import REPORT_DEFINITIONS, REPORT_FAMILIES, REPORT_ORDER  # noqa: E402


def test_launch_contains_exactly_three_locked_reports() -> None:
    assert REPORT_ORDER == (
        "Backfield Control",
        "Target Hierarchy",
        "Role Movement",
    )
    assert tuple(REPORT_DEFINITIONS) == REPORT_ORDER
    assert tuple(REPORT_FAMILIES) == REPORT_ORDER


def test_launch_report_families_are_closed() -> None:
    assert REPORT_FAMILIES["Backfield Control"] == (
        "rb_carry_share",
        "rb_opportunity_share",
    )
    assert REPORT_FAMILIES["Target Hierarchy"] == (
        "wr_target_share",
        "te_target_share",
    )
    assert set(REPORT_FAMILIES["Role Movement"]) == {
        "rb_carry_share",
        "rb_opportunity_share",
        "wr_target_share",
        "te_target_share",
    }


def test_navigation_exposes_reports_and_methodology() -> None:
    source = (DASHBOARD / "app.py").read_text(encoding="utf-8")
    assert 'title="Reports"' in source
    assert 'title="Methodology"' in source
    assert "NFL ROLE INTELLIGENCE" in source


def test_reports_page_declares_all_play_authority() -> None:
    source = (DASHBOARD / "pages" / "04_Reports.py").read_text(encoding="utf-8")
    assert "ALL_PLAY_AUTHORITY_NOTICE" in source
    assert '"All plays"' in source
    assert '"Normal game"' in source
    assert "Opportunity Versus Production" not in source
    assert "Game-Script Usage" not in source
