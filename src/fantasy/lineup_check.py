from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .models import FantasyLeagueState, Roster


READY = "READY"
WATCH = "WATCH"
NEEDS_ATTENTION = "NEEDS_ATTENTION"
PRE_DRAFT = "PRE_DRAFT"

OK = "OK"
QUESTIONABLE = "QUESTIONABLE"
UNAVAILABLE = "UNAVAILABLE"
OPEN = "OPEN"

SERIOUS_STATUSES = {
    "out",
    "ir",
    "pup",
    "suspended",
    "doubtful",
}
QUESTIONABLE_STATUSES = {"questionable", "q"}


@dataclass(frozen=True)
class LineupSlotCheck:
    slot: str
    player_id: str | None
    player_name: str | None
    player_position: str | None
    nfl_team: str | None
    player_status: str | None
    state: str


@dataclass(frozen=True)
class LineupCheckSummary:
    status: str
    slots: tuple[LineupSlotCheck, ...]

    @property
    def open_slots(self) -> int:
        return sum(1 for row in self.slots if row.state == OPEN)

    @property
    def unavailable_starters(self) -> int:
        return sum(1 for row in self.slots if row.state == UNAVAILABLE)

    @property
    def questionable_starters(self) -> int:
        return sum(1 for row in self.slots if row.state == QUESTIONABLE)

    @property
    def issue_count(self) -> int:
        return (
            self.open_slots
            + self.unavailable_starters
            + self.questionable_starters
        )


def analyze_starting_lineup(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> LineupCheckSummary:
    roster = _my_roster(league)
    starter_slots = tuple(league.rules.starter_positions)

    if roster is None or not roster.players:
        return LineupCheckSummary(
            status=PRE_DRAFT,
            slots=tuple(
                LineupSlotCheck(
                    slot=slot,
                    player_id=None,
                    player_name=None,
                    player_position=None,
                    nfl_team=None,
                    player_status=None,
                    state=OPEN,
                )
                for slot in starter_slots
            ),
        )

    starter_ids = tuple(str(value or "").strip() for value in roster.starters)
    checks: list[LineupSlotCheck] = []

    for index, slot in enumerate(starter_slots):
        player_id = starter_ids[index] if index < len(starter_ids) else ""
        if not player_id or player_id == "0":
            checks.append(
                LineupSlotCheck(
                    slot=slot,
                    player_id=None,
                    player_name=None,
                    player_position=None,
                    nfl_team=None,
                    player_status=None,
                    state=OPEN,
                )
            )
            continue

        player = player_catalog.get(player_id) or {}
        name = _player_name(player, player_id)
        position = str(player.get("position") or "").strip().upper() or None
        nfl_team = str(player.get("team") or "").strip().upper() or None
        raw_status = (
            str(player.get("injury_status") or "").strip()
            or str(player.get("status") or "").strip()
        )
        normalized_status = raw_status.casefold()

        if normalized_status in SERIOUS_STATUSES:
            state = UNAVAILABLE
        elif normalized_status in QUESTIONABLE_STATUSES:
            state = QUESTIONABLE
        else:
            state = OK

        checks.append(
            LineupSlotCheck(
                slot=slot,
                player_id=player_id,
                player_name=name,
                player_position=position,
                nfl_team=nfl_team,
                player_status=raw_status or "Active",
                state=state,
            )
        )

    if any(row.state in {OPEN, UNAVAILABLE} for row in checks):
        status = NEEDS_ATTENTION
    elif any(row.state == QUESTIONABLE for row in checks):
        status = WATCH
    else:
        status = READY

    return LineupCheckSummary(
        status=status,
        slots=tuple(checks),
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


def _player_name(player: Mapping[str, Any], player_id: str) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id
