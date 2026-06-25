from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.yaml"


def load_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def project_path(*parts: str) -> Path:
    return ROOT.joinpath(*parts)


def ensure_dirs(config: dict[str, Any] | None = None) -> None:
    cfg = config or load_config()
    for key in ("raw_dir", "processed_dir", "output_dir"):
        project_path(cfg["paths"][key]).mkdir(parents=True, exist_ok=True)


def output_path(filename: str, config: dict[str, Any] | None = None) -> Path:
    cfg = config or load_config()
    ensure_dirs(cfg)
    path = project_path(cfg["paths"]["output_dir"], filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def raw_path(filename: str, config: dict[str, Any] | None = None) -> Path:
    cfg = config or load_config()
    ensure_dirs(cfg)
    return project_path(cfg["paths"]["raw_dir"], filename)
