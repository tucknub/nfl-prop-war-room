from __future__ import annotations

import importlib
from pathlib import Path

_owner_module = None
_loaded_mtime_ns = 0


def _import_owner_module():
    try:
        return importlib.import_module("propwar_today_owner")
    except ImportError:
        return importlib.import_module("dashboard.propwar_today_owner")


def _current_module():
    global _owner_module, _loaded_mtime_ns

    if _owner_module is None:
        _owner_module = _import_owner_module()
        module_path = Path(str(getattr(_owner_module, "__file__", "") or ""))
        try:
            _loaded_mtime_ns = module_path.stat().st_mtime_ns
        except OSError:
            _loaded_mtime_ns = 0
        return _owner_module

    module_path = Path(str(getattr(_owner_module, "__file__", "") or ""))
    try:
        mtime_ns = module_path.stat().st_mtime_ns
    except OSError:
        mtime_ns = 0

    if mtime_ns and mtime_ns != _loaded_mtime_ns:
        _owner_module = importlib.reload(_owner_module)
        _loaded_mtime_ns = mtime_ns
    elif not _loaded_mtime_ns:
        _loaded_mtime_ns = mtime_ns

    return _owner_module


def render_propwar_today_if_owner() -> None:
    _current_module().render_propwar_today_if_owner()


__all__ = ["render_propwar_today_if_owner"]
