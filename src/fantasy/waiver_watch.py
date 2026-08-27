from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .live_ownership import (
    AVAILABLE,
    MINE,
    OTHER,
    lookup_live_sleeper_player,
)
from .models import FantasyLeagueState
from .sleeper import SleeperTrendingPlayer


@dataclass(frozen=True)
class WaiverWatchCandidate:
    sleeper_player_id: str
    player_name: str
    position: str
    nfl_team: str
    trend_count: int
    selected_league_name: str
    mine_elsewhere: tuple[str, ...]
    owned_elsewhere: tuple[str, ...]
    injury_status: str | None = None


def build_sleeper_waiver_watch(
    leagues: Iterable[FantasyLeagueState],
    *,
    selected_league_id: str,
    trends: Iterable[SleeperTrendingPlayer],
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> tuple[WaiverWatchCandidate, ...]:
    league_rows = tuple(leagues)
    selected_id = str(selected_league_id or "").strip()
    if not selected_id:
        raise ValueError("selected_league_id is required")

    selected = next(
        (
            league
            for league in league_rows
            if league.platform_league_id == selected_id
        ),
        None,
    )
    if selected is None:
        raise ValueError("selected_league_id is not present in scanned leagues")

    rows: list[WaiverWatchCandidate] = []
    seen: set[str] = set()
    for trend in trends:
        player_id = str(trend.player_id or "").strip()
        if not player_id or player_id in seen:
            continue
        seen.add(player_id)

        ownership = lookup_live_sleeper_player(league_rows, player_id)
        selected_status = next(
            (
                row
                for row in ownership.statuses
                if row.platform_league_id == selected_id
            ),
            None,
        )
        if selected_status is None or selected_status.status != AVAILABLE:
            continue

        player = player_catalog.get(player_id) or {}
        name = _player_name(player, player_id)
        position = str(player.get("position") or "—").strip().upper() or "—"
        nfl_team = str(player.get("team") or "FA").strip().upper() or "FA"
        injury_status = str(
            player.get("injury_status") or player.get("status") or ""
        ).strip() or None

        mine_elsewhere = tuple(
            row.league_name
            for row in ownership.statuses
            if row.platform_league_id != selected_id and row.status == MINE
        )
        owned_elsewhere = tuple(
            row.league_name
            for row in ownership.statuses
            if row.platform_league_id != selected_id and row.status == OTHER
        )
        rows.append(
            WaiverWatchCandidate(
                sleeper_player_id=player_id,
                player_name=name,
                position=position,
                nfl_team=nfl_team,
                trend_count=trend.count,
                selected_league_name=selected.name or selected.platform_league_id,
                mine_elsewhere=mine_elsewhere,
                owned_elsewhere=owned_elsewhere,
                injury_status=injury_status,
            )
        )

    rows.sort(
        key=lambda row: (
            -row.trend_count,
            row.position,
            row.player_name.casefold(),
        )
    )
    return tuple(rows)


def _player_name(player: Mapping[str, Any], player_id: str) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id
