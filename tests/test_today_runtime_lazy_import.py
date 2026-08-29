from __future__ import annotations

import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_today_runtime_source_does_not_eagerly_import_owner_stack() -> None:
    source = (
        ROOT / "dashboard" / "propwar_today_runtime.py"
    ).read_text(encoding="utf-8")

    assert "import propwar_today_owner as _owner_module" not in source
    assert "from dashboard import propwar_today_owner as _owner_module" not in source
    assert '_owner_module = None' in source
    assert 'importlib.import_module("propwar_today_owner")' in source


def test_importing_today_runtime_does_not_load_owner_module() -> None:
    sys.modules.pop("propwar_today_owner", None)
    sys.modules.pop("dashboard.propwar_today_owner", None)
    sys.modules.pop("dashboard.propwar_today_runtime", None)

    runtime = importlib.import_module("dashboard.propwar_today_runtime")

    assert runtime._owner_module is None
    assert "propwar_today_owner" not in sys.modules
    assert "dashboard.propwar_today_owner" not in sys.modules
