from __future__ import annotations

import base64
import json
from copy import deepcopy
from threading import RLock
from typing import Any, Mapping

import httpx

from src.margin import state_store

try:
    from glitch_radar_history import empty_market_history, update_market_history
except ImportError:
    from dashboard.glitch_radar_history import empty_market_history, update_market_history


DEFAULT_HISTORY_PATH = "glitch/market_history.json"
GITHUB_API = "https://api.github.com"


def history_config_from_secrets(
    secrets: Mapping[str, Any],
) -> dict[str, str] | None:
    base = state_store.config_from_secrets(secrets)
    if base is None:
        return None
    path = str(
        secrets.get("GLITCH_HISTORY_STATE_PATH", DEFAULT_HISTORY_PATH)
        or DEFAULT_HISTORY_PATH
    ).strip()
    return {
        **base,
        "path": path or DEFAULT_HISTORY_PATH,
    }


class PrivateMarketHistoryStore:
    """Durable owner-only market history in the existing private state repo."""

    def __init__(self, config: Mapping[str, str]) -> None:
        self._config = dict(config)
        self._lock = RLock()
        self._loaded = False
        self._state = empty_market_history()
        self._sha: str | None = None

    def update(
        self,
        observations: Mapping[str, Mapping[str, Any]],
        *,
        fetched_at: str,
    ) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            updated = update_market_history(
                self._state,
                observations,
                fetched_at=fetched_at,
            )
            if updated == self._state:
                return deepcopy(self._state)

            try:
                self._sha = self._write_remote(
                    updated,
                    expected_sha=self._sha,
                )
            except RuntimeError as exc:
                if "conflict" not in str(exc).casefold():
                    raise
                # Another worker/tab wrote newer history. Reload once and
                # recompute against the authoritative state instead of clobbering it.
                self._state, self._sha = self._load_remote()
                updated = update_market_history(
                    self._state,
                    observations,
                    fetched_at=fetched_at,
                )
                if updated != self._state:
                    self._sha = self._write_remote(
                        updated,
                        expected_sha=self._sha,
                    )

            self._state = updated
            return deepcopy(self._state)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            return deepcopy(self._state)

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        state_store.assert_private_repository(self._config)
        self._state, self._sha = self._load_remote()
        self._loaded = True

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._config['token']}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "PropWar-Glitch-History",
        }

    def _contents_url(self) -> str:
        repo = str(self._config["repo"]).strip()
        path = str(self._config["path"]).strip().lstrip("/")
        return f"{GITHUB_API}/repos/{repo}/contents/{path}"

    def _load_remote(self) -> tuple[dict[str, Any], str | None]:
        response = httpx.get(
            self._contents_url(),
            params={"ref": self._config["branch"]},
            headers=self._headers(),
            timeout=20.0,
            follow_redirects=True,
        )
        if response.status_code == 404:
            return empty_market_history(), None
        if response.status_code >= 400:
            raise RuntimeError(
                f"Glitch history read failed ({response.status_code}): "
                f"{response.text[:250]}"
            )

        payload = response.json()
        try:
            raw = base64.b64decode(payload["content"]).decode("utf-8")
            state = json.loads(raw)
        except Exception as exc:
            raise RuntimeError(
                "Private glitch history file is not valid JSON state."
            ) from exc
        if not isinstance(state, dict):
            raise RuntimeError(
                "Private glitch history file must contain one JSON object."
            )
        return state, str(payload.get("sha") or "") or None

    def _write_remote(
        self,
        state: Mapping[str, Any],
        *,
        expected_sha: str | None,
    ) -> str:
        encoded = base64.b64encode(
            (json.dumps(dict(state), indent=2) + "\n").encode("utf-8")
        ).decode("ascii")
        payload: dict[str, Any] = {
            "message": "Update Glitch Radar market history",
            "content": encoded,
            "branch": self._config["branch"],
        }
        if expected_sha:
            payload["sha"] = expected_sha

        response = httpx.put(
            self._contents_url(),
            headers={
                **self._headers(),
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20.0,
            follow_redirects=True,
        )
        if response.status_code in {409, 422}:
            raise RuntimeError(
                "Glitch history write conflict; authoritative state changed."
            )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Glitch history write failed ({response.status_code}): "
                f"{response.text[:250]}"
            )
        result = response.json()
        sha = str(result.get("content", {}).get("sha") or "")
        if not sha:
            raise RuntimeError(
                "Glitch history write succeeded without a returned file SHA."
            )
        return sha


__all__ = [
    "DEFAULT_HISTORY_PATH",
    "PrivateMarketHistoryStore",
    "history_config_from_secrets",
]
