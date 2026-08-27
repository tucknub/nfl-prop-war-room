from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .models import FantasyLeagueState, Roster
from .roster_health import QUESTIONABLE_STATUSES, SERIOUS_STATUSES


@dataclass(frozen=True)
class LineupPlayerFact:
    player_id: str
    name: str
    position: str
    nfl_team: str
    status: str

    @property
    def serious_status(self) -> bool:
        return self.status.casefold() in SERIOUS_STATUSES

    @property
    def questionable_status(self) -> bool:
        return self.status.casefold() in QUESTIONABLE_STATUSES


@dataclass(frozen=True)
class StarterLineupAlert:
    starter: LineupPlayerFact
    same_position_bench: tuple[LineupPlayerFact, ...]


@dataclass(frozen=True)
class LineupCheck:
    starter_slots: int
    filled_starter_slots: int
    open_starter_slots: int
    starters: tuple[LineupPlayerFact, ...]
    bench: tuple[LineupPlayerFact, ...]
    serious_starters: tuple[StarterLineupAlert, ...]
    questionable_starters: tuple[StarterLineupAlert, ...]

    @property
    def healthy_bench_count(self) -> int:
        return sum(1 for row in self.bench if not row.serious_status)

    @property
    def serious_starter_count(self) -> int:
        return len(self.serious_starters)

    @property
    def questionable_starter_count(self) -> int:
        return len(self.questionable_starters)

    @property
    def needs_action(self) -> bool:
        return bool(self.open_starter_slots or self.serious_starter_count)

    @property
    def needs_watch(self) -> bool:
        return bool(self.questionable_starter_count)


def build_lineup_check(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> LineupCheck | None:
    roster = _my_roster(league)
    if roster is None:
        return None

    starter_ids = _clean_ids(roster.starters)
    starter_set = set(starter_ids)
    reserve_set = set(_clean_ids(roster.reserve))
    taxi_set = set(_clean_ids(roster.taxi))
    bench_ids = tuple(
        player_id
        for player_id in _clean_ids(roster.players)
        if player_id not in starter_set
        and player_id not in reserve_set
        and player_id not in taxi_set
    )

    starters = tuple(
        _player_fact(player_id, player_catalog)
        for player_id in starter_ids
    )
    bench = tuple(
        _player_fact(player_id, player_catalog)
        for player_id in bench_ids
    )

    serious = tuple(
        _starter_alert(row, bench)
        for row in starters
        if row.serious_status
    )
    questionable = tuple(
        _starter_alert(row, bench)
        for row in starters
        if row.questionable_status
    )

    required = len(league.rules.starter_positions)
    return LineupCheck(
        starter_slots=required,
        filled_starter_slots=len(starter_ids),
        open_starter_slots=max(0, required - len(starter_ids)),
        starters=starters,
        bench=bench,
        serious_starters=serious,
        questionable_starters=questionable,
    )


def _starter_alert(
    starter: LineupPlayerFact,
    bench: tuple[LineupPlayerFact, ...],
) -> StarterLineupAlert:
    options = tuple(
        row
        for row in bench
        if row.position == starter.position and not row.serious_status
    )
    return StarterLineupAlert(
        starter=starter,
        same_position_bench=options,
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


def _clean_ids(values) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(value)
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
    return LineupPlayerFact(
        player_id=player_id,
        name=_player_name(player, player_id),
        position=str(player.get("position") or "—").strip().upper() or "—",
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
