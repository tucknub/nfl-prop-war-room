from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_deep_prop_radar_uses_lazy_diagnostic_tabs() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "10_Deep_Prop_Radar.py"
    ).read_text(encoding="utf-8")

    assert 'key="deep_prop_radar_tabs"' in source
    assert 'on_change="rerun"' in source
    for tab_name in (
        "price_tab",
        "shop_tab",
        "watch_tab",
        "gap_tab",
        "ladder_tab",
        "stale_tab",
        "coverage_tab",
    ):
        assert f"if {tab_name}.open:" in source


def test_deep_prop_force_refresh_clears_real_shared_cache() -> None:
    source = (
        ROOT / "dashboard" / "pages" / "10_Deep_Prop_Radar.py"
    ).read_text(encoding="utf-8")

    assert "shared_prop_snapshot.clear()" in source
    assert "_deep_snapshot.clear()" not in source
