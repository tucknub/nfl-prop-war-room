from __future__ import annotations

import importlib
from pathlib import Path

try:
    import propwar_today_owner as _owner_module
except ImportError:
    from dashboard import propwar_today_owner as _owner_module


_loaded_mtime_ns = 0


def _current_module():
    global _owner_module, _loaded_mtime_ns

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
