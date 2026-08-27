from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .live_ownership import lookup_live_sleeper_player
from .models import FantasyLeagueState


FANTASY_POSITIONS = ("QB", "RB", "WR", "TE", "K", "DEF")
_POSITION_ORDER = {position: index for index, position in enumerate(FANTASY_POSITIONS)}
_EXCLUDED_STATUSES = {"retired"}


@dataclass(frozen=True)
class LiveFreeAgent:
    sleeper_player_id: str
    name: str
    position: str
    nfl_team: str
    status: str
    mine_elsewhere: tuple[str, ...] = ()

    @property
    def familiar(self) -> bool:
        return bool(self.mine_elsewhere)


def find_live_free_agents(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    all_leagues: Iterable[FantasyLeagueState] = (),
    query: str = "",
    position: str | None = None,
    mine_elsewhere_only: bool = False,
    limit: int = 100,
) -> tuple[LiveFreeAgent, ...]:
    """Return factual live free agents from a normalized Sleeper league.

    Absence from rosters becomes available only when Sleeper ownership is
    initialized for the selected league. This intentionally provides no player
    ranking or waiver recommendation score.
    """

    if not league.ownership_ready:
        raise ValueError(
            "Sleeper ownership is not ready; free-agent availability is unsafe"
        )
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > 500:
        raise ValueError("limit must be an integer from 1 to 500")

    selected_position = str(position or "").strip().upper()
    if selected_position in {"", "ALL"}:
        selected_position = ""
    elif selected_position not in FANTASY_POSITIONS:
        raise ValueError("position must be a supported fantasy position")

    normalized_query = str(query or "").strip().casefold()
    league_rows = tuple(all_leagues)

    rostered = {
        str(player_id)
        for roster in league.rosters
        for player_id in (
            *roster.players,
            *roster.starters,
            *roster.reserve,
            *roster.taxi,
        )
        if str(player_id or "").strip() not in {"", "0"}
    }

    rows: list[LiveFreeAgent] = []
    for raw_player_id, raw_player in player_catalog.items():
        player_id = str(raw_player_id or "").strip()
        if not player_id or player_id in rostered:
            continue
        if not isinstance(raw_player, Mapping):
            continue

        player_position = str(raw_player.get("position") or "").strip().upper()
        if player_position not in FANTASY_POSITIONS:
            continue
        if selected_position and player_position != selected_position:
            continue

        if raw_player.get("active") is False:
            continue
        raw_status = (
            str(raw_player.get("injury_status") or "").strip()
            or str(raw_player.get("status") or "").strip()
            or "Active"
        )
        if raw_status.casefold() in _EXCLUDED_STATUSES:
            continue

        name = _player_name(raw_player, player_id)
        if normalized_query and normalized_query not in name.casefold():
            continue

        mine_elsewhere: tuple[str, ...] = ()
        if league_rows:
            cross = lookup_live_sleeper_player(league_rows, player_id)
            mine_elsewhere = tuple(
                league_name
                for league_name in cross.mine_in
                if league_name != (league.name or league.platform_league_id)
            )

        if mine_elsewhere_only and not mine_elsewhere:
            continue

        rows.append(
            LiveFreeAgent(
                sleeper_player_id=player_id,
                name=name,
                position=player_position,
                nfl_team=str(raw_player.get("team") or "FA").strip().upper() or "FA",
                status=raw_status.replace("_", " ").title(),
                mine_elsewhere=mine_elsewhere,
            )
        )

    rows.sort(
        key=lambda row: (
            0 if row.mine_elsewhere else 1,
            _POSITION_ORDER.get(row.position, 99),
            row.name.casefold(),
            row.sleeper_player_id,
        )
    )
    return tuple(rows[:limit])


def _player_name(player: Mapping[str, Any], player_id: str) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id
