from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .live_ownership import (
    AVAILABLE,
    MINE,
    OTHER,
    UNKNOWN,
    lookup_live_sleeper_player,
)
from .models import FantasyLeagueState
from .player_market import build_player_market_map
from .sleeper import SleeperTrendingPlayer


@dataclass(frozen=True)
class PlayerLeagueOwnership:
    league_name: str
    status: str
    owner_name: str | None
    roster_slot: str | None


@dataclass(frozen=True)
class PlayerIntelligenceCard:
    sleeper_player_id: str
    player_name: str
    positions: tuple[str, ...]
    nfl_team: str
    status: str
    age: int | None
    years_exp: int | None
    depth_chart_order: int | None
    depth_chart_position: str | None
    selected_league_status: str
    selected_league_owner: str | None
    selected_league_slot: str | None
    my_league_count: int
    opponent_owned_league_count: int
    available_league_count: int
    unknown_league_count: int
    add_trend_count: int
    drop_trend_count: int
    high_fit_team_count: int
    medium_fit_team_count: int
    ownership: tuple[PlayerLeagueOwnership, ...]

    @property
    def trend_delta(self) -> int:
        return self.add_trend_count - self.drop_trend_count

    @property
    def is_available_here(self) -> bool:
        return self.selected_league_status == AVAILABLE


def build_player_intelligence_card(
    selected_league: FantasyLeagueState,
    all_leagues: Iterable[FantasyLeagueState],
    sleeper_player_id: str,
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    add_trends: Iterable[SleeperTrendingPlayer] = (),
    drop_trends: Iterable[SleeperTrendingPlayer] = (),
) -> PlayerIntelligenceCard:
    player_id = str(sleeper_player_id or "").strip()
    if not player_id:
        raise ValueError("sleeper_player_id is required")

    player = player_catalog.get(player_id)
    if not isinstance(player, Mapping):
        raise ValueError("player was not found in the Sleeper catalog")

    league_rows = tuple(all_leagues)
    if not league_rows:
        league_rows = (selected_league,)

    cross = lookup_live_sleeper_player(league_rows, player_id)
    selected = next(
        (
            row
            for row in cross.statuses
            if row.platform_league_id == selected_league.platform_league_id
        ),
        None,
    )
    if selected is None:
        selected = lookup_live_sleeper_player(
            (selected_league,),
            player_id,
        ).statuses[0]

    market = build_player_market_map(
        selected_league,
        player_id,
        player_catalog,
    )

    add_counts = {
        str(row.player_id): max(0, int(row.count))
        for row in add_trends
        if str(row.player_id or "").strip()
    }
    drop_counts = {
        str(row.player_id): max(0, int(row.count))
        for row in drop_trends
        if str(row.player_id or "").strip()
    }

    ownership = tuple(
        PlayerLeagueOwnership(
            league_name=row.league_name,
            status=row.status,
            owner_name=row.owner_name,
            roster_slot=row.roster_slot,
        )
        for row in cross.statuses
    )

    return PlayerIntelligenceCard(
        sleeper_player_id=player_id,
        player_name=_player_name(player, player_id),
        positions=_fantasy_positions(player),
        nfl_team=str(player.get("team") or "FA").strip().upper() or "FA",
        status=_status(player).replace("_", " ").title(),
        age=_optional_int(player.get("age")),
        years_exp=_optional_int(player.get("years_exp")),
        depth_chart_order=_optional_int(player.get("depth_chart_order")),
        depth_chart_position=_optional_text(player.get("depth_chart_position")),
        selected_league_status=selected.status,
        selected_league_owner=selected.owner_name,
        selected_league_slot=selected.roster_slot,
        my_league_count=sum(1 for row in cross.statuses if row.status == MINE),
        opponent_owned_league_count=sum(
            1 for row in cross.statuses if row.status == OTHER
        ),
        available_league_count=sum(
            1 for row in cross.statuses if row.status == AVAILABLE
        ),
        unknown_league_count=sum(
            1 for row in cross.statuses if row.status == UNKNOWN
        ),
        add_trend_count=add_counts.get(player_id, 0),
        drop_trend_count=drop_counts.get(player_id, 0),
        high_fit_team_count=market.high_fit_count,
        medium_fit_team_count=market.medium_fit_count,
        ownership=ownership,
    )


def _fantasy_positions(player: Mapping[str, Any]) -> tuple[str, ...]:
    raw = player.get("fantasy_positions")
    if isinstance(raw, (list, tuple, set)):
        values = tuple(
            dict.fromkeys(
                str(value).strip().upper()
                for value in raw
                if str(value or "").strip()
            )
        )
        if values:
            return values
    position = str(player.get("position") or "").strip().upper()
    return (position,) if position else ()


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


def _optional_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None
