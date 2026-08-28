from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_product_gate_matches_production_runtime_and_all_visible_pages() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "propwar-product-gate.yml"
    ).read_text(encoding="utf-8")

    assert 'python-version: "3.14"' in workflow
    assert 'python-version: "3.12"' not in workflow

    expected = (
        'root / "dashboard" / "app.py"',
        "01_Teams.py",
        "02_Players.py",
        "03_Games.py",
        "04_Reports.py",
        "05_Explorer.py",
        "06_Methodology.py",
        "07_Margin_War_Room.py",
        "08_Knockout_Fantasy_War_Room.py",
        "09_Glitch_Radar.py",
        "10_Deep_Prop_Radar.py",
        "11_Fantasy_HQ.py",
    )
    for page in expected:
        assert page in workflow

    assert "90_Admin_Research.py" not in workflow
    assert 'os.chdir("/tmp")' in workflow
    assert "AppTest.from_file" in workflow


def test_product_gate_runs_live_proving_and_product_contracts() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "propwar-product-gate.yml"
    ).read_text(encoding="utf-8")

    required = (
        "tests/test_product_consolidation.py",
        "tests/test_product_consolidation_phase2.py",
        "tests/test_dashboard_app_import_path.py",
        "tests/test_public_role_research_language.py",
        "tests/test_propwar_today.py",
        "tests/test_propwar_today_owner.py",
        "tests/test_player_command_center.py",
        "tests/test_live_proving_round*.py",
        "tests/test_glitch_radar_*.py",
        "tests/test_fantasy_*.py",
        "tests/test_knockout_fantasy.py",
        "tests/test_margin_championship.py",
        "tests/test_margin_pool_state.py",
        "tests/test_margin_state_store.py",
        "tests/test_role_change_detector.py",
        "tests/test_role_research.py",
        "tests/test_role_validation.py",
        "tests/test_weekly_role_report.py",
    )
    for pattern in required:
        assert pattern in workflow
