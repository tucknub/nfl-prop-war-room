from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence

from .changes import FantasyChangeEvent, FantasySnapshot
from .models import FantasyLeagueState


@dataclass(frozen=True)
class LeagueSeasonIdentity:
    """Existing persistence identity for one accepted fantasy league season."""

    league_season_id: str
    platform: str
    platform_league_id: str
    season: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "league_season_id",
            _required_text(self.league_season_id, "league_season_id"),
        )
        object.__setattr__(self, "platform", _required_text(self.platform, "platform"))
        object.__setattr__(
            self,
            "platform_league_id",
            _required_text(self.platform_league_id, "platform_league_id"),
        )
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
        object.__setattr__(
            self,
            "sync_run_id",
            _required_text(self.sync_run_id, "sync_run_id"),
        )
        object.__setattr__(
            self,
            "snapshot_id",
            _required_text(self.snapshot_id, "snapshot_id"),
        )
        if len(self.statements) < 2:
            raise ValueError(
                "successful sync write plan requires snapshot and completion statements"
            )


class UnsafePersistencePlan(ValueError):
    """Raised when domain state cannot safely be serialized into the persistence schema."""


def canonical_json(value: Any) -> str:
    """Serialize persistence JSON deterministically and reject non-JSON values."""

    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"value is not valid persistence JSON: {exc}") from exc


def serialize_fantasy_league_state(state: FantasyLeagueState) -> Mapping[str, Any]:
    """Serialize normalized domain facts while deliberately excluding raw provider blobs."""

    payload = _strip_provider_raw(asdict(state))
    payload["rules"]["rules_fingerprint"] = state.rules_fingerprint
    return payload


def serialize_fantasy_snapshot(snapshot: FantasySnapshot) -> Mapping[str, Any]:
    """Serialize the exact normalized snapshot content persisted to storage."""

    return {
        "league": serialize_fantasy_league_state(snapshot.league),
        "transactions": [
            _strip_provider_raw(asdict(row)) for row in snapshot.transactions
        ],
    }


def persistence_content_fingerprint(snapshot: FantasySnapshot) -> str:
    """Hash the exact canonical normalized JSON that persistence writes.

    `FantasySnapshot.fingerprint` intentionally serves change detection and hashes a
    smaller decision-relevant payload. The persistence fingerprint is separate so
    `fantasy_state_snapshots.content_fingerprint` always describes the complete
    normalized JSON stored in that row.
    """

    encoded = canonical_json(serialize_fantasy_snapshot(snapshot))
    return sha256(encoded.encode("utf-8")).hexdigest()


