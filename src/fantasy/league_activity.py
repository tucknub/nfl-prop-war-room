from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .models import FantasyLeagueState, LeagueTransaction


@dataclass(frozen=True)
class LeagueActivityPlayer:
    player_id: str
    name: str
    position: str
    nfl_team: str
    roster_id: str
    team_name: str


@dataclass(frozen=True)
class LeagueActivityFaabTransfer:
    sender_team: str | None
    receiver_team: str | None
    amount: int | float | None


@dataclass(frozen=True)
class LeagueActivityTransaction:
    transaction_id: str
    transaction_type: str
    status: str
    week: int | None
    created_at_ms: int | None
    status_updated_at_ms: int | None
    teams: tuple[str, ...]
    adds: tuple[LeagueActivityPlayer, ...]
    drops: tuple[LeagueActivityPlayer, ...]
    waiver_bid: int | float | None
    faab_transfers: tuple[LeagueActivityFaabTransfer, ...]
    traded_pick_count: int

    @property
    def type_label(self) -> str:
        value = self.transaction_type.replace("_", " ").strip()
        return value.title() if value else "Unknown"

    @property
    def sort_timestamp_ms(self) -> int:
        return int(self.status_updated_at_ms or self.created_at_ms or 0)


@dataclass(frozen=True)
class LeagueActivityFeed:
    transactions: tuple[LeagueActivityTransaction, ...]

    @property
    def transaction_count(self) -> int:
        return len(self.transactions)

    @property
    def add_count(self) -> int:
        return sum(len(row.adds) for row in self.transactions)

    @property
    def drop_count(self) -> int:
        return sum(len(row.drops) for row in self.transactions)

    @property
    def trade_count(self) -> int:
        return sum(
            1
            for row in self.transactions
            if row.transaction_type.casefold() == "trade"
        )

    @property
    def waiver_count(self) -> int:
        return sum(
            1
            for row in self.transactions
            if row.transaction_type.casefold() == "waiver"
        )


def build_league_activity(
    league: FantasyLeagueState,
    transactions: Iterable[LeagueTransaction],
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> LeagueActivityFeed:
    roster_names = _roster_names(league)
    rows = [
        _activity_transaction(
            transaction,
            roster_names=roster_names,
            player_catalog=player_catalog,
        )
        for transaction in transactions
    ]
    rows.sort(
        key=lambda row: (
            -row.sort_timestamp_ms,
            row.transaction_id,
        )
    )
    return LeagueActivityFeed(transactions=tuple(rows))


def _activity_transaction(
    transaction: LeagueTransaction,
    *,
    roster_names: Mapping[str, str],
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> LeagueActivityTransaction:
    roster_ids = tuple(
        dict.fromkeys(
            (
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
        )
    )
    teams = tuple(
        roster_names.get(roster_id, f"Roster {roster_id}")
        for roster_id in roster_ids
        if roster_id
    )

    adds = tuple(
        _player_move(
            player_id,
            roster_id,
            roster_names=roster_names,
            player_catalog=player_catalog,
        )
        for player_id, roster_id in transaction.adds.items()
    )
    drops = tuple(
        _player_move(
            player_id,
            roster_id,
            roster_names=roster_names,
            player_catalog=player_catalog,
        )
        for player_id, roster_id in transaction.drops.items()
    )

    faab_transfers = tuple(
        LeagueActivityFaabTransfer(
            sender_team=(
                roster_names.get(
                    transfer.sender_roster_id,
                    f"Roster {transfer.sender_roster_id}",
                )
                if transfer.sender_roster_id
                else None
            ),
            receiver_team=(
                roster_names.get(
                    transfer.receiver_roster_id,
                    f"Roster {transfer.receiver_roster_id}",
                )
                if transfer.receiver_roster_id
                else None
            ),
            amount=transfer.amount,
        )
        for transfer in transaction.faab_transfers
    )

    return LeagueActivityTransaction(
        transaction_id=transaction.platform_transaction_id,
        transaction_type=transaction.transaction_type,
        status=transaction.status,
        week=transaction.week,
        created_at_ms=transaction.created_at_ms,
        status_updated_at_ms=transaction.status_updated_at_ms,
        teams=teams,
        adds=adds,
        drops=drops,
        waiver_bid=transaction.waiver_bid,
        faab_transfers=faab_transfers,
        traded_pick_count=len(transaction.traded_picks),
    )


def _roster_names(league: FantasyLeagueState) -> dict[str, str]:
    manager_names = {
        manager.platform_user_id: (
            manager.team_name
            or manager.display_name
            or manager.platform_user_id
        )
        for manager in league.managers
    }
    return {
        roster.platform_roster_id: manager_names.get(
            roster.platform_user_id or "",
            f"Roster {roster.platform_roster_id}",
        )
        for roster in league.rosters
    }


def _player_move(
    player_id: str,
    roster_id: str,
    *,
    roster_names: Mapping[str, str],
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> LeagueActivityPlayer:
    player = player_catalog.get(player_id) or {}
    return LeagueActivityPlayer(
        player_id=player_id,
        name=_player_name(player, player_id),
        position=str(player.get("position") or "—").strip().upper() or "—",
        nfl_team=str(player.get("team") or "FA").strip().upper() or "FA",
        roster_id=roster_id,
        team_name=roster_names.get(roster_id, f"Roster {roster_id}"),
    )


def _player_name(player: Mapping[str, Any], player_id: str) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id
