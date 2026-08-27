from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .models import FantasyLeagueState, Roster
from .roster_health import (
    DIRECT_POSITIONS,
    FLEX_ELIGIBLE,
    FLEX_SLOTS,
    QUESTIONABLE_STATUSES,
    SERIOUS_STATUSES,
)
from .sleeper import SleeperTrendingPlayer


HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"


@dataclass(frozen=True)
class TeamNeed:
    position: str
    level: str
    reason: str


@dataclass(frozen=True)
class TeamTarget:
    sleeper_player_id: str
    player_name: str
    position: str
    nfl_team: str
    status: str
    need_level: str
    trend_count: int


@dataclass(frozen=True)
class LeagueTeamProfile:
    roster_id: str
    team_name: str
    record: str
    points_for: float
    roster_size: int
    starter_slots: int
    filled_starter_slots: int
    open_starter_slots: int
    position_counts: Mapping[str, int]
    serious_status_count: int
    questionable_status_count: int
    needs: tuple[TeamNeed, ...]
    targets: tuple[TeamTarget, ...]


_LEVEL_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}


def build_league_team_profile(
    league: FantasyLeagueState,
    roster_id: str,
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    trends: Iterable[SleeperTrendingPlayer] = (),
    target_limit: int = 25,
) -> LeagueTeamProfile:
    if isinstance(target_limit, bool) or not isinstance(target_limit, int):
        raise ValueError("target_limit must be an integer")
    if not 1 <= target_limit <= 100:
        raise ValueError("target_limit must be from 1 to 100")

    normalized_roster_id = str(roster_id or "").strip()
    if not normalized_roster_id:
        raise ValueError("roster_id is required")

    roster = next(
        (
            row
            for row in league.rosters
            if row.platform_roster_id == normalized_roster_id
        ),
        None,
    )
    if roster is None:
        raise ValueError("roster_id was not found in this league")

    manager_names = {
        manager.platform_user_id: (
            manager.team_name
            or manager.display_name
            or manager.platform_user_id
        )
        for manager in league.managers
    }
    team_name = manager_names.get(
        roster.platform_user_id or "",
        f"Roster {roster.platform_roster_id}",
    )

    player_ids = _all_roster_player_ids(roster)
    positions: Counter[str] = Counter()
    serious_by_position: Counter[str] = Counter()
    serious_count = 0
    questionable_count = 0

    for player_id in player_ids:
        player = player_catalog.get(player_id) or {}
        position = str(player.get("position") or "").strip().upper()
        if position:
            positions[position] += 1
        status = _status(player)
        normalized_status = status.casefold()
        if normalized_status in SERIOUS_STATUSES:
            serious_count += 1
            if position:
                serious_by_position[position] += 1
        elif normalized_status in QUESTIONABLE_STATUSES:
            questionable_count += 1

    starter_slots = len(league.rules.starter_positions)
    filled_starters = len(
        tuple(
            value
            for value in roster.starters
            if str(value or "").strip() not in {"", "0"}
        )
    )
    open_starters = max(0, starter_slots - filled_starters)

    needs = _build_needs(
        league,
        positions=positions,
        serious_by_position=serious_by_position,
        open_starters=open_starters,
    )
    targets = _build_targets(
        league,
        player_catalog,
        needs,
        trends=trends,
        limit=target_limit,
    )

    return LeagueTeamProfile(
        roster_id=roster.platform_roster_id,
        team_name=team_name,
        record=_record(roster),
        points_for=_points_for(roster),
        roster_size=len(player_ids),
        starter_slots=starter_slots,
        filled_starter_slots=filled_starters,
        open_starter_slots=open_starters,
        position_counts=dict(sorted(positions.items())),
        serious_status_count=serious_count,
        questionable_status_count=questionable_count,
        needs=needs,
        targets=targets,
    )


