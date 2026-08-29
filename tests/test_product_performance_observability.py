from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_product_gate_records_page_startup_timing_evidence() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "propwar-product-gate.yml"
    ).read_text(encoding="utf-8")

    assert "time.perf_counter()" in workflow
    assert 'Path("/tmp/propwar-startup-timings.json")' in workflow
    assert '"seconds": round(elapsed, 3)' in workflow
    assert "Slowest visible page startups:" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "name: propwar-startup-timings" in workflow


def test_performance_observability_is_measurement_not_flaky_budget() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "propwar-product-gate.yml"
    ).read_text(encoding="utf-8")

    assert "test_product_performance_observability.py" in workflow
    assert "startup timing budget exceeded" not in workflow.lower()
