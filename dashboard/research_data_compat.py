from __future__ import annotations

import importlib

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


def _current_module():
    global _research_data
    if any(not hasattr(_research_data, name) for name in _REQUIRED):
        _research_data = importlib.reload(_research_data)
    return _research_data


def _export(name: str):
    module = _current_module()
    if not hasattr(module, name):
        raise ImportError(
            f"research_data is missing required production symbol {name!r} "
            "even after a cold-source reload"
        )
    return getattr(module, name)


ROLE_LABELS = _export("ROLE_LABELS")
available_seasons = _export("available_seasons")
available_weeks = _export("available_weeks")
explorer_usage = _export("explorer_usage")
game_usage = _export("game_usage")
league_window_summary = _export("league_window_summary")
load_operational_status = _export("load_operational_status")
load_opportunity_events = _export("load_opportunity_events")
load_production_data = _export("load_production_data")
load_situational_data = _export("load_situational_data")
operational_status_text = _export("operational_status_text")
opponent_from_game_id = _export("opponent_from_game_id")
player_profile = _export("player_profile")
player_selector_rows = _export("player_selector_rows")
player_window_table = _export("player_window_table")
primary_rows = _export("primary_rows")
situational_team_summary = _export("situational_team_summary")
team_window_summary = _export("team_window_summary")


__all__ = list(_REQUIRED)
