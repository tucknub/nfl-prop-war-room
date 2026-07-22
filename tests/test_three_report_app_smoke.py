from __future__ import annotations

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
if str(DASHBOARD) not in sys.path:
    sys.path.insert(0, str(DASHBOARD))


@pytest.mark.parametrize(
    "relative_path",
    (
        "dashboard/Home.py",
        "dashboard/pages/04_Reports.py",
        "dashboard/pages/06_Methodology.py",
    ),
)
def test_three_report_public_pages_execute_without_exception(relative_path: str) -> None:
    app = AppTest.from_file(str(ROOT / relative_path), default_timeout=120)
    app.run()
    assert not app.exception, [str(item.value) for item in app.exception]
