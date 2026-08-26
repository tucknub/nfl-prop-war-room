from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping

from .models import DraftState, FantasyLeagueState, LeagueTransaction, Roster

_PLAYER_EVENT_TYPES = {
    "PLAYER_ADDED",
    "PLAYER_DROPPED",
    "PLAYER_BECAME_AVAILABLE",
    "STARTER_CHANGED",
    "IR_CHANGED",
}


@dataclass(frozen=True)
class FantasySnapshot:
    """One accepted provider-state observation used only for deterministic diffing."""

    league: FantasyLeagueState
    transactions: tuple[LeagueTransaction, ...] = ()

    @property
    def fingerprint(self) -> str:
        return _fingerprint(_snapshot_payload(self))


@dataclass(frozen=True)
class FantasyChangeEvent:
    event_type: str
    platform: str
    platform_league_id: str
    season: str
    platform_roster_id: str | None = None
    platform_player_id: str | None = None
    before_value: Any = None
    after_value: Any = None
    source_transaction_ids: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    event_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        payload = {
            "event_type": self.event_type,
            "platform": self.platform,
            "platform_league_id": self.platform_league_id,
            "season": self.season,
            "platform_roster_id": self.platform_roster_id,
            "platform_player_id": self.platform_player_id,
            "before_value": self.before_value,
            "after_value": self.after_value,
            "source_transaction_ids": list(self.source_transaction_ids),
            "reason_codes": list(self.reason_codes),
        }
        object.__setattr__(self, "event_fingerprint", _fingerprint(payload))


class UnsafeSnapshotTransition(ValueError):
    """Raised when a diff would require interpreting degraded provider state as real change."""


def derive_fantasy_change_events(
    previous: FantasySnapshot,
    current: FantasySnapshot,
) -> tuple[FantasyChangeEvent, ...]:
    """Derive deterministic events from two accepted snapshots without mutating either."""

    _validate_transition(previous, current)
    if previous.fingerprint == current.fingerprint:
        return ()

    before = previous.league
    after = current.league
    events: list[FantasyChangeEvent] = []

    if before.rules_fingerprint != after.rules_fingerprint:
        events.append(
            _event(
                after,
                "LEAGUE_RULE_CHANGED",
                before_value={"rules_fingerprint": before.rules_fingerprint},
                after_value={"rules_fingerprint": after.rules_fingerprint},
                reason_codes=("RULES_FINGERPRINT_CHANGED",),
            )
        )

    if _draft_payload(before.draft) != _draft_payload(after.draft):
        events.append(
            _event(
                after,
                "DRAFT_STATE_CHANGED",
                before_value=_draft_payload(before.draft),
                after_value=_draft_payload(after.draft),
                reason_codes=("NORMALIZED_DRAFT_STATE_CHANGED",),
            )
        )

    ownership_initialized = not before.ownership_ready and after.ownership_ready
    if ownership_initialized:
        events.append(
            _event(
                after,
                "OWNERSHIP_INITIALIZED",
                before_value={"ownership_ready": False},
                after_value={
                    "ownership_ready": True,
                    "rosters_with_players": sum(1 for roster in after.rosters if roster.players),
                    "owned_player_count": len(_ownership_index(after)),
                },
                reason_codes=("FIRST_AUTHORITATIVE_OWNERSHIP",),
            )
        )
    elif before.ownership_ready and after.ownership_ready:
        events.extend(_derive_roster_events(before, after, current.transactions))

    events.extend(_derive_new_transaction_events(previous, current))
    return tuple(sorted(events, key=_event_sort_key))


def _validate_transition(previous: FantasySnapshot, current: FantasySnapshot) -> None:
    before = previous.league
    after = current.league
    identity_before = (before.platform, before.platform_league_id, before.season)
    identity_after = (after.platform, after.platform_league_id, after.season)
    if identity_before != identity_after:
        raise UnsafeSnapshotTransition(
            "snapshots must represent the same platform league and season"
        )
    if before.rules_ready and not after.rules_ready:
        raise UnsafeSnapshotTransition("rules readiness regressed; fail closed")
    if before.draft_ready and not after.draft_ready:
        raise UnsafeSnapshotTransition("draft readiness regressed; fail closed")
    if before.ownership_ready and not after.ownership_ready:
        raise UnsafeSnapshotTransition("ownership readiness regressed; fail closed")
    _validate_roster_integrity(before)
    _validate_roster_integrity(after)


