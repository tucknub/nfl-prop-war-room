from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .models import FantasyLeagueState
from .team_explorer import HIGH, LOW, MEDIUM, build_league_team_profile


@dataclass(frozen=True)
class PlayerMarketTeamFit:
    roster_id: str
    team_name: str
    fit_level: str
    reason: str
    owns_player: bool = False


@dataclass(frozen=True)
class PlayerMarketMap:
    sleeper_player_id: str
    player_name: str
    positions: tuple[str, ...]
    nfl_team: str
    status: str
    available: bool
    owner_team: str | None
    team_fits: tuple[PlayerMarketTeamFit, ...]

    @property
    def high_fit_count(self) -> int:
        return sum(1 for row in self.team_fits if row.fit_level == HIGH)

    @property
    def medium_fit_count(self) -> int:
        return sum(1 for row in self.team_fits if row.fit_level == MEDIUM)


_LEVEL_ORDER = {
    HIGH: 0,
    MEDIUM: 1,
    LOW: 2,
}


def build_player_market_map(
    league: FantasyLeagueState,
    sleeper_player_id: str,
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> PlayerMarketMap:
    player_id = str(sleeper_player_id or "").strip()
    if not player_id:
        raise ValueError("sleeper_player_id is required")

    player = player_catalog.get(player_id)
    if not isinstance(player, Mapping):
        raise ValueError("player was not found in the Sleeper catalog")

    positions = _fantasy_positions(player)
    if not positions:
        raise ValueError("player has no fantasy position")

    owner_roster_id: str | None = None
    owner_team: str | None = None
    manager_names = {
        manager.platform_user_id: (
            manager.team_name
            or manager.display_name
            or manager.platform_user_id
        )
        for manager in league.managers
    }

    for roster in league.rosters:
        if player_id not in _roster_player_ids(roster):
            continue
        if owner_roster_id is not None and owner_roster_id != roster.platform_roster_id:
            raise ValueError("player appears on multiple rosters")
        owner_roster_id = roster.platform_roster_id
        owner_team = manager_names.get(
            roster.platform_user_id or "",
            f"Roster {roster.platform_roster_id}",
        )

    if owner_roster_id is None and not league.ownership_ready:
        raise ValueError(
            "Sleeper ownership is not ready; player availability is unsafe"
        )

    rows: list[PlayerMarketTeamFit] = []
    for roster in league.rosters:
        team_name = manager_names.get(
            roster.platform_user_id or "",
            f"Roster {roster.platform_roster_id}",
        )
        if roster.platform_roster_id == owner_roster_id:
            rows.append(
                PlayerMarketTeamFit(
                    roster_id=roster.platform_roster_id,
                    team_name=team_name,
                    fit_level=LOW,
                    reason="Current owner",
                    owns_player=True,
                )
            )
            continue

        profile = build_league_team_profile(
            league,
            roster.platform_roster_id,
            player_catalog,
            trends=(),
        )
        level, reason = _fit_from_needs(profile.needs, positions)
        rows.append(
            PlayerMarketTeamFit(
                roster_id=roster.platform_roster_id,
                team_name=team_name,
                fit_level=level,
                reason=reason,
                owns_player=False,
            )
        )

    rows.sort(
        key=lambda row: (
            3 if row.owns_player else _LEVEL_ORDER.get(row.fit_level, 99),
            row.team_name.casefold(),
            row.roster_id,
        )
    )

    return PlayerMarketMap(
        sleeper_player_id=player_id,
        player_name=_player_name(player, player_id),
        positions=positions,
        nfl_team=str(player.get("team") or "FA").strip().upper() or "FA",
        status=_status(player).replace("_", " ").title(),
        available=owner_roster_id is None,
        owner_team=owner_team,
        team_fits=tuple(rows),
    )


def _fit_from_needs(needs, positions: tuple[str, ...]) -> tuple[str, str]:
    strongest_level = LOW
    reasons: list[str] = []

    for need in needs:
        matches = False
        if need.position in positions:
            matches = True
        elif need.position == "RB/WR/TE" and any(
            position in {"RB", "WR", "TE"}
            for position in positions
        ):
            matches = True
        elif need.position == "ANY":
            matches = True

        if not matches:
            continue

        if _LEVEL_ORDER.get(need.level, 99) < _LEVEL_ORDER.get(strongest_level, 99):
            strongest_level = need.level
        reasons.append(need.reason)

    if reasons:
        return strongest_level, " | ".join(dict.fromkeys(reasons))
    return LOW, "No obvious structural need for this player's position."


def _roster_player_ids(roster) -> tuple[str, ...]:
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
