from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence

from .changes import FantasyChangeEvent, FantasySnapshot
from .models import DraftState, FantasyLeagueState, LeagueRules, LeagueTransaction, Manager, Roster


@dataclass(frozen=True)
class LeagueSeasonIdentity:
    """Existing persistence identity for one accepted fantasy league season."""

    league_season_id: str
    platform: str
    platform_league_id: str
    season: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "league_season_id", _required_text(self.league_season_id, "league_season_id"))
        object.__setattr__(self, "platform", _required_text(self.platform, "platform"))
        object.__setattr__(self, "platform_league_id", _required_text(self.platform_league_id, "platform_league_id"))
        object.__setattr__(self, "season", _required_text(self.season, "season"))


@dataclass(frozen=True)
class PersistenceStatement:
    """One SQLite/D1-compatible statement with positional bind parameters."""

    sql: str
    parameters: tuple[Any, ...]
    expected_affected_rows: int | None = 1

    def __post_init__(self) -> None:
        if not str(self.sql or "").strip():
            raise ValueError("persistence statement SQL is required")
        if self.expected_affected_rows is not None and self.expected_affected_rows < 0:
            raise ValueError("expected_affected_rows cannot be negative")


@dataclass(frozen=True)
class SuccessfulSyncWritePlan:
    """Atomic post-provider write set: accepted snapshot, events, then sync completion."""

    sync_run_id: str
    snapshot_id: str
    statements: tuple[PersistenceStatement, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sync_run_id", _required_text(self.sync_run_id, "sync_run_id"))
        object.__setattr__(self, "snapshot_id", _required_text(self.snapshot_id, "snapshot_id"))
        if len(self.statements) < 2:
            raise ValueError("successful sync write plan requires snapshot and completion statements")


class UnsafePersistencePlan(ValueError):
    """Raised when domain state cannot safely be serialized into the persistence schema."""


def canonical_json(value: Any) -> str:
    """Serialize persistence JSON deterministically and reject non-JSON values."""

    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not valid persistence JSON: {exc}") from exc


def serialize_fantasy_league_state(state: FantasyLeagueState) -> Mapping[str, Any]:
    """Return normalized league facts only; raw provider payloads stay outside accepted state JSON."""

    return {
        "platform": state.platform,
        "platform_league_id": state.platform_league_id,
        "name": state.name,
        "season": state.season,
        "status": state.status,
        "team_count": state.team_count,
        "previous_platform_league_id": state.previous_platform_league_id,
        "current_platform_user_id": state.current_platform_user_id,
        "my_platform_roster_id": state.my_platform_roster_id,
        "rules": _serialize_rules(state.rules),
        "draft": _serialize_draft(state.draft),
        "managers": [_serialize_manager(row) for row in state.managers],
        "rosters": [_serialize_roster(row) for row in state.rosters],
        "readiness": {
            "rules_ready": bool(state.rules_ready),
            "draft_ready": bool(state.draft_ready),
            "ownership_ready": bool(state.ownership_ready),
        },
    }


def serialize_fantasy_snapshot(snapshot: FantasySnapshot) -> Mapping[str, Any]:
    """Serialize the exact normalized content represented by a snapshot fingerprint."""

    return {
        "league": serialize_fantasy_league_state(snapshot.league),
        "transactions": [_serialize_transaction(row) for row in snapshot.transactions],
    }


def build_sync_start_statement(
    identity: LeagueSeasonIdentity,
    *,
    sync_run_id: str,
    started_at_ms: int,
    request_metadata: Mapping[str, Any] | None = None,
) -> PersistenceStatement:
    """Create the pre-provider write that records a sync attempt."""

    sync_run_id = _required_text(sync_run_id, "sync_run_id")
    started_at_ms = _nonnegative_int(started_at_ms, "started_at_ms")
    return PersistenceStatement(
        sql=(
            "INSERT INTO fantasy_sync_runs ("
            "sync_run_id, league_season_id, platform, platform_league_id, season, "
            "started_at_ms, completed_at_ms, status, accepted_snapshot_id, error_code, "
            "error_summary, request_metadata_json"
            ") VALUES (?, ?, ?, ?, ?, ?, NULL, ?, NULL, NULL, NULL, ?)"
        ),
        parameters=(
            sync_run_id,
            identity.league_season_id,
            identity.platform,
            identity.platform_league_id,
            identity.season,
            started_at_ms,
            "STARTED",
            canonical_json(dict(request_metadata or {})),
        ),
    )


def build_failed_sync_statement(
    identity: LeagueSeasonIdentity,
    *,
    sync_run_id: str,
    completed_at_ms: int,
    error_code: str,
    error_summary: str,
) -> PersistenceStatement:
    """Finish a previously started sync without creating an accepted snapshot."""

    sync_run_id = _required_text(sync_run_id, "sync_run_id")
    completed_at_ms = _nonnegative_int(completed_at_ms, "completed_at_ms")
    error_code = _required_text(error_code, "error_code")
    error_summary = _required_text(error_summary, "error_summary")
    return PersistenceStatement(
        sql=(
            "UPDATE fantasy_sync_runs SET completed_at_ms = ?, status = ?, error_code = ?, "
            "error_summary = ?, accepted_snapshot_id = NULL "
            "WHERE sync_run_id = ? AND league_season_id = ? AND platform = ? "
            "AND platform_league_id = ? AND season = ? AND status = ?"
        ),
        parameters=(
            completed_at_ms,
            "FAILED",
            error_code,
            error_summary,
            sync_run_id,
            identity.league_season_id,
            identity.platform,
            identity.platform_league_id,
            identity.season,
            "STARTED",
        ),
    )


def build_successful_sync_write_plan(
    identity: LeagueSeasonIdentity,
    *,
    sync_run_id: str,
    snapshot: FantasySnapshot,
    events: Sequence[FantasyChangeEvent],
    observed_at_ms: int,
    accepted_at_ms: int,
    completed_at_ms: int,
    derived_at_ms: int,
    source_metadata: Mapping[str, Any] | None = None,
) -> SuccessfulSyncWritePlan:
    """Build the statements that must execute atomically after provider normalization succeeds."""

    sync_run_id = _required_text(sync_run_id, "sync_run_id")
    observed_at_ms = _nonnegative_int(observed_at_ms, "observed_at_ms")
    accepted_at_ms = _nonnegative_int(accepted_at_ms, "accepted_at_ms")
    completed_at_ms = _nonnegative_int(completed_at_ms, "completed_at_ms")
    derived_at_ms = _nonnegative_int(derived_at_ms, "derived_at_ms")
    if accepted_at_ms < observed_at_ms:
        raise UnsafePersistencePlan("accepted_at_ms cannot precede observed_at_ms")

    _validate_identity_matches_state(identity, snapshot.league)
    _validate_events(identity, snapshot, events)

    snapshot_statement = PersistenceStatement(
        sql=(
            "INSERT INTO fantasy_state_snapshots ("
            "snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, "
            "provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, "
            "source_metadata_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        parameters=(
            snapshot.snapshot_id,
            identity.league_season_id,
            snapshot.fingerprint,
            observed_at_ms,
            accepted_at_ms,
            snapshot.league.status,
            int(bool(snapshot.league.rules_ready)),
            int(bool(snapshot.league.draft_ready)),
            int(bool(snapshot.league.ownership_ready)),
            canonical_json(serialize_fantasy_snapshot(snapshot)),
            canonical_json(dict(source_metadata or {})),
        ),
    )

    event_statements = tuple(
        _build_event_statement(identity, event, derived_at_ms=derived_at_ms)
        for event in events
    )

    completion = PersistenceStatement(
        sql=(
            "UPDATE fantasy_sync_runs SET completed_at_ms = ?, status = ?, accepted_snapshot_id = ?, "
            "error_code = NULL, error_summary = NULL "
            "WHERE sync_run_id = ? AND league_season_id = ? AND platform = ? "
            "AND platform_league_id = ? AND season = ? AND status = ?"
        ),
        parameters=(
            completed_at_ms,
            "COMPLETED",
            snapshot.snapshot_id,
            sync_run_id,
            identity.league_season_id,
            identity.platform,
            identity.platform_league_id,
            identity.season,
            "STARTED",
        ),
    )

    return SuccessfulSyncWritePlan(
        sync_run_id=sync_run_id,
        snapshot_id=snapshot.snapshot_id,
        statements=(snapshot_statement, *event_statements, completion),
    )


def _build_event_statement(
    identity: LeagueSeasonIdentity,
    event: FantasyChangeEvent,
    *,
    derived_at_ms: int,
) -> PersistenceStatement:
    return PersistenceStatement(
        sql=(
            "INSERT INTO fantasy_change_events ("
            "event_fingerprint, league_season_id, event_type, platform, platform_league_id, season, "
            "before_snapshot_id, after_snapshot_id, platform_roster_id, platform_player_id, "
            "before_value_json, after_value_json, source_transaction_ids_json, reason_codes_json, "
            "derived_at_ms"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        parameters=(
            event.event_fingerprint,
            identity.league_season_id,
            event.event_type,
            event.platform,
            event.platform_league_id,
            event.season,
            event.before_snapshot_id,
            event.after_snapshot_id,
            event.platform_roster_id,
            event.platform_player_id,
            None if event.before_value is None else canonical_json(event.before_value),
            None if event.after_value is None else canonical_json(event.after_value),
            canonical_json(list(event.source_transaction_ids)),
            canonical_json(list(event.reason_codes)),
            derived_at_ms,
        ),
    )


def _validate_identity_matches_state(identity: LeagueSeasonIdentity, state: FantasyLeagueState) -> None:
    expected = (identity.platform, identity.platform_league_id, identity.season)
    actual = (state.platform, state.platform_league_id, state.season)
    if expected != actual:
        raise UnsafePersistencePlan(
            f"league-season persistence identity {expected} does not match snapshot state {actual}"
        )


def _validate_events(
    identity: LeagueSeasonIdentity,
    snapshot: FantasySnapshot,
    events: Sequence[FantasyChangeEvent],
) -> None:
    seen: set[str] = set()
    expected = (identity.platform, identity.platform_league_id, identity.season)
    for event in events:
        actual = (event.platform, event.platform_league_id, event.season)
        if actual != expected:
            raise UnsafePersistencePlan(
                f"change event league identity {actual} does not match write plan {expected}"
            )
        if event.after_snapshot_id != snapshot.snapshot_id:
            raise UnsafePersistencePlan(
                "change event after_snapshot_id must equal the accepted snapshot_id"
            )
        if event.before_snapshot_id == event.after_snapshot_id:
            raise UnsafePersistencePlan("change event cannot reference one snapshot as both before and after")
        if event.event_fingerprint in seen:
            raise UnsafePersistencePlan("successful write plan contains duplicate event fingerprints")
        seen.add(event.event_fingerprint)


def _serialize_rules(rules: LeagueRules) -> Mapping[str, Any]:
    return {
        "roster_positions": list(rules.roster_positions),
        "scoring_settings": dict(rules.scoring_settings),
        "waiver_budget": rules.waiver_budget,
        "max_keepers": rules.max_keepers,
        "playoff_teams": rules.playoff_teams,
        "playoff_week_start": rules.playoff_week_start,
        "trade_deadline": rules.trade_deadline,
        "reserve_slots": rules.reserve_slots,
        "taxi_slots": rules.taxi_slots,
        "position_limits": dict(rules.position_limits),
        "rule_settings": dict(rules.rule_settings),
        "rules_fingerprint": rules.rules_fingerprint,
    }


def _serialize_draft(draft: DraftState | None) -> Mapping[str, Any] | None:
    if draft is None:
        return None
    return {
        "platform_draft_id": draft.platform_draft_id,
        "status": draft.status,
        "draft_type": draft.draft_type,
        "rounds": draft.rounds,
        "teams": draft.teams,
        "start_time_ms": draft.start_time_ms,
        "draft_order": dict(draft.draft_order),
        "slot_counts": dict(draft.slot_counts),
        "position_limits": dict(draft.position_limits),
        "enforce_position_limits": bool(draft.enforce_position_limits),
    }


def _serialize_manager(manager: Manager) -> Mapping[str, Any]:
    return {
        "platform_user_id": manager.platform_user_id,
        "display_name": manager.display_name,
        "team_name": manager.team_name,
        "is_owner": bool(manager.is_owner),
    }


def _serialize_roster(roster: Roster) -> Mapping[str, Any]:
    return {
        "platform_roster_id": roster.platform_roster_id,
        "platform_user_id": roster.platform_user_id,
        "players": list(roster.players),
        "starters": list(roster.starters),
        "reserve": list(roster.reserve),
        "taxi": list(roster.taxi),
        "settings": dict(roster.settings),
    }


def _serialize_transaction(transaction: LeagueTransaction) -> Mapping[str, Any]:
    return {
        "platform_transaction_id": transaction.platform_transaction_id,
        "transaction_type": transaction.transaction_type,
        "status": transaction.status,
        "week": transaction.week,
        "roster_ids": list(transaction.roster_ids),
        "creator_user_id": transaction.creator_user_id,
        "created_at_ms": transaction.created_at_ms,
        "status_updated_at_ms": transaction.status_updated_at_ms,
        "consenter_roster_ids": list(transaction.consenter_roster_ids),
        "adds": dict(transaction.adds),
        "drops": dict(transaction.drops),
        "traded_picks": [
            {
                "season": row.season,
                "round": row.round,
                "original_roster_id": row.original_roster_id,
                "previous_owner_roster_id": row.previous_owner_roster_id,
                "owner_roster_id": row.owner_roster_id,
            }
            for row in transaction.traded_picks
        ],
        "faab_transfers": [
            {
                "sender_roster_id": row.sender_roster_id,
                "receiver_roster_id": row.receiver_roster_id,
                "amount": row.amount,
            }
            for row in transaction.faab_transfers
        ],
        "waiver_bid": transaction.waiver_bid,
        "metadata": dict(transaction.metadata),
    }


def _required_text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a non-negative integer")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{label} must be a non-negative integer")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a non-negative integer") from None
    if result < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return result
