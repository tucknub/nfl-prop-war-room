from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .league_needs import ONE_WAY, TWO_WAY, build_league_needs_board
from .models import FantasyLeagueState, Roster
from .roster_health import QUESTIONABLE_STATUSES, SERIOUS_STATUSES


@dataclass(frozen=True)
class TradeCandidatePlayer:
    sleeper_player_id: str
    name: str
    position: str
    nfl_team: str
    roster_slot: str
    status: str

    @property
    def serious_status(self) -> bool:
        return self.status.casefold() in SERIOUS_STATUSES

    @property
    def questionable_status(self) -> bool:
        return self.status.casefold() in QUESTIONABLE_STATUSES


@dataclass(frozen=True)
class TradeCandidateMatch:
    partner_roster_id: str
    partner_team_name: str
    fit_signal: str
    players_i_could_target: tuple[TradeCandidatePlayer, ...]
    my_players_they_could_target: tuple[TradeCandidatePlayer, ...]
    positions_i_need: tuple[str, ...]
    positions_they_need: tuple[str, ...]

    @property
    def two_way(self) -> bool:
        return self.fit_signal == TWO_WAY


@dataclass(frozen=True)
class TradeCandidateBoard:
    matches: tuple[TradeCandidateMatch, ...]

    @property
    def two_way_count(self) -> int:
        return sum(1 for row in self.matches if row.two_way)


_SLOT_ORDER = {
    "Bench": 0,
    "Taxi": 1,
    "Starter": 2,
    "IR": 3,
}


def build_trade_candidate_board(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    per_side_limit: int = 8,
) -> TradeCandidateBoard:
    if isinstance(per_side_limit, bool) or not isinstance(per_side_limit, int):
        raise ValueError("per_side_limit must be an integer")
    if not 1 <= per_side_limit <= 25:
        raise ValueError("per_side_limit must be from 1 to 25")

    my_roster = _my_roster(league)
    if my_roster is None or not _roster_player_ids(my_roster):
        return TradeCandidateBoard(matches=())

    needs_board = build_league_needs_board(league, player_catalog)
    roster_by_id = {
        roster.platform_roster_id: roster
        for roster in league.rosters
    }

    matches: list[TradeCandidateMatch] = []
    for fit in needs_board.trade_fits:
        partner = roster_by_id.get(fit.roster_id)
        if partner is None:
            continue

        theirs = _players_for_positions(
            partner,
            set(fit.they_can_help_me_at),
            player_catalog,
            limit=per_side_limit,
        )
        mine = _players_for_positions(
            my_roster,
            set(fit.i_can_help_them_at),
            player_catalog,
            limit=per_side_limit,
        )
        if not theirs and not mine:
            continue

        matches.append(
            TradeCandidateMatch(
                partner_roster_id=fit.roster_id,
                partner_team_name=fit.team_name,
                fit_signal=fit.signal,
                players_i_could_target=theirs,
                my_players_they_could_target=mine,
                positions_i_need=fit.they_can_help_me_at,
                positions_they_need=fit.i_can_help_them_at,
            )
        )

    matches.sort(
        key=lambda row: (
            0 if row.fit_signal == TWO_WAY else 1,
            -len(row.players_i_could_target),
            -len(row.my_players_they_could_target),
            row.partner_team_name.casefold(),
            row.partner_roster_id,
        )
    )
    return TradeCandidateBoard(matches=tuple(matches))


def _players_for_positions(
    roster: Roster,
    positions: set[str],
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[TradeCandidatePlayer, ...]:
    if not positions:
        return ()

    rows: list[TradeCandidatePlayer] = []
    for player_id in _roster_player_ids(roster):
        player = player_catalog.get(player_id) or {}
        position = str(player.get("position") or "").strip().upper()
        if position not in positions:
            continue
        raw_status = _status(player)
        rows.append(
            TradeCandidatePlayer(
                sleeper_player_id=player_id,
                name=_player_name(player, player_id),
                position=position,
                nfl_team=str(player.get("team") or "FA").strip().upper() or "FA",
                roster_slot=_roster_slot(roster, player_id),
                status=raw_status.replace("_", " ").title(),
            )
        )

    rows.sort(
        key=lambda row: (
            1 if row.serious_status else 0,
            1 if row.questionable_status else 0,
            _SLOT_ORDER.get(row.roster_slot, 99),
            row.name.casefold(),
            row.sleeper_player_id,
        )
    )
    return tuple(rows[:limit])


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
            str(value).strip()
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


def _status(player: Mapping[str, Any]) -> str:
    return (
        str(player.get("injury_status") or "").strip()
        or str(player.get("status") or "").strip()
        or "Active"
    )


def _player_name(player: Mapping[str, Any], player_id: str) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id