def build_sync_start_statement(
    identity: LeagueSeasonIdentity,
    *,
    sync_run_id: str,
    started_at_ms: int,
    request_metadata: Mapping[str, Any] | None = None,
) -> PersistenceStatement:
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
    sync_run_id = _required_text(sync_run_id, "sync_run_id")
    completed_at_ms = _nonnegative_int(completed_at_ms, "completed_at_ms")
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
            _required_text(error_code, "error_code"),
            _required_text(error_summary, "error_summary"),
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
    provider_status: str,
    source_metadata: Mapping[str, Any] | None = None,
) -> SuccessfulSyncWritePlan:
    """Build statements intended for one D1/SQLite transactional batch.

    The snapshot INSERT resolves its non-null league-season ID from the exact
    matching STARTED sync row. A missing, mismatched, or already-finished sync
    therefore produces a NOT NULL SQL error instead of a harmless zero-row write.
    D1 batch execution can then roll back the entire sequence at the database
    boundary rather than depending on a post-commit affected-row check.
    """

    sync_run_id = _required_text(sync_run_id, "sync_run_id")
    provider_status = _required_text(provider_status, "provider_status")
    observed_at_ms = _nonnegative_int(observed_at_ms, "observed_at_ms")
    accepted_at_ms = _nonnegative_int(accepted_at_ms, "accepted_at_ms")
    completed_at_ms = _nonnegative_int(completed_at_ms, "completed_at_ms")
    derived_at_ms = _nonnegative_int(derived_at_ms, "derived_at_ms")

    if accepted_at_ms < observed_at_ms:
        raise UnsafePersistencePlan("accepted_at_ms cannot precede observed_at_ms")
    if derived_at_ms < observed_at_ms:
        raise UnsafePersistencePlan("derived_at_ms cannot precede observed_at_ms")
    if completed_at_ms < accepted_at_ms:
        raise UnsafePersistencePlan("completed_at_ms cannot precede accepted_at_ms")
    if completed_at_ms < derived_at_ms:
        raise UnsafePersistencePlan("completed_at_ms cannot precede derived_at_ms")

    _validate_identity_matches_state(identity, snapshot.league)
    _validate_events(identity, snapshot, events)

    normalized_state_json = canonical_json(serialize_fantasy_snapshot(snapshot))
    content_fingerprint = persistence_content_fingerprint(snapshot)

    snapshot_statement = PersistenceStatement(
        sql=(
            "INSERT INTO fantasy_state_snapshots ("
            "snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, "
            "provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, "
            "source_metadata_json"
            ") VALUES (?, (SELECT league_season_id FROM fantasy_sync_runs "
            "WHERE sync_run_id = ? AND league_season_id = ? AND platform = ? "
            "AND platform_league_id = ? AND season = ? AND status = 'STARTED'), "
            "?, ?, ?, ?, ?, ?, ?, ?, ?)"
        ),
        parameters=(
            snapshot.snapshot_id,
            sync_run_id,
            identity.league_season_id,
            identity.platform,
            identity.platform_league_id,
            identity.season,
            content_fingerprint,
            observed_at_ms,
            accepted_at_ms,
            provider_status,
            int(bool(snapshot.league.rules_ready)),
            int(bool(snapshot.league.draft_ready)),
            int(bool(snapshot.league.ownership_ready)),
            normalized_state_json,
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



def build_unchanged_sync_statement(
    identity: LeagueSeasonIdentity,
    *,
    sync_run_id: str,
    completed_at_ms: int,
    accepted_snapshot_id: str,
    content_fingerprint: str,
) -> PersistenceStatement:
    """Complete one STARTED sync by reusing the current latest accepted snapshot.

    This path deliberately inserts no snapshot and no change events. The UPDATE
    succeeds only when the referenced snapshot belongs to the same league season,
    matches the supplied content fingerprint, and is still the league's latest
    snapshot accepted by a COMPLETED sync. A stale comparison therefore affects
    zero rows and is rejected by the D1 affected-row invariant.
    """

    sync_run_id = _required_text(sync_run_id, "sync_run_id")
    completed_at_ms = _nonnegative_int(completed_at_ms, "completed_at_ms")
    accepted_snapshot_id = _required_text(
        accepted_snapshot_id,
        "accepted_snapshot_id",
    )
    content_fingerprint = _sha256_fingerprint(
        content_fingerprint,
        "content_fingerprint",
    )

    return PersistenceStatement(
        sql=(
            "UPDATE fantasy_sync_runs SET completed_at_ms = ?, status = ?, "
            "accepted_snapshot_id = ?, error_code = NULL, error_summary = NULL "
            "WHERE sync_run_id = ? AND league_season_id = ? AND platform = ? "
            "AND platform_league_id = ? AND season = ? AND status = ? "
            "AND ? = ("
            "SELECT s.snapshot_id FROM fantasy_state_snapshots AS s "
            "WHERE s.league_season_id = ? AND s.snapshot_id = ? "
            "AND s.content_fingerprint = ? "
            "AND EXISTS ("
            "SELECT 1 FROM fantasy_sync_runs AS accepted "
            "WHERE accepted.league_season_id = s.league_season_id "
            "AND accepted.accepted_snapshot_id = s.snapshot_id "
            "AND accepted.status = 'COMPLETED'"
            ") "
            "ORDER BY s.accepted_at_ms DESC, s.snapshot_id DESC LIMIT 1"
            ") "
            "AND ? = ("
            "SELECT latest.snapshot_id FROM fantasy_state_snapshots AS latest "
            "WHERE latest.league_season_id = ? "
            "AND EXISTS ("
            "SELECT 1 FROM fantasy_sync_runs AS accepted_latest "
            "WHERE accepted_latest.league_season_id = latest.league_season_id "
            "AND accepted_latest.accepted_snapshot_id = latest.snapshot_id "
            "AND accepted_latest.status = 'COMPLETED'"
            ") "
            "ORDER BY latest.accepted_at_ms DESC, latest.snapshot_id DESC LIMIT 1"
            ")"
        ),
        parameters=(
            completed_at_ms,
            "COMPLETED",
            accepted_snapshot_id,
            sync_run_id,
            identity.league_season_id,
            identity.platform,
            identity.platform_league_id,
            identity.season,
            "STARTED",
            accepted_snapshot_id,
            identity.league_season_id,
            accepted_snapshot_id,
            content_fingerprint,
            accepted_snapshot_id,
            identity.league_season_id,
        ),
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
            None
            if event.before_value is None
            else canonical_json(event.before_value),
            None
            if event.after_value is None
            else canonical_json(event.after_value),
            canonical_json(list(event.source_transaction_ids)),
            canonical_json(list(event.reason_codes)),
            derived_at_ms,
        ),
    )


def _validate_identity_matches_state(
    identity: LeagueSeasonIdentity,
    state: FantasyLeagueState,
) -> None:
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
            raise UnsafePersistencePlan(
                "change event cannot reference one snapshot as both before and after"
            )
        if event.event_fingerprint in seen:
            raise UnsafePersistencePlan(
                "successful write plan contains duplicate event fingerprints"
            )
        seen.add(event.event_fingerprint)


def _strip_provider_raw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _strip_provider_raw(item)
            for key, item in value.items()
            if str(key) not in {"raw", "raw_settings"}
        }
    if isinstance(value, tuple):
        return [_strip_provider_raw(item) for item in value]
    if isinstance(value, list):
        return [_strip_provider_raw(item) for item in value]
    return value


def _required_text(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result



def _sha256_fingerprint(value: Any, label: str) -> str:
    result = _required_text(value, label)
    if len(result) != 64 or any(char not in "0123456789abcdef" for char in result):
        raise ValueError(
            f"{label} must be a lowercase 64-character SHA-256 hex fingerprint"
        )
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