def _validate_roster_integrity(state: FantasyLeagueState) -> None:
    if not state.ownership_ready:
        return
    seen: dict[str, str] = {}
    for roster in state.rosters:
        player_set = _real_player_set(roster.players)
        for player_id in player_set:
            prior = seen.get(player_id)
            if prior is not None and prior != roster.platform_roster_id:
                raise UnsafeSnapshotTransition(
                    f"player {player_id} is owned by multiple rosters in one snapshot"
                )
            seen[player_id] = roster.platform_roster_id
        starters = _real_player_set(roster.starters)
        reserve = _real_player_set(roster.reserve)
        if not starters.issubset(player_set):
            raise UnsafeSnapshotTransition(
                f"roster {roster.platform_roster_id} has starter outside player list"
            )
        if not reserve.issubset(player_set):
            raise UnsafeSnapshotTransition(
                f"roster {roster.platform_roster_id} has reserve player outside player list"
            )


def _derive_roster_events(
    before: FantasyLeagueState,
    after: FantasyLeagueState,
    current_transactions: tuple[LeagueTransaction, ...],
) -> list[FantasyChangeEvent]:
    events: list[FantasyChangeEvent] = []
    old_owners = _ownership_index(before)
    new_owners = _ownership_index(after)
    all_players = sorted(set(old_owners) | set(new_owners))

    for player_id in all_players:
        old_roster = old_owners.get(player_id)
        new_roster = new_owners.get(player_id)
        if old_roster == new_roster:
            continue
        tx_ids = _transaction_ids_for_player(current_transactions, player_id)
        if old_roster is not None:
            events.append(
                _event(
                    after,
                    "PLAYER_DROPPED",
                    roster_id=old_roster,
                    player_id=player_id,
                    before_value={"owner_roster_id": old_roster},
                    after_value={"owner_roster_id": new_roster},
                    source_transaction_ids=tx_ids,
                    reason_codes=("OWNERSHIP_CHANGED",),
                )
            )
        if new_roster is not None:
            events.append(
                _event(
                    after,
                    "PLAYER_ADDED",
                    roster_id=new_roster,
                    player_id=player_id,
                    before_value={"owner_roster_id": old_roster},
                    after_value={"owner_roster_id": new_roster},
                    source_transaction_ids=tx_ids,
                    reason_codes=("OWNERSHIP_CHANGED",),
                )
            )
        else:
            events.append(
                _event(
                    after,
                    "PLAYER_BECAME_AVAILABLE",
                    roster_id=old_roster,
                    player_id=player_id,
                    before_value={"owner_roster_id": old_roster},
                    after_value={"owner_roster_id": None},
                    source_transaction_ids=tx_ids,
                    reason_codes=("UNOWNED_AFTER_ACCEPTED_SNAPSHOT",),
                )
            )

    before_rosters = {roster.platform_roster_id: roster for roster in before.rosters}
    after_rosters = {roster.platform_roster_id: roster for roster in after.rosters}
    for roster_id in sorted(set(before_rosters) & set(after_rosters)):
        old = before_rosters[roster_id]
        new = after_rosters[roster_id]
        events.extend(_derive_membership_flag_events(after, old, new, "starters", "STARTER_CHANGED"))
        events.extend(_derive_membership_flag_events(after, old, new, "reserve", "IR_CHANGED"))

        old_faab = _setting_number(old.settings, "waiver_budget_used")
        new_faab = _setting_number(new.settings, "waiver_budget_used")
        if old_faab is not None and new_faab is not None and old_faab != new_faab:
            events.append(
                _event(
                    after,
                    "FAAB_CHANGED",
                    roster_id=roster_id,
                    before_value={"waiver_budget_used": old_faab},
                    after_value={"waiver_budget_used": new_faab},
                    reason_codes=("PROVIDER_FAAB_USED_CHANGED",),
                )
            )

        old_priority = _setting_number(old.settings, "waiver_position")
        new_priority = _setting_number(new.settings, "waiver_position")
        if old_priority is not None and new_priority is not None and old_priority != new_priority:
            events.append(
                _event(
                    after,
                    "WAIVER_PRIORITY_CHANGED",
                    roster_id=roster_id,
                    before_value={"waiver_position": old_priority},
                    after_value={"waiver_position": new_priority},
                    reason_codes=("PROVIDER_WAIVER_POSITION_CHANGED",),
                )
            )

    return events


def _derive_membership_flag_events(
    state: FantasyLeagueState,
    before_roster: Roster,
    after_roster: Roster,
    attribute: str,
    event_type: str,
) -> list[FantasyChangeEvent]:
    before_ids = _real_player_set(getattr(before_roster, attribute))
    after_ids = _real_player_set(getattr(after_roster, attribute))
    events: list[FantasyChangeEvent] = []
    for player_id in sorted(before_ids ^ after_ids):
        events.append(
            _event(
                state,
                event_type,
                roster_id=after_roster.platform_roster_id,
                player_id=player_id,
                before_value={attribute: player_id in before_ids},
                after_value={attribute: player_id in after_ids},
                reason_codes=(f"{attribute.upper()}_MEMBERSHIP_CHANGED",),
            )
        )
    return events


