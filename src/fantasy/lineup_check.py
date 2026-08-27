from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .models import FantasyLeagueState, MatchupTeam, Roster
from .roster_health import QUESTIONABLE_STATUSES, SERIOUS_STATUSES


READY = "READY"
WATCH = "WATCH"
NEEDS_ACTION = "NEEDS_ACTION"

FLEX_ELIGIBILITY: Mapping[str, frozenset[str]] = {
    "FLEX": frozenset({"RB", "WR", "TE"}),
    "WRRBTE_FLEX": frozenset({"RB", "WR", "TE"}),
    "WRRB_FLEX": frozenset({"RB", "WR"}),
    "REC_FLEX": frozenset({"WR", "TE"}),
    "SUPER_FLEX": frozenset({"QB", "RB", "WR", "TE"}),
    "IDP_FLEX": frozenset({"DL", "LB", "DB"}),
}


@dataclass(frozen=True)
class LineupPlayerFact:
    player_id: str
    name: str
    position: str
    fantasy_positions: tuple[str, ...]
    nfl_team: str
    status: str

    @property
    def serious_status(self) -> bool:
        return self.status.casefold() in SERIOUS_STATUSES

    @property
    def questionable_status(self) -> bool:
        return self.status.casefold() in QUESTIONABLE_STATUSES


@dataclass(frozen=True)
class LineupSlotCheck:
    slot_index: int
    slot: str
    starter: LineupPlayerFact | None
    eligible_alternatives: tuple[LineupPlayerFact, ...]
    state: str
    reason: str

    @property
    def open(self) -> bool:
        return self.starter is None

    @property
    def needs_action(self) -> bool:
        return self.state == NEEDS_ACTION

    @property
    def needs_watch(self) -> bool:
        return self.state == WATCH


@dataclass(frozen=True)
class LineupCheck:
    slots: tuple[LineupSlotCheck, ...]
    bench: tuple[LineupPlayerFact, ...]
    used_matchup_lineup: bool

    @property
    def starter_slots(self) -> int:
        return len(self.slots)

    @property
    def filled_starter_slots(self) -> int:
        return sum(1 for row in self.slots if not row.open)

    @property
    def open_starter_slots(self) -> int:
        return sum(1 for row in self.slots if row.open)

    @property
    def needs_action_count(self) -> int:
        return sum(1 for row in self.slots if row.needs_action)

    @property
    def watch_count(self) -> int:
        return sum(1 for row in self.slots if row.needs_watch)

    @property
    def ready_count(self) -> int:
        return sum(1 for row in self.slots if row.state == READY)

    @property
    def healthy_bench_count(self) -> int:
        return sum(1 for row in self.bench if not row.serious_status)

    @property
    def needs_action(self) -> bool:
        return self.needs_action_count > 0

    @property
    def needs_watch(self) -> bool:
        return self.watch_count > 0


def build_lineup_check(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    matchup: MatchupTeam | None = None,
) -> LineupCheck | None:
    roster = _my_roster(league)
    if roster is None:
        return None

    starter_slots = tuple(str(slot).strip().upper() for slot in league.rules.starter_positions)
    if not starter_slots:
        return LineupCheck(slots=(), bench=(), used_matchup_lineup=False)

    used_matchup = bool(
        matchup is not None
        and matchup.platform_roster_id == roster.platform_roster_id
        and matchup.starters
    )
    raw_starters: Iterable[Any] = (
        matchup.starters if used_matchup and matchup is not None else roster.starters
    )
    starter_ids = _ordered_starter_ids(raw_starters, len(starter_slots))
    active_starter_ids = {
        player_id for player_id in starter_ids if player_id is not None
    }

    reserve_set = set(_clean_ids(roster.reserve))
    taxi_set = set(_clean_ids(roster.taxi))
    bench_ids = tuple(
        player_id
        for player_id in _clean_ids(roster.players)
        if player_id not in active_starter_ids
        and player_id not in reserve_set
        and player_id not in taxi_set
    )
    bench = tuple(_player_fact(player_id, player_catalog) for player_id in bench_ids)

    slots: list[LineupSlotCheck] = []
    for index, slot in enumerate(starter_slots):
        player_id = starter_ids[index]
        starter = (
            _player_fact(player_id, player_catalog)
            if player_id is not None
            else None
        )
        alternatives = tuple(
            sorted(
                (
                    row
                    for row in bench
                    if not row.serious_status and _eligible_for_slot(row, slot)
                ),
                key=_alternative_sort_key,
            )
        )
        state, reason = _slot_state(slot, starter)
        slots.append(
            LineupSlotCheck(
                slot_index=index,
                slot=slot,
                starter=starter,
                eligible_alternatives=alternatives,
                state=state,
                reason=reason,
            )
        )

    return LineupCheck(
        slots=tuple(slots),
        bench=bench,
        used_matchup_lineup=used_matchup,
    )


