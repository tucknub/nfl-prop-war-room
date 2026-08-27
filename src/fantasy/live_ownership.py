from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .models import FantasyLeagueState, Roster


MINE = "MINE"
OTHER = "OTHER"
AVAILABLE = "AVAILABLE"
UNKNOWN = "UNKNOWN"

STARTER = "Starter"
BENCH = "Bench"
RESERVE = "IR"
TAXI = "Taxi"


class UnsafeLiveOwnership(ValueError):
    """Raised when direct provider ownership contradicts itself."""


@dataclass(frozen=True)
class LiveLeaguePlayerStatus:
    platform_league_id: str
    league_name: str
    status: str
    platform_roster_id: str | None = None
    platform_user_id: str | None = None
    owner_name: str | None = None
    roster_slot: str | None = None

    @property
    def available(self) -> bool:
        return self.status == AVAILABLE

    @property
    def mine(self) -> bool:
        return self.status == MINE


@dataclass(frozen=True)
class LiveCrossLeaguePlayer:
    sleeper_player_id: str
    statuses: tuple[LiveLeaguePlayerStatus, ...]

    @property
    def mine_in(self) -> tuple[str, ...]:
        return tuple(row.league_name for row in self.statuses if row.status == MINE)

    @property
    def available_in(self) -> tuple[str, ...]:
        return tuple(
            row.league_name for row in self.statuses if row.status == AVAILABLE
        )

    @property
    def owned_elsewhere_in(self) -> tuple[str, ...]:
        return tuple(row.league_name for row in self.statuses if row.status == OTHER)

    @property
    def actionable_elsewhere(self) -> bool:
        return bool(self.mine_in and self.available_in)


def lookup_live_sleeper_player(
    leagues: Iterable[FantasyLeagueState],
    sleeper_player_id: str,
) -> LiveCrossLeaguePlayer:
    player_id = str(sleeper_player_id or "").strip()
    if not player_id:
        raise ValueError("sleeper_player_id is required")

    statuses = tuple(
        _lookup_in_league(league, player_id)
        for league in tuple(leagues)
    )
    return LiveCrossLeaguePlayer(
        sleeper_player_id=player_id,
        statuses=statuses,
    )


def my_players_available_elsewhere(
    leagues: Iterable[FantasyLeagueState],
) -> tuple[LiveCrossLeaguePlayer, ...]:
    league_rows = tuple(leagues)
    my_player_ids: list[str] = []
    seen: set[str] = set()

    for league in league_rows:
        my_roster = _my_roster(league)
        if my_roster is None:
            continue
        for player_id in _roster_player_ids(my_roster):
            if player_id in seen:
                continue
            seen.add(player_id)
            my_player_ids.append(player_id)

    rows = [
        lookup_live_sleeper_player(league_rows, player_id)
        for player_id in my_player_ids
    ]
    return tuple(row for row in rows if row.actionable_elsewhere)


def _lookup_in_league(
    league: FantasyLeagueState,
    player_id: str,
) -> LiveLeaguePlayerStatus:
    manager_names = {
        manager.platform_user_id: (
            manager.team_name or manager.display_name or manager.platform_user_id
        )
        for manager in league.managers
    }

    owner: Roster | None = None
    for roster in league.rosters:
        if player_id not in _roster_player_ids(roster):
            continue
        if owner is not None and owner.platform_roster_id != roster.platform_roster_id:
            raise UnsafeLiveOwnership(
                f"Sleeper player {player_id} appears on multiple rosters in "
                f"league {league.platform_league_id}"
            )
        owner = roster

    if owner is None:
        return LiveLeaguePlayerStatus(
            platform_league_id=league.platform_league_id,
            league_name=league.name or league.platform_league_id,
            status=(AVAILABLE if league.ownership_ready else UNKNOWN),
        )

    mine = bool(
        (
            league.current_platform_user_id
            and owner.platform_user_id == league.current_platform_user_id
        )
        or (
            league.my_platform_roster_id
            and owner.platform_roster_id == league.my_platform_roster_id
        )
    )
    return LiveLeaguePlayerStatus(
        platform_league_id=league.platform_league_id,
        league_name=league.name or league.platform_league_id,
        status=MINE if mine else OTHER,
        platform_roster_id=owner.platform_roster_id,
        platform_user_id=owner.platform_user_id,
        owner_name=manager_names.get(owner.platform_user_id or ""),
        roster_slot=_roster_slot(owner, player_id),
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


def _roster_player_ids(roster: Roster) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(value)
            for value in (
                *roster.players,
                *roster.starters,
                *roster.reserve,
                *roster.taxi,
            )
            if value not in (None, "", "0")
        )
    )


def _roster_slot(roster: Roster, player_id: str) -> str:
    if player_id in roster.reserve:
        return RESERVE
    if player_id in roster.taxi:
        return TAXI
    if player_id in roster.starters:
        return STARTER
    return BENCH
