from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import FantasyLeagueState, Roster


@dataclass(frozen=True)
class PlayerExposureLeague:
    platform_league_id: str
    league_name: str
    roster_slot: str


@dataclass(frozen=True)
class PlayerExposure:
    sleeper_player_id: str
    leagues: tuple[PlayerExposureLeague, ...]

    @property
    def league_count(self) -> int:
        return len(self.leagues)

    @property
    def starter_count(self) -> int:
        return sum(1 for row in self.leagues if row.roster_slot == "Starter")

    @property
    def bench_count(self) -> int:
        return sum(1 for row in self.leagues if row.roster_slot == "Bench")

    @property
    def reserve_count(self) -> int:
        return sum(1 for row in self.leagues if row.roster_slot == "IR")

    @property
    def taxi_count(self) -> int:
        return sum(1 for row in self.leagues if row.roster_slot == "Taxi")

    @property
    def multi_league(self) -> bool:
        return self.league_count > 1


@dataclass(frozen=True)
class PlayerExposureIndex:
    players: tuple[PlayerExposure, ...]

    @property
    def distinct_player_count(self) -> int:
        return len(self.players)

    @property
    def multi_league_player_count(self) -> int:
        return sum(1 for row in self.players if row.multi_league)

    @property
    def max_league_count(self) -> int:
        return max((row.league_count for row in self.players), default=0)

    @property
    def total_roster_slots(self) -> int:
        return sum(row.league_count for row in self.players)


def build_my_player_exposure(
    leagues: Iterable[FantasyLeagueState],
) -> PlayerExposureIndex:
    by_player: dict[str, list[PlayerExposureLeague]] = {}

    for league in tuple(leagues):
        my_roster = _my_roster(league)
        if my_roster is None:
            continue

        for player_id in _roster_player_ids(my_roster):
            by_player.setdefault(player_id, []).append(
                PlayerExposureLeague(
                    platform_league_id=league.platform_league_id,
                    league_name=league.name or league.platform_league_id,
                    roster_slot=_roster_slot(my_roster, player_id),
                )
            )

    players = [
        PlayerExposure(
            sleeper_player_id=player_id,
            leagues=tuple(rows),
        )
        for player_id, rows in by_player.items()
    ]
    players.sort(
        key=lambda row: (
            -row.league_count,
            -row.starter_count,
            row.sleeper_player_id,
        )
    )
    return PlayerExposureIndex(players=tuple(players))


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
            if str(value or "").strip() not in {"", "0"}
        )
    )


def _roster_slot(roster: Roster, player_id: str) -> str:
    if player_id in roster.reserve:
        return "IR"
    if player_id in roster.taxi:
        return "Taxi"
    if player_id in roster.starters:
        return "Starter"
    return "Bench"