def _slot_state(
    slot: str,
    starter: LineupPlayerFact | None,
) -> tuple[str, str]:
    if starter is None:
        return NEEDS_ACTION, "Starter slot is open."
    if not _eligible_for_slot(starter, slot):
        return NEEDS_ACTION, "Current starter is not eligible for this slot."
    if starter.serious_status:
        return NEEDS_ACTION, f"Current starter status: {starter.status}."
    if starter.questionable_status:
        return WATCH, f"Current starter status: {starter.status}."
    return READY, "No factual lineup-status issue."


def eligible_positions_for_slot(slot: str) -> frozenset[str]:
    normalized = str(slot or "").strip().upper()
    if not normalized:
        raise ValueError("slot is required")
    flex_positions = FLEX_ELIGIBILITY.get(normalized)
    if flex_positions is not None:
        return flex_positions
    return frozenset({normalized})


def positions_eligible_for_slot(
    positions: Iterable[str],
    slot: str,
) -> bool:
    normalized_positions = {
        str(value).strip().upper()
        for value in positions
        if str(value or "").strip()
    }
    if not normalized_positions:
        return False
    return bool(normalized_positions & eligible_positions_for_slot(slot))


def _eligible_for_slot(player: LineupPlayerFact, slot: str) -> bool:
    positions = player.fantasy_positions or (player.position,)
    return positions_eligible_for_slot(positions, slot)


def _alternative_sort_key(player: LineupPlayerFact) -> tuple[int, str, str]:
    return (
        1 if player.questionable_status else 0,
        player.name.casefold(),
        player.player_id,
    )


def _my_roster(league: FantasyLeagueState) -> Roster | None:
    if league.my_platform_roster_id:
        for roster in league.rosters:
            if roster.platform_roster_id == league.my_platform_roster_id:
                return roster

    if league.current_platform_user_id:
        for roster in league.rosters:
            if roster.platform_user_id == league.current_platform_user_id:
                return roster

    return None


def _ordered_starter_ids(
    values: Iterable[Any],
    slot_count: int,
) -> tuple[str | None, ...]:
    raw = tuple(values)
    rows: list[str | None] = []
    for index in range(slot_count):
        value = raw[index] if index < len(raw) else None
        player_id = str(value or "").strip()
        rows.append(None if player_id in {"", "0"} else player_id)
    return tuple(rows)


def _clean_ids(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(value).strip()
            for value in values
            if str(value or "").strip() not in {"", "0"}
        )
    )


def _player_fact(
    player_id: str,
    catalog: Mapping[str, Mapping[str, Any]],
) -> LineupPlayerFact:
    player = catalog.get(player_id) or {}
    raw_status = (
        str(player.get("injury_status") or "").strip()
        or str(player.get("status") or "").strip()
        or "Active"
    )
    primary_position = str(player.get("position") or "—").strip().upper() or "—"
    raw_fantasy_positions = player.get("fantasy_positions")
    if isinstance(raw_fantasy_positions, (list, tuple, set)):
        fantasy_positions = tuple(
            dict.fromkeys(
                str(value).strip().upper()
                for value in raw_fantasy_positions
                if str(value or "").strip()
            )
        )
    else:
        fantasy_positions = ()
    if not fantasy_positions and primary_position != "—":
        fantasy_positions = (primary_position,)

    return LineupPlayerFact(
        player_id=player_id,
        name=_player_name(player, player_id),
        position=primary_position,
        fantasy_positions=fantasy_positions,
        nfl_team=str(player.get("team") or "FA").strip().upper() or "FA",
        status=raw_status.replace("_", " ").title(),
    )


def _player_name(player: Mapping[str, Any], player_id: str) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id
