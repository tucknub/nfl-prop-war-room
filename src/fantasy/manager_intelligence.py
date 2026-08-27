from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .league_needs import LeagueNeedsBoard, build_league_needs_board
from .models import FantasyLeagueState, LeagueTransaction, Roster
from .team_explorer import (
    HIGH,
    MEDIUM,
    LeagueTeamProfile,
    TeamNeed,
    TeamTarget,
    build_league_team_profile,
)
from .trade_candidates import (
    TradeCandidateBoard,
    TradeCandidatePlayer,
    build_trade_candidate_board,
)


@dataclass(frozen=True)
class ManagerDepthPlayer:
    sleeper_player_id: str
    name: str
    position: str
    nfl_team: str
    roster_slot: str
    status: str


@dataclass(frozen=True)
class ManagerTradeStartingPoint:
    i_give: TradeCandidatePlayer
    i_receive: TradeCandidatePlayer


@dataclass(frozen=True)
class ManagerBehaviorItem:
    transaction_id: str
    week: int | None
    kind: str
    summary: str
    timestamp_ms: int


@dataclass(frozen=True)
class ManagerIntelligence:
    roster_id: str
    team_name: str
    record: str
    points_for: float
    roster_size: int
    high_needs: tuple[TeamNeed, ...]
    medium_needs: tuple[TeamNeed, ...]
    depth_positions: tuple[str, ...]
    likely_shopping: tuple[str, ...]
    available_targets: tuple[TeamTarget, ...]
    movable_depth_players: tuple[ManagerDepthPlayer, ...]
    my_players_fit_them: tuple[TradeCandidatePlayer, ...]
    their_players_fit_me: tuple[TradeCandidatePlayer, ...]
    mutual_trade_starting_points: tuple[ManagerTradeStartingPoint, ...]
    trade_fit_signal: str | None


_SLOT_ORDER = {
    "Bench": 0,
    "Taxi": 1,
    "Starter": 2,
    "IR": 3,
}


def build_manager_intelligence(
    league: FantasyLeagueState,
    roster_id: str,
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    trends=(),
    team_profile: LeagueTeamProfile | None = None,
    needs_board: LeagueNeedsBoard | None = None,
    trade_board: TradeCandidateBoard | None = None,
    target_limit: int = 8,
    movable_limit: int = 8,
) -> ManagerIntelligence:
    normalized_roster_id = str(roster_id or "").strip()
    if not normalized_roster_id:
        raise ValueError("roster_id is required")
    if not 1 <= int(target_limit) <= 25:
        raise ValueError("target_limit must be from 1 to 25")
    if not 1 <= int(movable_limit) <= 25:
        raise ValueError("movable_limit must be from 1 to 25")

    profile = team_profile or build_league_team_profile(
        league,
        normalized_roster_id,
        player_catalog,
        trends=trends,
    )
    if profile.roster_id != normalized_roster_id:
        raise ValueError("team_profile does not match roster_id")

    board = needs_board or build_league_needs_board(league, player_catalog)
    trade_candidates = trade_board or build_trade_candidate_board(
        league,
        player_catalog,
    )

    needs_row = next(
        (row for row in board.rows if row.roster_id == normalized_roster_id),
        None,
    )
    depth_positions = tuple(needs_row.depth_positions) if needs_row else ()

    match = next(
        (
            row
            for row in trade_candidates.matches
            if row.partner_roster_id == normalized_roster_id
        ),
        None,
    )

    high_needs = tuple(need for need in profile.needs if need.level == HIGH)
    medium_needs = tuple(need for need in profile.needs if need.level == MEDIUM)
    likely_shopping = tuple(
        dict.fromkeys(
            need.position
            for need in (*high_needs, *medium_needs)
        )
    )

    roster = _roster(league, normalized_roster_id)
    movable = _depth_players(
        roster,
        set(depth_positions),
        player_catalog,
        limit=int(movable_limit),
    )

    my_fit: tuple[TradeCandidatePlayer, ...] = ()
    their_fit: tuple[TradeCandidatePlayer, ...] = ()
    starting_points: tuple[ManagerTradeStartingPoint, ...] = ()
    fit_signal: str | None = None
    if match is not None:
        my_fit = tuple(match.my_players_they_could_target)
        their_fit = tuple(match.players_i_could_target)
        fit_signal = match.fit_signal
        if match.two_way:
            starting_points = tuple(
                ManagerTradeStartingPoint(i_give=mine, i_receive=theirs)
                for mine, theirs in zip(my_fit[:3], their_fit[:3])
            )

    return ManagerIntelligence(
        roster_id=profile.roster_id,
        team_name=profile.team_name,
        record=profile.record,
        points_for=profile.points_for,
        roster_size=profile.roster_size,
        high_needs=high_needs,
        medium_needs=medium_needs,
        depth_positions=depth_positions,
        likely_shopping=likely_shopping,
        available_targets=tuple(profile.targets[: int(target_limit)]),
        movable_depth_players=movable,
        my_players_fit_them=my_fit,
        their_players_fit_me=their_fit,
        mutual_trade_starting_points=starting_points,
        trade_fit_signal=fit_signal,
    )


