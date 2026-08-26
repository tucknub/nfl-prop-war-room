from __future__ import annotations

from typing import Any, Mapping

from .persistence import LeagueSeasonIdentity, canonical_json
from .persistence_protocol import (
    FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    JAVASCRIPT_MAX_SAFE_INTEGER,
    UnsafePersistenceCommand,
)


LEAGUE_SEASON_UPSERT = "LEAGUE_SEASON_UPSERT"


def build_league_season_upsert_command(
    identity: LeagueSeasonIdentity,
    *,
    league_family_id: str,
    family_display_name: str,
    season_display_name: str,
    created_at_ms: int,
    family_metadata: Mapping[str, Any] | None = None,
    season_metadata: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Build protocol-v1 league registration without exposing SQL.

    The Worker owns the fixed registration SQL and enforces immutable league-season
    identity. Python exports only the already-normalized identity plus labels,
    creation time, and deterministic JSON metadata.
    """

    created_at_ms = _javascript_safe_nonnegative_int(created_at_ms, "created_at_ms")
    return {
        "protocol_version": FANTASY_PERSISTENCE_PROTOCOL_VERSION,
        "kind": LEAGUE_SEASON_UPSERT,
        "identity": {
            "league_season_id": identity.league_season_id,
            "platform": identity.platform,
            "platform_league_id": identity.platform_league_id,
            "season": identity.season,
        },
        "league_family_id": _required_text(league_family_id, "league_family_id"),
        "family_display_name": _required_text(
            family_display_name,
            "family_display_name",
        ),
        "season_display_name": _required_text(
            season_display_name,
            "season_display_name",
        ),
        "created_at_ms": created_at_ms,
        "family_metadata_json": _canonical_object_json(
            family_metadata,
            "family_metadata",
        ),
        "season_metadata_json": _canonical_object_json(
            season_metadata,
            "season_metadata",
        ),
    }


def _required_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise UnsafePersistenceCommand(f"{label} must be a string")
    result = value.strip()
    if not result:
        raise UnsafePersistenceCommand(f"{label} is required")
    return result


def _canonical_object_json(
    value: Mapping[str, Any] | None,
    label: str,
) -> str:
    if value is None:
        return "{}"
    if not isinstance(value, Mapping):
        raise UnsafePersistenceCommand(f"{label} must be a mapping")
    try:
        return canonical_json(dict(value))
    except ValueError as exc:
        raise UnsafePersistenceCommand(f"{label} is not valid JSON: {exc}") from exc


def _javascript_safe_nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise UnsafePersistenceCommand(
            f"{label} must be a non-negative JavaScript safe integer"
        )
    if isinstance(value, float) and not value.is_integer():
        raise UnsafePersistenceCommand(
            f"{label} must be a non-negative JavaScript safe integer"
        )
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise UnsafePersistenceCommand(
            f"{label} must be a non-negative JavaScript safe integer"
        ) from None
    if result < 0 or result > JAVASCRIPT_MAX_SAFE_INTEGER:
        raise UnsafePersistenceCommand(
            f"{label} must be a non-negative JavaScript safe integer"
        )
    return result
