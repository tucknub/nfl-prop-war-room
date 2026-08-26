from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .changes import FantasySnapshot
from .models import (
    DraftState,
    FaabTransfer,
    FantasyLeagueState,
    LeagueRules,
    LeagueTransaction,
    Manager,
    Roster,
    TradedPick,
)
from .persistence import persistence_content_fingerprint


class UnsafePersistedFantasySnapshot(ValueError):
    """Raised when persisted normalized state cannot be trusted as domain evidence."""


@dataclass(frozen=True)
class PersistedFantasySnapshot:
    """One accepted D1 snapshot rehydrated into the typed Fantasy domain."""

    snapshot: FantasySnapshot
    league_season_id: str
    content_fingerprint: str
    observed_at_ms: int
    accepted_at_ms: int
    provider_status: str
    source_metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "league_season_id",
            _text(self.league_season_id, "league_season_id"),
        )
        object.__setattr__(
            self,
            "content_fingerprint",
            _text(self.content_fingerprint, "content_fingerprint"),
        )
        object.__setattr__(
            self,
            "provider_status",
            _text(self.provider_status, "provider_status"),
        )
        observed = _nonnegative_int(self.observed_at_ms, "observed_at_ms")
        accepted = _nonnegative_int(self.accepted_at_ms, "accepted_at_ms")
        if accepted < observed:
            raise UnsafePersistedFantasySnapshot(
                "accepted_at_ms cannot precede observed_at_ms"
            )
        object.__setattr__(self, "observed_at_ms", observed)
        object.__setattr__(self, "accepted_at_ms", accepted)
        object.__setattr__(
            self,
            "source_metadata",
            _mapping(self.source_metadata, "source_metadata"),
        )


def rehydrate_latest_snapshot_read(
    payload: Mapping[str, Any],
) -> PersistedFantasySnapshot | None:
    """Rehydrate one validated latest-snapshot read response.

    A missing snapshot is authoritative absence and returns None. A found record is
    independently revalidated here so persisted bytes are never trusted merely
    because the HTTP envelope was well formed.
    """

    body = _mapping(payload, "latest snapshot read")
    found = body.get("found")
    if not isinstance(found, bool):
        raise UnsafePersistedFantasySnapshot("latest snapshot read found must be boolean")
    record = body.get("record")
    if not found:
        if record is not None:
            raise UnsafePersistedFantasySnapshot(
                "missing latest snapshot read must contain record=null"
            )
        return None
    return rehydrate_persisted_snapshot_record(
        _mapping(record, "latest snapshot record")
    )


def rehydrate_persisted_snapshot_record(
    record: Mapping[str, Any],
) -> PersistedFantasySnapshot:
    """Rebuild typed state and verify persisted integrity metadata."""

    row = _exact_mapping(
        record,
        "latest snapshot record",
        {
            "snapshot_id",
            "league_season_id",
            "content_fingerprint",
            "observed_at_ms",
            "accepted_at_ms",
            "provider_status",
            "rules_ready",
            "draft_ready",
            "ownership_ready",
            "normalized_state",
            "source_metadata",
        },
    )
    normalized = _exact_mapping(
        row["normalized_state"],
        "normalized_state",
        {"league", "transactions"},
    )

    league = _rehydrate_league(
        _mapping(normalized["league"], "normalized_state.league")
    )
    transactions = tuple(
        _rehydrate_transaction(value, f"normalized_state.transactions[{index}]")
        for index, value in enumerate(
            _sequence(normalized["transactions"], "normalized_state.transactions")
        )
    )
    snapshot = FantasySnapshot(
        snapshot_id=_text(row["snapshot_id"], "snapshot_id"),
        league=league,
        transactions=transactions,
    )

    for key, actual in (
        ("rules_ready", league.rules_ready),
        ("draft_ready", league.draft_ready),
        ("ownership_ready", league.ownership_ready),
    ):
        persisted = _bool(row[key], key)
        if persisted is not actual:
            raise UnsafePersistedFantasySnapshot(
                f"{key} column disagrees with normalized league state"
            )

    stored_fingerprint = _text(row["content_fingerprint"], "content_fingerprint")
    calculated_fingerprint = persistence_content_fingerprint(snapshot)
    if stored_fingerprint != calculated_fingerprint:
        raise UnsafePersistedFantasySnapshot(
            "stored content_fingerprint does not match normalized snapshot content"
        )

    return PersistedFantasySnapshot(
        snapshot=snapshot,
        league_season_id=_text(row["league_season_id"], "league_season_id"),
        content_fingerprint=stored_fingerprint,
        observed_at_ms=_nonnegative_int(row["observed_at_ms"], "observed_at_ms"),
        accepted_at_ms=_nonnegative_int(row["accepted_at_ms"], "accepted_at_ms"),
        provider_status=_text(row["provider_status"], "provider_status"),
        source_metadata=_mapping(row["source_metadata"], "source_metadata"),
    )