def build_manager_recent_behavior(
    league: FantasyLeagueState,
    roster_id: str,
    transactions: Iterable[LeagueTransaction],
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    limit: int = 8,
) -> tuple[ManagerBehaviorItem, ...]:
    normalized_roster_id = str(roster_id or "").strip()
    if not normalized_roster_id:
        raise ValueError("roster_id is required")
    if not 1 <= int(limit) <= 25:
        raise ValueError("limit must be from 1 to 25")
    _roster(league, normalized_roster_id)

    rows: list[ManagerBehaviorItem] = []
    for transaction in transactions:
        if not _transaction_involves_roster(transaction, normalized_roster_id):
            continue

        received = [
            _player_name(player_catalog.get(player_id) or {}, player_id)
            for player_id, target_roster in transaction.adds.items()
            if str(target_roster) == normalized_roster_id
        ]
        sent = [
            _player_name(player_catalog.get(player_id) or {}, player_id)
            for player_id, source_roster in transaction.drops.items()
            if str(source_roster) == normalized_roster_id
        ]

        kind = str(transaction.transaction_type or "transaction").replace("_", " ").title()
        pieces: list[str] = []
        if kind.casefold() == "trade":
            if received:
                pieces.append("Received " + ", ".join(received))
            if sent:
                pieces.append("Sent " + ", ".join(sent))
        else:
            if received:
                pieces.append("Added " + ", ".join(received))
            if sent:
                pieces.append("Dropped " + ", ".join(sent))

        if transaction.waiver_bid is not None and received:
            pieces.append("FAAB bid $" + str(transaction.waiver_bid))

        if not pieces:
            pieces.append(kind)

        rows.append(
            ManagerBehaviorItem(
                transaction_id=transaction.platform_transaction_id,
                week=transaction.week,
                kind=kind,
                summary=" · ".join(pieces),
                timestamp_ms=int(
                    transaction.status_updated_at_ms
                    or transaction.created_at_ms
                    or 0
                ),
            )
        )

    rows.sort(
        key=lambda row: (-row.timestamp_ms, row.transaction_id)
    )
    return tuple(rows[: int(limit)])


def _roster(league: FantasyLeagueState, roster_id: str) -> Roster:
    roster = next(
        (
            row
            for row in league.rosters
            if str(row.platform_roster_id) == str(roster_id)
        ),
        None,
    )
    if roster is None:
        raise ValueError("roster_id was not found in this league")
    return roster


def _depth_players(
    roster: Roster,
    depth_positions: set[str],
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    limit: int,
) -> tuple[ManagerDepthPlayer, ...]:
    if not depth_positions:
        return ()

    rows: list[ManagerDepthPlayer] = []
    for player_id in _roster_player_ids(roster):
        player = player_catalog.get(player_id) or {}
        position = str(player.get("position") or "").strip().upper()
        if position not in depth_positions:
            continue
        rows.append(
            ManagerDepthPlayer(
                sleeper_player_id=player_id,
                name=_player_name(player, player_id),
                position=position,
                nfl_team=str(player.get("team") or "FA").strip().upper() or "FA",
                roster_slot=_roster_slot(roster, player_id),
                status=_status(player).replace("_", " ").title(),
            )
        )

    rows.sort(
        key=lambda row: (
            _SLOT_ORDER.get(row.roster_slot, 99),
            row.position,
            row.name.casefold(),
            row.sleeper_player_id,
        )
    )
    return tuple(rows[:limit])


def _transaction_involves_roster(
    transaction: LeagueTransaction,
    roster_id: str,
) -> bool:
    involved = {
        str(value)
        for value in (
            *transaction.roster_ids,
            *transaction.consenter_roster_ids,
            *transaction.adds.values(),
            *transaction.drops.values(),
            *(
                transfer.sender_roster_id
                for transfer in transaction.faab_transfers
                if transfer.sender_roster_id
            ),
            *(
                transfer.receiver_roster_id
                for transfer in transaction.faab_transfers
                if transfer.receiver_roster_id
            ),
        )
        if value not in (None, "")
    }
    return str(roster_id) in involved


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


__all__ = [
    "ManagerBehaviorItem",
    "ManagerDepthPlayer",
    "ManagerIntelligence",
    "ManagerTradeStartingPoint",
    "build_manager_intelligence",
    "build_manager_recent_behavior",
]
