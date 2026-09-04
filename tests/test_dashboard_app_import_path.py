from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_dashboard_app_imports_from_outside_repo_root(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    app = repo_root / "dashboard" / "app.py"

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import runpy; "
                f"runpy.run_path({str(app)!r}, run_name='propwar_import_probe')"
            ),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        "dashboard/app.py must import successfully even when the process working "
        "directory is outside the repository root.\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )



def test_research_ui_owns_formatters_without_research_data_symbol_import() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "dashboard" / "research_ui.py").read_text(encoding="utf-8")

    assert "from research_data import percent, pp" not in source
    assert "def percent(value: object)" in source
    assert "def pp(value: object)" in source



def test_public_role_pages_use_reload_safe_research_data_boundary() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    compat = (repo_root / "dashboard" / "research_data_compat.py").read_text(encoding="utf-8")

    assert "importlib.reload(_research_data)" in compat
    assert "even after a cold-source reload" in compat

    for relative in (
        "dashboard/pages/01_Teams.py",
        "dashboard/pages/02_Players.py",
        "dashboard/pages/03_Games.py",
        "dashboard/pages/04_Reports.py",
        "dashboard/pages/05_Explorer.py",
        "dashboard/pages/06_Methodology.py",
        "dashboard/home_page.py",
    ):
        source = (repo_root / relative).read_text(encoding="utf-8")
        assert "research_data_compat" in source