def _rehydrate_league(value: Mapping[str, Any]) -> FantasyLeagueState:
    row = _exact_mapping(
        value,
        "league",
        {
            "platform",
            "platform_league_id",
            "name",
            "season",
            "status",
            "team_count",
            "previous_platform_league_id",
            "current_platform_user_id",
            "my_platform_roster_id",
            "rules",
            "draft",
            "managers",
            "rosters",
            "rules_ready",
            "draft_ready",
            "ownership_ready",
        },
    )
    draft_value = row["draft"]
    return FantasyLeagueState(
        platform=_text(row["platform"], "league.platform"),
        platform_league_id=_text(
            row["platform_league_id"], "league.platform_league_id"
        ),
        name=_text(row["name"], "league.name"),
        season=_text(row["season"], "league.season"),
        status=_text(row["status"], "league.status"),
        team_count=_nonnegative_int(row["team_count"], "league.team_count"),
        previous_platform_league_id=_optional_text(
            row["previous_platform_league_id"],
            "league.previous_platform_league_id",
        ),
        current_platform_user_id=_optional_text(
            row["current_platform_user_id"], "league.current_platform_user_id"
        ),
        my_platform_roster_id=_optional_text(
            row["my_platform_roster_id"], "league.my_platform_roster_id"
        ),
        rules=_rehydrate_rules(_mapping(row["rules"], "league.rules")),
        draft=(
            None
            if draft_value is None
            else _rehydrate_draft(_mapping(draft_value, "league.draft"))
        ),
        managers=tuple(
            _rehydrate_manager(item, f"league.managers[{index}]")
            for index, item in enumerate(_sequence(row["managers"], "league.managers"))
        ),
        rosters=tuple(
            _rehydrate_roster(item, f"league.rosters[{index}]")
            for index, item in enumerate(_sequence(row["rosters"], "league.rosters"))
        ),
        rules_ready=_bool(row["rules_ready"], "league.rules_ready"),
        draft_ready=_bool(row["draft_ready"], "league.draft_ready"),
        ownership_ready=_bool(row["ownership_ready"], "league.ownership_ready"),
    )


def _rehydrate_rules(value: Mapping[str, Any]) -> LeagueRules:
    row = _exact_mapping(
        value,
        "league.rules",
        {
            "roster_positions",
            "scoring_settings",
            "waiver_budget",
            "max_keepers",
            "playoff_teams",
            "playoff_week_start",
            "trade_deadline",
            "reserve_slots",
            "taxi_slots",
            "position_limits",
            "rule_settings",
            "rules_fingerprint",
        },
    )
    rules = LeagueRules(
        roster_positions=_string_tuple(
            row["roster_positions"], "league.rules.roster_positions"
        ),
        scoring_settings=_mapping(
            row["scoring_settings"], "league.rules.scoring_settings"
        ),
        waiver_budget=_optional_int(
            row["waiver_budget"], "league.rules.waiver_budget"
        ),
        max_keepers=_optional_int(
            row["max_keepers"], "league.rules.max_keepers"
        ),
        playoff_teams=_optional_int(
            row["playoff_teams"], "league.rules.playoff_teams"
        ),
        playoff_week_start=_optional_int(
            row["playoff_week_start"], "league.rules.playoff_week_start"
        ),
        trade_deadline=_optional_int(
            row["trade_deadline"], "league.rules.trade_deadline"
        ),
        reserve_slots=_nonnegative_int(
            row["reserve_slots"], "league.rules.reserve_slots"
        ),
        taxi_slots=_nonnegative_int(row["taxi_slots"], "league.rules.taxi_slots"),
        position_limits=_string_int_mapping(
            row["position_limits"], "league.rules.position_limits"
        ),
        rule_settings=_mapping(
            row["rule_settings"], "league.rules.rule_settings"
        ),
    )
    stored = _text(row["rules_fingerprint"], "league.rules.rules_fingerprint")
    if rules.rules_fingerprint != stored:
        raise UnsafePersistedFantasySnapshot(
            "persisted rules_fingerprint does not match normalized rules"
        )
    return rules


