from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .lineup_check import (
    NEEDS_ACTION,
    WATCH,
    LineupCheck,
    eligible_positions_for_slot,
    positions_eligible_for_slot,
)
from .models import FantasyLeagueState, Roster
from .roster_health import QUESTIONABLE_STATUSES, SERIOUS_STATUSES
from .sleeper import SleeperTrendingPlayer


@dataclass(frozen=True)
class RosterNeed:
    slot_index: int
    slot: str
    label: str
    level: str
    reason: str


@dataclass(frozen=True)
class WaiverNeedMatch:
    sleeper_player_id: str
    player_name: str
    position: str
    nfl_team: str
    status: str
    action_slots: tuple[str, ...]
    watch_slots: tuple[str, ...]
    mine_elsewhere: tuple[str, ...]
    trend_count: int = 0

    @property
    def familiar(self) -> bool:
        return bool(self.mine_elsewhere)

    @property
    def questionable(self) -> bool:
        return self.status.casefold() in QUESTIONABLE_STATUSES

    @property
    def fit_count(self) -> int:
        return len(self.action_slots) + len(self.watch_slots)


@dataclass(frozen=True)
class RosterNeedWaiverBoard:
    needs: tuple[RosterNeed, ...]
    matches: tuple[WaiverNeedMatch, ...]

    @property
    def action_need_count(self) -> int:
        return sum(1 for row in self.needs if row.level == NEEDS_ACTION)

    @property
    def watch_need_count(self) -> int:
        return sum(1 for row in self.needs if row.level == WATCH)

    @property
    def familiar_match_count(self) -> int:
        return sum(1 for row in self.matches if row.familiar)

    @property
    def trending_match_count(self) -> int:
        return sum(1 for row in self.matches if row.trend_count > 0)


def build_roster_need_waiver_board(
    league: FantasyLeagueState,
    lineup: LineupCheck,
    player_catalog: Mapping[str, Mapping[str, Any]],
    *,
    all_leagues: Iterable[FantasyLeagueState] = (),
    trends: Iterable[SleeperTrendingPlayer] = (),
    limit: int = 75,
) -> RosterNeedWaiverBoard:
    if not league.ownership_ready:
        raise ValueError(
            "Sleeper ownership is not ready; waiver availability is unsafe"
        )
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("limit must be an integer from 1 to 200")

    needs = _lineup_needs(lineup)
    if not needs:
        return RosterNeedWaiverBoard(needs=(), matches=())

    selected_roster = _my_roster(league)
    if selected_roster is None:
        return RosterNeedWaiverBoard(needs=needs, matches=())

    selected_rostered = set(_all_roster_player_ids(selected_roster))
    elsewhere = _mine_elsewhere(
        all_leagues,
        selected_league_id=league.platform_league_id,
    )
    trend_counts = {
        str(row.player_id): int(row.count)
        for row in trends
        if str(row.player_id or "").strip()
    }

    rows: list[WaiverNeedMatch] = []
    for raw_player_id, raw_player in player_catalog.items():
        player_id = str(raw_player_id or "").strip()
        if not player_id or player_id in selected_rostered:
            continue
        if not isinstance(raw_player, Mapping):
            continue
        if raw_player.get("active") is False:
            continue

        positions = _fantasy_positions(raw_player)
        if not positions:
            continue

        action_slots = tuple(
            need.label
            for need in needs
            if need.level == NEEDS_ACTION
            and positions_eligible_for_slot(positions, need.slot)
        )
        watch_slots = tuple(
            need.label
            for need in needs
            if need.level == WATCH
            and positions_eligible_for_slot(positions, need.slot)
        )
        if not action_slots and not watch_slots:
            continue

        raw_status = (
            str(raw_player.get("injury_status") or "").strip()
            or str(raw_player.get("status") or "").strip()
            or "Active"
        )
        normalized_status = raw_status.casefold()
        if (
            normalized_status in SERIOUS_STATUSES
            or normalized_status in {"retired", "inactive"}
        ):
            continue

        rows.append(
            WaiverNeedMatch(
                sleeper_player_id=player_id,
                player_name=_player_name(raw_player, player_id),
                position=str(raw_player.get("position") or "—").strip().upper() or "—",
                nfl_team=str(raw_player.get("team") or "FA").strip().upper() or "FA",
                status=raw_status.replace("_", " ").title(),
                action_slots=action_slots,
                watch_slots=watch_slots,
                mine_elsewhere=elsewhere.get(player_id, ()),
                trend_count=max(0, trend_counts.get(player_id, 0)),
            )
        )

    rows.sort(
        key=lambda row: (
            -len(row.action_slots),
            0 if row.familiar else 1,
            -row.trend_count,
            1 if row.questionable else 0,
            row.player_name.casefold(),
            row.sleeper_player_id,
        )
    )
    return RosterNeedWaiverBoard(
        needs=needs,
        matches=tuple(rows[:limit]),
    )


def _lineup_needs(lineup: LineupCheck) -> tuple[RosterNeed, ...]:
    relevant = tuple(
        row
        for row in lineup.slots
        if row.state in {NEEDS_ACTION, WATCH}
    )
    totals = Counter(row.slot for row in relevant)
    seen: Counter[str] = Counter()
    rows: list[RosterNeed] = []
    for row in relevant:
        seen[row.slot] += 1
        label = (
            row.slot
            if totals[row.slot] == 1
            else f"{row.slot} {seen[row.slot]}"
        )
        rows.append(
            RosterNeed(
                slot_index=row.slot_index,
                slot=row.slot,
                label=label,
                level=row.state,
                reason=row.reason,
            )
        )
    return tuple(rows)


def _mine_elsewhere(
    leagues: Iterable[FantasyLeagueState],
    *,
    selected_league_id: str,
) -> Mapping[str, tuple[str, ...]]:
    by_player: dict[str, list[str]] = {}
    for league in leagues:
        if league.platform_league_id == selected_league_id:
            continue
        roster = _my_roster(league)
        if roster is None:
            continue
        league_name = league.name or league.platform_league_id
        for player_id in _all_roster_player_ids(roster):
            values = by_player.setdefault(player_id, [])
            if league_name not in values:
                values.append(league_name)
    return {
        player_id: tuple(names)
        for player_id, names in by_player.items()
    }


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


def _fantasy_positions(player: Mapping[str, Any]) -> tuple[str, ...]:
    raw = player.get("fantasy_positions")
    if isinstance(raw, (list, tuple, set)):
        positions = tuple(
            dict.fromkeys(
                str(value).strip().upper()
                for value in raw
                if str(value or "").strip()
            )
        )
        if positions:
            return positions
    position = str(player.get("position") or "").strip().upper()
    return (position,) if position else ()


def _player_name(player: Mapping[str, Any], player_id: str) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id