def _build_needs(
    league: FantasyLeagueState,
    *,
    positions: Counter[str],
    serious_by_position: Counter[str],
    open_starters: int,
) -> tuple[TeamNeed, ...]:
    rows: list[TeamNeed] = []
    direct_requirements = Counter(
        slot
        for slot in league.rules.starter_positions
        if slot in DIRECT_POSITIONS
    )

    for position, required in sorted(direct_requirements.items()):
        actual = positions.get(position, 0)
        serious = serious_by_position.get(position, 0)
        healthyish = max(0, actual - serious)
        if actual < required:
            rows.append(
                TeamNeed(
                    position=position,
                    level=HIGH,
                    reason=f"Roster has {actual} {position}, below {required} direct starter requirement.",
                )
            )
        elif healthyish < required:
            rows.append(
                TeamNeed(
                    position=position,
                    level=HIGH,
                    reason=f"Serious player status leaves fewer than {required} usable {position} for direct starter demand.",
                )
            )
        elif actual == required and position not in {"K", "DEF"}:
            rows.append(
                TeamNeed(
                    position=position,
                    level=MEDIUM,
                    reason=f"Exactly {required} {position} rostered for {required} direct starter slot{'s' if required != 1 else ''}; no bench cushion.",
                )
            )
        elif serious and actual <= required + 1:
            rows.append(
                TeamNeed(
                    position=position,
                    level=MEDIUM,
                    reason=f"{serious} {position} carries a serious status with limited depth behind the starter requirement.",
                )
            )

    flex_slots = sum(
        1
        for slot in league.rules.starter_positions
        if slot in FLEX_SLOTS
    )
    direct_flex_demand = sum(
        direct_requirements.get(position, 0)
        for position in FLEX_ELIGIBLE
    )
    flex_count = sum(positions.get(position, 0) for position in FLEX_ELIGIBLE)
    minimum_flex = direct_flex_demand + flex_slots
    if minimum_flex and flex_count <= minimum_flex:
        level = HIGH if flex_count < minimum_flex else MEDIUM
        rows.append(
            TeamNeed(
                position="RB/WR/TE",
                level=level,
                reason=(
                    "Flex-eligible depth is "
                    + ("below" if flex_count < minimum_flex else "exactly at")
                    + " the minimum RB/WR/TE starter demand."
                ),
            )
        )

    if open_starters and not rows:
        rows.append(
            TeamNeed(
                position="ANY",
                level=MEDIUM,
                reason=f"{open_starters} starter slot{'s are' if open_starters != 1 else ' is'} currently unfilled.",
            )
        )

    unique: dict[tuple[str, str], TeamNeed] = {}
    for row in rows:
        unique[(row.position, row.reason)] = row
    result = tuple(
        sorted(
            unique.values(),
            key=lambda row: (
                _LEVEL_ORDER.get(row.level, 99),
                row.position,
                row.reason,
            ),
        )
    )
    return result


def _build_targets(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
    needs: tuple[TeamNeed, ...],
    *,
    trends: Iterable[SleeperTrendingPlayer],
    limit: int,
) -> tuple[TeamTarget, ...]:
    if not league.ownership_ready or not needs:
        return ()

    rostered = {
        player_id
        for roster in league.rosters
        for player_id in _all_roster_player_ids(roster)
    }
    trend_counts = {
        str(row.player_id): max(0, int(row.count))
        for row in trends
        if str(row.player_id or "").strip()
    }

    need_levels: dict[str, str] = {}
    broad_flex_level: str | None = None
    any_level: str | None = None
    for need in needs:
        if need.position == "RB/WR/TE":
            broad_flex_level = _higher_level(broad_flex_level, need.level)
        elif need.position == "ANY":
            any_level = _higher_level(any_level, need.level)
        else:
            need_levels[need.position] = _higher_level(
                need_levels.get(need.position),
                need.level,
            )

    rows: list[TeamTarget] = []
    for raw_player_id, raw_player in player_catalog.items():
        player_id = str(raw_player_id or "").strip()
        if not player_id or player_id in rostered:
            continue
        if not isinstance(raw_player, Mapping) or raw_player.get("active") is False:
            continue

        position = str(raw_player.get("position") or "").strip().upper()
        if not position:
            continue
        need_level = need_levels.get(position)
        if need_level is None and broad_flex_level and position in FLEX_ELIGIBLE:
            need_level = broad_flex_level
        if need_level is None:
            need_level = any_level
        if need_level is None:
            continue

        status = _status(raw_player)
        normalized_status = status.casefold()
        if normalized_status in SERIOUS_STATUSES or normalized_status in {
            "retired",
            "inactive",
        }:
            continue

        rows.append(
            TeamTarget(
                sleeper_player_id=player_id,
                player_name=_player_name(raw_player, player_id),
                position=position,
                nfl_team=str(raw_player.get("team") or "FA").strip().upper() or "FA",
                status=status.replace("_", " ").title(),
                need_level=need_level,
                trend_count=trend_counts.get(player_id, 0),
            )
        )

    rows.sort(
        key=lambda row: (
            _LEVEL_ORDER.get(row.need_level, 99),
            -row.trend_count,
            1 if row.status.casefold() in QUESTIONABLE_STATUSES else 0,
            row.position,
            row.player_name.casefold(),
            row.sleeper_player_id,
        )
    )
    return tuple(rows[:limit])


def _higher_level(current: str | None, candidate: str) -> str:
    if current is None:
        return candidate
    return (
        candidate
        if _LEVEL_ORDER.get(candidate, 99) < _LEVEL_ORDER.get(current, 99)
        else current
    )


def _all_roster_player_ids(roster: Roster) -> tuple[str, ...]:
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


def _status(player: Mapping[str, Any]) -> str:
    return (
        str(player.get("injury_status") or "").strip()
        or str(player.get("status") or "").strip()
        or "Active"
    )


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
