from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_browser_qa_exercises_native_home_report_navigation() -> None:
    source = (ROOT / "scripts" / "run_three_report_launch_browser_qa.py").read_text(
        encoding="utf-8"
    )

    assert 'get_by_role("button", name="View Backfield Control", exact=True)' in source
    assert 'validate_report_href(page.url, "Backfield Control")' in source
    assert 'get_by_role("heading", name=REPORT_HEADING, exact=True)' in source
    assert 'get_by_role("link", name="View Backfield Control", exact=True)' not in source
