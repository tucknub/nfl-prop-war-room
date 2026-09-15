from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable

try:
    import research_data as _research_data
except ImportError:  # package import path used by tests/tools
    from dashboard import research_data as _research_data


_REQUIRED = (
    "ROLE_LABELS",
    "available_seasons",
    "available_weeks",
    "explorer_usage",
    "game_usage",
    "league_window_summary",
    "load_operational_status",
    "load_opportunity_events",
    "load_production_data",
    "load_situational_data",
    "operational_status_text",
    "opponent_from_game_id",
    "player_profile",
    "player_selector_rows",
    "player_window_table",
    "primary_rows",
    "situational_team_summary",
    "team_window_summary",
)

_DATA_SIGNATURE: tuple[tuple[str, int, int], ...] | None = None


def _role_data_signature() -> tuple[tuple[str, int, int], ...]:
    root = Path(__file__).resolve().parents[1] / "outputs" / "role_research"
    if not root.exists():
        return ()
    watched = [
        path
        for path in root.iterdir()
        if path.is_file()
        and (
            "_live." in path.name
            or path.name.startswith("role_research_status_")
            or path.name.startswith("role_research_manifest_")
        )
    ]
    return tuple(
        sorted(
            (path.name, path.stat().st_mtime_ns, path.stat().st_size)
            for path in watched
        )
    )


def _current_module():
    global _research_data, _DATA_SIGNATURE
    signature = _role_data_signature()
    missing = any(not hasattr(_research_data, name) for name in _REQUIRED)
    changed = _DATA_SIGNATURE is not None and signature != _DATA_SIGNATURE
    if missing or changed:
        _research_data = importlib.reload(_research_data)
    _DATA_SIGNATURE = signature
    return _research_data


def _export(name: str):
    module = _current_module()
    if not hasattr(module, name):
        raise ImportError(
            f"research_data is missing required production symbol {name!r} "
            "even after a cold-source reload"
        )
    return getattr(module, name)


def _proxy(name: str) -> Callable[..., Any]:
    def call(*args: Any, **kwargs: Any) -> Any:
        return _export(name)(*args, **kwargs)

    call.__name__ = name
    return call


ROLE_LABELS = _export("ROLE_LABELS")
available_seasons = _proxy("available_seasons")
available_weeks = _proxy("available_weeks")
explorer_usage = _proxy("explorer_usage")
game_usage = _proxy("game_usage")
league_window_summary = _proxy("league_window_summary")
load_operational_status = _proxy("load_operational_status")
load_opportunity_events = _proxy("load_opportunity_events")
load_production_data = _proxy("load_production_data")
load_situational_data = _proxy("load_situational_data")
operational_status_text = _proxy("operational_status_text")
opponent_from_game_id = _proxy("opponent_from_game_id")
player_profile = _proxy("player_profile")
player_selector_rows = _proxy("player_selector_rows")
player_window_table = _proxy("player_window_table")
primary_rows = _proxy("primary_rows")
situational_team_summary = _proxy("situational_team_summary")
team_window_summary = _proxy("team_window_summary")


__all__ = list(_REQUIRED)