def _rehydrate_draft(value: Mapping[str, Any]) -> DraftState:
    row = _exact_mapping(
        value,
        "league.draft",
        {
            "platform_draft_id",
            "status",
            "draft_type",
            "rounds",
            "teams",
            "start_time_ms",
            "draft_order",
            "slot_counts",
            "position_limits",
            "enforce_position_limits",
        },
    )
    return DraftState(
        platform_draft_id=_text(
            row["platform_draft_id"], "league.draft.platform_draft_id"
        ),
        status=_text(row["status"], "league.draft.status"),
        draft_type=_optional_text(row["draft_type"], "league.draft.draft_type"),
        rounds=_optional_int(row["rounds"], "league.draft.rounds"),
        teams=_optional_int(row["teams"], "league.draft.teams"),
        start_time_ms=_optional_int(
            row["start_time_ms"], "league.draft.start_time_ms"
        ),
        draft_order=_string_int_mapping(
            row["draft_order"], "league.draft.draft_order"
        ),
        slot_counts=_string_int_mapping(
            row["slot_counts"], "league.draft.slot_counts"
        ),
        position_limits=_string_int_mapping(
            row["position_limits"], "league.draft.position_limits"
        ),
        enforce_position_limits=_bool(
            row["enforce_position_limits"],
            "league.draft.enforce_position_limits",
        ),
    )


def _rehydrate_manager(value: Any, label: str) -> Manager:
    row = _exact_mapping(
        value,
        label,
        {"platform_user_id", "display_name", "team_name", "is_owner"},
    )
    return Manager(
        platform_user_id=_text(row["platform_user_id"], f"{label}.platform_user_id"),
        display_name=_text(row["display_name"], f"{label}.display_name"),
        team_name=_optional_text(row["team_name"], f"{label}.team_name"),
        is_owner=_bool(row["is_owner"], f"{label}.is_owner"),
    )


def _rehydrate_roster(value: Any, label: str) -> Roster:
    row = _exact_mapping(
        value,
        label,
        {
            "platform_roster_id",
            "platform_user_id",
            "players",
            "starters",
            "reserve",
            "taxi",
            "settings",
        },
    )
    return Roster(
        platform_roster_id=_text(
            row["platform_roster_id"], f"{label}.platform_roster_id"
        ),
        platform_user_id=_optional_text(
            row["platform_user_id"], f"{label}.platform_user_id"
        ),
        players=_string_tuple(row["players"], f"{label}.players"),
        starters=_string_tuple(row["starters"], f"{label}.starters"),
        reserve=_string_tuple(row["reserve"], f"{label}.reserve"),
        taxi=_string_tuple(row["taxi"], f"{label}.taxi"),
        settings=_mapping(row["settings"], f"{label}.settings"),
    )


def _rehydrate_transaction(value: Any, label: str) -> LeagueTransaction:
    row = _exact_mapping(
        value,
        label,
        {
            "platform_transaction_id",
            "transaction_type",
            "status",
            "week",
            "roster_ids",
            "creator_user_id",
            "created_at_ms",
            "status_updated_at_ms",
            "consenter_roster_ids",
            "adds",
            "drops",
            "traded_picks",
            "faab_transfers",
            "waiver_bid",
            "metadata",
        },
    )
    return LeagueTransaction(
        platform_transaction_id=_text(
            row["platform_transaction_id"], f"{label}.platform_transaction_id"
        ),
        transaction_type=_text(
            row["transaction_type"], f"{label}.transaction_type"
        ),
        status=_text(row["status"], f"{label}.status"),
        week=_optional_int(row["week"], f"{label}.week"),
        roster_ids=_string_tuple(row["roster_ids"], f"{label}.roster_ids"),
        creator_user_id=_optional_text(
            row["creator_user_id"], f"{label}.creator_user_id"
        ),
        created_at_ms=_optional_int(
            row["created_at_ms"], f"{label}.created_at_ms"
        ),
        status_updated_at_ms=_optional_int(
            row["status_updated_at_ms"], f"{label}.status_updated_at_ms"
        ),
        consenter_roster_ids=_string_tuple(
            row["consenter_roster_ids"], f"{label}.consenter_roster_ids"
        ),
        adds=_string_string_mapping(row["adds"], f"{label}.adds"),
        drops=_string_string_mapping(row["drops"], f"{label}.drops"),
        traded_picks=tuple(
            _rehydrate_traded_pick(item, f"{label}.traded_picks[{index}]")
            for index, item in enumerate(
                _sequence(row["traded_picks"], f"{label}.traded_picks")
            )
        ),
        faab_transfers=tuple(
            _rehydrate_faab_transfer(item, f"{label}.faab_transfers[{index}]")
            for index, item in enumerate(
                _sequence(row["faab_transfers"], f"{label}.faab_transfers")
            )
        ),
        waiver_bid=_optional_number(row["waiver_bid"], f"{label}.waiver_bid"),
        metadata=_mapping(row["metadata"], f"{label}.metadata"),
    )


