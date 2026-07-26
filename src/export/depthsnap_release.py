from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from src.export.depthsnap_exporter import (
    ACTIVE_EXPORT_DIRECTORY,
    CURRENT_ROLE_OUTPUT_DIRECTORY,
    DepthSnapExportError,
    build_and_promote,
    current_published_registry_spec,
    registry_spec_from_status,
    validate_registry,
)


SUPPORTED_OPERATIONAL_STATES = {
    "PUBLISHED",
    "PRESEASON",
    "WAITING_FOR_COMPLETED_WEEK",
    "BLOCKED",
    "VALIDATED_NOT_PUBLISHED",
}


def _read_status(path: Path) -> Mapping[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise DepthSnapExportError("Supplied operational status could not be read") from exc
    if not isinstance(payload, dict):
        raise DepthSnapExportError("Supplied operational status must be an object")
    return payload


def _valid_prior_for_season(active: Path, season: int) -> Mapping[str, Any] | None:
    if not Path(active).is_dir():
        return None
    try:
        result = validate_registry(active)
    except DepthSnapExportError:
        return None
    return result if int(result["season"]) == season else None


def apply_current_publication(
    status_path: Path,
    *,
    active: Path = ACTIVE_EXPORT_DIRECTORY,
    output_dir: Path = CURRENT_ROLE_OUTPUT_DIRECTORY,
    generated_at: str | None = None,
) -> Mapping[str, Any]:
    status_path = Path(status_path)
    active = Path(active)
    payload = _read_status(status_path)
    state = str(payload.get("status") or "")
    if state not in SUPPORTED_OPERATIONAL_STATES:
        raise DepthSnapExportError(f"Unsupported operational state: {state or '<empty>'}")
    season = int(payload.get("season") or 0)
    if season < 2026:
        raise DepthSnapExportError("Current publication orchestration requires season 2026 or later")

    prior = _valid_prior_for_season(active, season)
    if state == "VALIDATED_NOT_PUBLISHED":
        return {
            "action": "not_promoted",
            "operationalState": state,
            "priorRegistryRetained": prior is not None,
            "season": season,
        }
    if state == "BLOCKED" and prior is not None:
        return {
            "action": "retained_prior",
            "operationalState": state,
            "priorRegistryRetained": True,
            "publicationStatus": prior["publicationStatus"],
            "season": season,
            "sourceVersion": prior["sourceVersion"],
            "throughWeek": prior["throughWeek"],
        }

    if state == "PUBLISHED":
        spec = current_published_registry_spec(
            status_path,
            output_dir=output_dir,
            generated_at=generated_at,
        )
        action = "promoted_published"
    else:
        spec = registry_spec_from_status(
            status_path,
            generated_at=generated_at,
        )
        action = (
            "promoted_unavailable"
            if state == "BLOCKED"
            else "promoted_no_published_week"
        )

    result = build_and_promote(spec, active=active, keep_rollback=True)
    return {
        "action": action,
        "operationalState": state,
        "priorRegistryRetained": False,
        **result,
    }
