from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_legacy_three_report_workflow_is_retired() -> None:
    assert not (ROOT / ".github" / "workflows" / "three-report-mvp.yml").exists()


def test_public_role_browser_qa_uses_production_runtime_and_playwright() -> None:
    workflow = _read(".github/workflows/public-role-browser-qa.yml")

    assert 'name: Public Role Browser QA' in workflow
    assert 'python-version: "3.14"' in workflow
    assert 'python-version: "3.12"' not in workflow
    assert "playwright install --with-deps chromium" in workflow
    assert "run_three_report_launch_browser_qa.py" in workflow
    assert "dashboard/Home.py" in workflow
    assert "tests/test_public_role_research_language.py" in workflow
    assert "workers/fantasy-hq/*.test.mjs" not in workflow


def test_fantasy_worker_tests_are_isolated_from_streamlit_browser_qa() -> None:
    workflow = _read(".github/workflows/fantasy-worker-tests.yml")

    assert "name: Fantasy Worker Tests" in workflow
    assert "node --test workers/fantasy-hq/*.test.mjs" in workflow
    assert "playwright" not in workflow.lower()
    assert "streamlit" not in workflow.lower()
    assert 'workers/fantasy-hq/**' in workflow


def test_permanent_product_gate_remains_whole_product_authority() -> None:
    workflow = _read(".github/workflows/propwar-product-gate.yml")

    assert "name: PropWar Product Gate" in workflow
    assert 'python-version: "3.14"' in workflow
    assert "Start every visible Streamlit page" in workflow