def _rehydrate_traded_pick(value: Any, label: str) -> TradedPick:
    row = _exact_mapping(
        value,
        label,
        {
            "season",
            "round",
            "original_roster_id",
            "previous_owner_roster_id",
            "owner_roster_id",
        },
    )
    return TradedPick(
        season=_text(row["season"], f"{label}.season"),
        round=_optional_int(row["round"], f"{label}.round"),
        original_roster_id=_optional_text(
            row["original_roster_id"], f"{label}.original_roster_id"
        ),
        previous_owner_roster_id=_optional_text(
            row["previous_owner_roster_id"],
            f"{label}.previous_owner_roster_id",
        ),
        owner_roster_id=_optional_text(
            row["owner_roster_id"], f"{label}.owner_roster_id"
        ),
    )


def _rehydrate_faab_transfer(value: Any, label: str) -> FaabTransfer:
    row = _exact_mapping(
        value,
        label,
        {"sender_roster_id", "receiver_roster_id", "amount"},
    )
    return FaabTransfer(
        sender_roster_id=_optional_text(
            row["sender_roster_id"], f"{label}.sender_roster_id"
        ),
        receiver_roster_id=_optional_text(
            row["receiver_roster_id"], f"{label}.receiver_roster_id"
        ),
        amount=_optional_number(row["amount"], f"{label}.amount"),
    )


def _exact_mapping(
    value: Any,
    label: str,
    expected_keys: set[str],
) -> dict[str, Any]:
    result = _mapping(value, label)
    keys = set(result)
    if keys != expected_keys:
        missing = sorted(expected_keys - keys)
        extra = sorted(keys - expected_keys)
        details = []
        if missing:
            details.append(f"missing={missing}")
        if extra:
            details.append(f"extra={extra}")
        raise UnsafePersistedFantasySnapshot(
            f"{label} has unsupported shape ({', '.join(details)})"
        )
    return result


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise UnsafePersistedFantasySnapshot(f"{label} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise UnsafePersistedFantasySnapshot(f"{label} keys must be strings")
    return dict(value)


def _sequence(value: Any, label: str) -> list[Any]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise UnsafePersistedFantasySnapshot(f"{label} must be an array")
    return list(value)


def _string_tuple(value: Any, label: str) -> tuple[str, ...]:
    return tuple(
        _text(item, f"{label}[{index}]")
        for index, item in enumerate(_sequence(value, label))
    )


def _string_int_mapping(value: Any, label: str) -> dict[str, int]:
    result = _mapping(value, label)
    return {
        _text(key, f"{label}.key"): _int(item, f"{label}[{key!r}]")
        for key, item in result.items()
    }


def _string_string_mapping(value: Any, label: str) -> dict[str, str]:
    result = _mapping(value, label)
    return {
        _text(key, f"{label}.key"): _text(item, f"{label}[{key!r}]")
        for key, item in result.items()
    }


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise UnsafePersistedFantasySnapshot(
            f"{label} must be a nonblank canonical string"
        )
    return value


def _optional_text(value: Any, label: str) -> str | None:
    return None if value is None else _text(value, label)


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise UnsafePersistedFantasySnapshot(f"{label} must be boolean")
    return value


def _int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UnsafePersistedFantasySnapshot(f"{label} must be an integer")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    result = _int(value, label)
    if result < 0:
        raise UnsafePersistedFantasySnapshot(f"{label} cannot be negative")
    return result


def _optional_int(value: Any, label: str) -> int | None:
    return None if value is None else _int(value, label)


def _optional_number(value: Any, label: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnsafePersistedFantasySnapshot(f"{label} must be numeric or null")
    return value
