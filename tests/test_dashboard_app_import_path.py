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

# Validation-only trigger for product gate after live import fix.
