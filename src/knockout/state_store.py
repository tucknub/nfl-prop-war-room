from __future__ import annotations

from typing import Any, Mapping

from src.margin import state_store as private_store


DEFAULT_STATE_PATH = "knockout/live_state_2026.json"


def config_from_secrets(secrets: Mapping[str, Any]) -> dict[str, str] | None:
    config = private_store.config_from_secrets(secrets)
    if config is None:
        return None
    return {
        **config,
        "path": str(secrets.get("KNOCKOUT_STATE_PATH", DEFAULT_STATE_PATH)).strip() or DEFAULT_STATE_PATH,
    }


def owner_write_authorized(config: Mapping[str, str]) -> bool:
    return private_store.owner_write_authorized(config)


def fetch_remote_state(config: Mapping[str, str]) -> tuple[dict[str, Any], str]:
    return private_store.fetch_remote_state(config)


def write_remote_state(
    config: Mapping[str, str],
    state: dict[str, Any],
    *,
    expected_sha: str,
    message: str,
) -> str:
    return private_store.write_remote_state(config, state, expected_sha=expected_sha, message=message)
