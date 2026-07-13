from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise ValueError(f"Configuration must be a mapping: {config_path}")
    return config


def canonical_config_bytes(config: dict[str, Any]) -> bytes:
    clean = json.loads(json.dumps(config))
    status = clean.setdefault("status", {})
    status["frozen_at_utc"] = None
    status["frozen_config_sha256"] = None
    return json.dumps(clean, sort_keys=True, separators=(",", ":")).encode("utf-8")


def config_sha256(config: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_config_bytes(config)).hexdigest()


def verify_frozen_config(config: dict[str, Any]) -> None:
    status = config.get("status", {})
    if not status.get("rules_frozen_for_2025", False):
        raise RuntimeError("Rules are not frozen for the 2025 holdout.")
    expected = status.get("frozen_config_sha256")
    actual = config_sha256(config)
    if not expected or expected != actual:
        raise RuntimeError(
            "Frozen configuration fingerprint mismatch. "
            "Do not run the final holdout with edited rules."
        )
