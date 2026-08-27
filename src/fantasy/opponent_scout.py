from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .models import FantasyLeagueState, MatchupTeam, Roster
from .roster_health import QUESTIONABLE_STATUSES, SERIOUS_STATUSES


@dataclass(frozen=True)
class OpponentPlayerFact:
    player_id: str
    name: str
    position: str
    nfl_team: str
    fantasy_slot: str
    status: str
    points: int | float | None

    @property
    def serious_status(self) -> bool:
        return self.status.casefold() in SERIOUS_STATUSES

    @property
    def questionable_status(self) -> bool:
        return self.status.casefold() in QUESTIONABLE_STATUSES


@dataclass(frozen=True)
class OpponentScout:
    week: int
    opponent_roster_id: str
    opponent_name: str
    opponent_record: str
    opponent_points_for: float
    my_matchup_points: int | float | None
    opponent_matchup_points: int | float | None
    open_starter_slots: int
    position_counts: Mapping[str, int]
    starters: tuple[OpponentPlayerFact, ...]
    bench: tuple[OpponentPlayerFact, ...]

    @property
    def serious_starter_count(self) -> int:
        return sum(1 for row in self.starters if row.serious_status)

    @property
    def questionable_starter_count(self) -> int:
        return sum(1 for row in self.starters if row.questionable_status)

    @property
    def starter_alert_count(self) -> int:
        return self.serious_starter_count + self.questionable_starter_count


def build_opponent_scout(
    league: FantasyLeagueState,
    matchups: Iterable[MatchupTeam],
    *,
    week: int,
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> OpponentScout | None:
    if isinstance(week, bool) or not isinstance(week, int) or week < 1:
        raise ValueError("week must be a positive integer")

    my_roster = _my_roster(league)
    if my_roster is None:
        return None

    matchup_rows = tuple(matchups)
    mine = next(
        (
            row
            for row in matchup_rows
            if row.platform_roster_id == my_roster.platform_roster_id
        ),
        None,
    )
    if mine is None or mine.matchup_id is None:
        return None

    opponents = tuple(
        row
        for row in matchup_rows
        if row.matchup_id == mine.matchup_id
        and row.platform_roster_id != mine.platform_roster_id
    )
    if not opponents:
        return None
    if len(opponents) != 1:
        raise ValueError("Sleeper matchup has multiple opponent rows")

    opponent_matchup = opponents[0]
    opponent_roster = next(
        (
            roster
            for roster in league.rosters
            if roster.platform_roster_id == opponent_matchup.platform_roster_id
        ),
        None,
    )
    if opponent_roster is None:
        raise ValueError("Sleeper matchup opponent roster was not found")

    manager_names = {
        manager.platform_user_id: (
            manager.team_name
            or manager.display_name
            or manager.platform_user_id
        )
        for manager in league.managers
    }
    opponent_name = manager_names.get(
        opponent_roster.platform_user_id or "",
        f"Roster {opponent_roster.platform_roster_id}",
    )

    starter_ids = _clean_ids(
        opponent_matchup.starters
        if opponent_matchup.starters
        else opponent_roster.starters
    )
    all_player_ids = _clean_ids(
        (
            *opponent_roster.players,
            *opponent_roster.starters,
            *opponent_roster.reserve,
            *opponent_roster.taxi,
        )
    )

    starters = tuple(
        _player_fact(
            player_id,
            opponent_roster,
            player_catalog,
            points=opponent_matchup.players_points.get(player_id),
            force_slot="Starter",
        )
        for player_id in starter_ids
    )
    starter_set = set(starter_ids)
    bench = tuple(
        _player_fact(
            player_id,
            opponent_roster,
            player_catalog,
            points=opponent_matchup.players_points.get(player_id),
        )
        for player_id in all_player_ids
        if player_id not in starter_set
    )

    position_counts: Counter[str] = Counter()
    for player_id in all_player_ids:
        player = player_catalog.get(player_id) or {}
        position = str(player.get("position") or "").strip().upper()
        if position:
            position_counts[position] += 1

    starter_slots = len(league.rules.starter_positions)
    return OpponentScout(
        week=week,
        opponent_roster_id=opponent_roster.platform_roster_id,
        opponent_name=opponent_name,
        opponent_record=_record(opponent_roster),
        opponent_points_for=_points_for(opponent_roster),
        my_matchup_points=mine.points,
        opponent_matchup_points=opponent_matchup.points,
        open_starter_slots=max(0, starter_slots - len(starter_ids)),
        position_counts=dict(sorted(position_counts.items())),
        starters=starters,
        bench=bench,
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


def _clean_ids(values: Iterable[Any]) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(value)
            for value in values
            if str(value or "").strip() not in {"", "0"}
        )
    )


def _player_fact(
    player_id: str,
    roster: Roster,
    catalog: Mapping[str, Mapping[str, Any]],
    *,
    points: Any,
    force_slot: str | None = None,
) -> OpponentPlayerFact:
    player = catalog.get(player_id) or {}
    raw_status = (
        str(player.get("injury_status") or "").strip()
        or str(player.get("status") or "").strip()
        or "Active"
    )
    return OpponentPlayerFact(
        player_id=player_id,
        name=_player_name(player, player_id),
        position=str(player.get("position") or "—").strip().upper() or "—",
        nfl_team=str(player.get("team") or "FA").strip().upper() or "FA",
        fantasy_slot=force_slot or _roster_slot(roster, player_id),
        status=raw_status.replace("_", " ").title(),
        points=_number_or_none(points),
    )


def _roster_slot(roster: Roster, player_id: str) -> str:
    if player_id in roster.reserve:
        return "IR"
    if player_id in roster.taxi:
        return "Taxi"
    if player_id in roster.starters:
        return "Starter"
    return "Bench"


def _record(roster: Roster) -> str:
    settings = dict(roster.settings or {})
    wins = int(settings.get("wins") or 0)
    losses = int(settings.get("losses") or 0)
    ties = int(settings.get("ties") or 0)
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _points_for(roster: Roster) -> float:
    settings = dict(roster.settings or {})
    whole = float(settings.get("fpts") or 0)
    decimal = float(settings.get("fpts_decimal") or 0) / 100
    return whole + decimal


def _player_name(player: Mapping[str, Any], player_id: str) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id


def _number_or_none(value: Any) -> int | float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text) if "." in text else int(text)
    except (TypeError, ValueError):
        return None