def _derive_new_transaction_events(
    previous: FantasySnapshot,
    current: FantasySnapshot,
) -> list[FantasyChangeEvent]:
    before_ids = {tx.platform_transaction_id for tx in previous.transactions}
    events: list[FantasyChangeEvent] = []
    for tx in current.transactions:
        if tx.platform_transaction_id in before_ids or tx.status.lower() != "complete":
            continue
        events.append(
            _event(
                current.league,
                "TRANSACTION_COMPLETED",
                before_value=None,
                after_value={
                    "transaction_id": tx.platform_transaction_id,
                    "transaction_type": tx.transaction_type,
                    "week": tx.week,
                    "roster_ids": list(tx.roster_ids),
                    "adds": dict(sorted(tx.adds.items())),
                    "drops": dict(sorted(tx.drops.items())),
                    "waiver_bid": tx.waiver_bid,
                },
                source_transaction_ids=(tx.platform_transaction_id,),
                reason_codes=("NEW_COMPLETED_PROVIDER_TRANSACTION",),
            )
        )
    return events


def _ownership_index(state: FantasyLeagueState) -> dict[str, str]:
    ownership: dict[str, str] = {}
    for roster in state.rosters:
        for player_id in _real_player_set(roster.players):
            ownership[player_id] = roster.platform_roster_id
    return ownership


def _transaction_ids_for_player(
    transactions: Iterable[LeagueTransaction],
    player_id: str,
) -> tuple[str, ...]:
    ids = {
        tx.platform_transaction_id
        for tx in transactions
        if tx.status.lower() == "complete" and (player_id in tx.adds or player_id in tx.drops)
    }
    return tuple(sorted(ids))


def _real_player_set(values: Iterable[str]) -> set[str]:
    return {str(value).strip() for value in values if str(value).strip() not in {"", "0"}}


def _setting_number(settings: Mapping[str, Any], key: str) -> int | float | None:
    value = settings.get(key)
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        return float(text) if "." in text else int(text)
    except (TypeError, ValueError):
        return None


def _event(
    state: FantasyLeagueState,
    event_type: str,
    *,
    roster_id: str | None = None,
    player_id: str | None = None,
    before_value: Any = None,
    after_value: Any = None,
    source_transaction_ids: tuple[str, ...] = (),
    reason_codes: tuple[str, ...] = (),
) -> FantasyChangeEvent:
    return FantasyChangeEvent(
        event_type=event_type,
        platform=state.platform,
        platform_league_id=state.platform_league_id,
        season=state.season,
        platform_roster_id=roster_id,
        platform_player_id=player_id,
        before_value=before_value,
        after_value=after_value,
        source_transaction_ids=tuple(sorted(source_transaction_ids)),
        reason_codes=reason_codes,
    )


def _snapshot_payload(snapshot: FantasySnapshot) -> dict[str, Any]:
    state = snapshot.league
    return {
        "platform": state.platform,
        "platform_league_id": state.platform_league_id,
        "season": state.season,
        "status": state.status,
        "rules_fingerprint": state.rules_fingerprint,
        "draft": _draft_payload(state.draft),
        "rules_ready": state.rules_ready,
        "draft_ready": state.draft_ready,
        "ownership_ready": state.ownership_ready,
        "rosters": [
            {
                "roster_id": roster.platform_roster_id,
                "user_id": roster.platform_user_id,
                "players": sorted(_real_player_set(roster.players)),
                "starters": sorted(_real_player_set(roster.starters)),
                "reserve": sorted(_real_player_set(roster.reserve)),
                "taxi": sorted(_real_player_set(roster.taxi)),
                "waiver_budget_used": _setting_number(roster.settings, "waiver_budget_used"),
                "waiver_position": _setting_number(roster.settings, "waiver_position"),
            }
            for roster in sorted(state.rosters, key=lambda value: value.platform_roster_id)
        ],
        "transactions": sorted(
            tx.platform_transaction_id for tx in snapshot.transactions if tx.status.lower() == "complete"
        ),
    }


def _draft_payload(draft: DraftState | None) -> dict[str, Any] | None:
    if draft is None:
        return None
    return {
        "platform_draft_id": draft.platform_draft_id,
        "status": draft.status,
        "draft_type": draft.draft_type,
        "rounds": draft.rounds,
        "teams": draft.teams,
        "start_time_ms": draft.start_time_ms,
        "draft_order": dict(sorted(draft.draft_order.items())),
        "slot_counts": dict(sorted(draft.slot_counts.items())),
        "position_limits": dict(sorted(draft.position_limits.items())),
        "enforce_position_limits": draft.enforce_position_limits,
    }


def _fingerprint(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(raw.encode("utf-8")).hexdigest()


def _event_sort_key(event: FantasyChangeEvent) -> tuple[str, str, str, str]:
    return (
        event.event_type,
        event.platform_roster_id or "",
        event.platform_player_id or "",
        event.event_fingerprint,
    )
