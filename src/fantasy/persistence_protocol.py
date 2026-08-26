from __future__ import annotations

from typing import Any, Mapping, Sequence

from .changes import FantasyChangeEvent, FantasySnapshot
from .persistence import (
    LeagueSeasonIdentity,
    build_failed_sync_statement,
    build_successful_sync_write_plan,
    build_unchanged_sync_statement,
    build_sync_start_statement,
    canonical_json,
    persistence_content_fingerprint,
    serialize_fantasy_snapshot,
)


FANTASY_PERSISTENCE_PROTOCOL_VERSION = 1
SYNC_START = "SYNC_START"
SYNC_FAILED = "SYNC_FAILED"
SYNC_SUCCESS = "SYNC_SUCCESS"
SYNC_UNCHANGED = "SYNC_UNCHANGED"
JAVASCRIPT_MAX_SAFE_INTEGER = 9_007_199_254_740_991


class UnsafePersistenceCommand(ValueError):
    """Raised when a validated Python persistence object cannot cross the Worker protocol safely."""


def build_sync_start_command(
    identity: LeagueSeasonIdentity,
    *,
    sync_run_id: str,
    started_at_ms: int,
    request_metadata: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Build protocol-v1 SYNC_START without exposing SQL to the Worker route."""

    statement = build_sync_start_statement(
        identity,
        sync_run_id=sync_run_id,
        started_at_ms=started_at_ms,
        request_metadata=request_metadata,
    )
    normalized_started_at_ms = _javascript_safe_nonnegative_int(
        statement.parameters[5],
        "started_at_ms",
    )
    return {
        "protocol_version": FANTASY_PERSISTENCE_PROTOCOL_VERSION,
        "kind": SYNC_START,
        "identity": _identity_payload(identity),
        "sync_run_id": statement.parameters[0],
        "started_at_ms": normalized_started_at_ms,
        "request_metadata_json": statement.parameters[7],
    }


def build_failed_sync_command(
    identity: LeagueSeasonIdentity,
    *,
    sync_run_id: str,
    completed_at_ms: int,
    error_code: str,
    error_summary: str,
) -> Mapping[str, Any]:
    """Build protocol-v1 SYNC_FAILED from the same validated fields as the SQL writer."""

    statement = build_failed_sync_statement(
        identity,
        sync_run_id=sync_run_id,
        completed_at_ms=completed_at_ms,
        error_code=error_code,
        error_summary=error_summary,
    )
    normalized_completed_at_ms = _javascript_safe_nonnegative_int(
        statement.parameters[0],
        "completed_at_ms",
    )
    return {
        "protocol_version": FANTASY_PERSISTENCE_PROTOCOL_VERSION,
        "kind": SYNC_FAILED,
        "identity": _identity_payload(identity),
        "sync_run_id": statement.parameters[4],
        "completed_at_ms": normalized_completed_at_ms,
        "error_code": statement.parameters[2],
        "error_summary": statement.parameters[3],
    }


def build_successful_sync_command(
    identity: LeagueSeasonIdentity,
    *,
    sync_run_id: str,
    snapshot: FantasySnapshot,
    events: Sequence[FantasyChangeEvent],
    observed_at_ms: int,
    accepted_at_ms: int,
    completed_at_ms: int,
    derived_at_ms: int,
    provider_status: str,
    source_metadata: Mapping[str, Any] | None = None,
) -> Mapping[str, Any]:
    """Build protocol-v1 SYNC_SUCCESS from already validated Fantasy HQ domain state.

    The existing successful write-plan builder remains the Python-side source of
    truth for league identity, event binding, duplicate fingerprints, provider
    status, and timestamp ordering. This exporter adds only transport constraints
    that matter before JSON crosses into JavaScript/Cloudflare Workers.
    """

    observed_at_ms = _javascript_safe_nonnegative_int(observed_at_ms, "observed_at_ms")
    accepted_at_ms = _javascript_safe_nonnegative_int(accepted_at_ms, "accepted_at_ms")
    completed_at_ms = _javascript_safe_nonnegative_int(completed_at_ms, "completed_at_ms")
    derived_at_ms = _javascript_safe_nonnegative_int(derived_at_ms, "derived_at_ms")

    plan = build_successful_sync_write_plan(
        identity,
        sync_run_id=sync_run_id,
        snapshot=snapshot,
        events=events,
        observed_at_ms=observed_at_ms,
        accepted_at_ms=accepted_at_ms,
        completed_at_ms=completed_at_ms,
        derived_at_ms=derived_at_ms,
        provider_status=provider_status,
        source_metadata=source_metadata,
    )

    normalized_state_json = canonical_json(serialize_fantasy_snapshot(snapshot))
    event_payloads = tuple(
        _event_payload(event, derived_at_ms=derived_at_ms)
        for event in events
    )

    return {
        "protocol_version": FANTASY_PERSISTENCE_PROTOCOL_VERSION,
        "kind": SYNC_SUCCESS,
        "identity": _identity_payload(identity),
        "sync_run_id": plan.sync_run_id,
        "snapshot": {
            "snapshot_id": plan.snapshot_id,
            "content_fingerprint": persistence_content_fingerprint(snapshot),
            "observed_at_ms": observed_at_ms,
            "accepted_at_ms": accepted_at_ms,
            "provider_status": _required_text(provider_status, "provider_status"),
            "rules_ready": bool(snapshot.league.rules_ready),
            "draft_ready": bool(snapshot.league.draft_ready),
            "ownership_ready": bool(snapshot.league.ownership_ready),
            "normalized_state_json": normalized_state_json,
            "source_metadata_json": canonical_json(dict(source_metadata or {})),
        },
        "events": list(event_payloads),
        "completed_at_ms": completed_at_ms,
    }



def build_unchanged_sync_command(
    identity: LeagueSeasonIdentity,
    *,
    sync_run_id: str,
    completed_at_ms: int,
    accepted_snapshot_id: str,
    content_fingerprint: str,
) -> Mapping[str, Any]:
    """Build protocol-v1 SYNC_UNCHANGED without inserting duplicate state."""

    completed_at_ms = _javascript_safe_nonnegative_int(
        completed_at_ms,
        "completed_at_ms",
    )
    accepted_snapshot_id = _required_text(
        accepted_snapshot_id,
        "accepted_snapshot_id",
    )
    content_fingerprint = _sha256_fingerprint(
        content_fingerprint,
        "content_fingerprint",
    )

    # Keep the Python SQL contract as the source of truth for identity/text/time
    # validation even though the Worker will construct its own fixed statement.
    build_unchanged_sync_statement(
        identity,
        sync_run_id=sync_run_id,
        completed_at_ms=completed_at_ms,
        accepted_snapshot_id=accepted_snapshot_id,
        content_fingerprint=content_fingerprint,
    )

    return {
        "protocol_version": FANTASY_PERSISTENCE_PROTOCOL_VERSION,
        "kind": SYNC_UNCHANGED,
        "identity": _identity_payload(identity),
        "sync_run_id": _required_text(sync_run_id, "sync_run_id"),
        "completed_at_ms": completed_at_ms,
        "accepted_snapshot_id": accepted_snapshot_id,
        "content_fingerprint": content_fingerprint,
    }

def _identity_payload(identity: LeagueSeasonIdentity) -> Mapping[str, str]:
    return {
        "league_season_id": identity.league_season_id,
        "platform": identity.platform,
        "platform_league_id": identity.platform_league_id,
        "season": identity.season,
    }


def _event_payload(
    event: FantasyChangeEvent,
    *,
    derived_at_ms: int,
) -> Mapping[str, Any]:
    return {
        "event_fingerprint": _required_text(
            event.event_fingerprint,
            "event.event_fingerprint",
        ),
        "event_type": _required_text(event.event_type, "event.event_type"),
        "before_snapshot_id": _required_text(
            event.before_snapshot_id,
            "event.before_snapshot_id",
        ),
        "after_snapshot_id": _required_text(
            event.after_snapshot_id,
            "event.after_snapshot_id",
        ),
        "platform_roster_id": _optional_text(
            event.platform_roster_id,
            "event.platform_roster_id",
        ),
        "platform_player_id": _optional_text(
            event.platform_player_id,
            "event.platform_player_id",
        ),
        "before_value_json": (
            None
            if event.before_value is None
            else canonical_json(event.before_value)
        ),
        "after_value_json": (
            None
            if event.after_value is None
            else canonical_json(event.after_value)
        ),
        "source_transaction_ids_json": canonical_json(
            list(_string_values(event.source_transaction_ids, "event.source_transaction_ids"))
        ),
        "reason_codes_json": canonical_json(
            list(_string_values(event.reason_codes, "event.reason_codes"))
        ),
        "derived_at_ms": _javascript_safe_nonnegative_int(
            derived_at_ms,
            "derived_at_ms",
        ),
    }



def _sha256_fingerprint(value: Any, label: str) -> str:
    result = _required_text(value, label)
    if len(result) != 64 or any(char not in "0123456789abcdef" for char in result):
        raise UnsafePersistenceCommand(
            f"{label} must be a lowercase 64-character SHA-256 hex fingerprint"
        )
    return result

def _required_text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise UnsafePersistenceCommand(f"{label} is required")
    return result


def _optional_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, label)


def _string_values(values: Sequence[Any], label: str) -> tuple[str, ...]:
    result: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str):
            raise UnsafePersistenceCommand(f"{label}[{index}] must be a string")
        result.append(value)
    return tuple(result)


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
