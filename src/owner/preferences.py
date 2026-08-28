from __future__ import annotations

from typing import Any, Mapping

from src.margin import state_store


DEFAULT_OWNER_PREFS_PATH = "owner/preferences.json"


def private_owner_preferences_config(
    secrets: Mapping[str, Any],
) -> dict[str, str] | None:
    """Reuse PropWar's existing private-state repository for owner preferences."""
    config = state_store.write_config_from_secrets(secrets)
    if config is None:
        return None
    return {
        **config,
        "path": (
            str(secrets.get("PROPWAR_OWNER_PREFS_PATH", "")).strip()
            or DEFAULT_OWNER_PREFS_PATH
        ),
    }


def fetch_owner_preferences(
    secrets: Mapping[str, Any],
) -> dict[str, Any]:
    config = private_owner_preferences_config(secrets)
    if config is None:
        return {}

    state, _sha = state_store.fetch_remote_state(config)
    return dict(state)


def sleeper_username_from_preferences(
    preferences: Mapping[str, Any],
) -> str:
    return str(preferences.get("sleeper_username") or "").strip()


__all__ = [
    "DEFAULT_OWNER_PREFS_PATH",
    "fetch_owner_preferences",
    "private_owner_preferences_config",
    "sleeper_username_from_preferences",
]
