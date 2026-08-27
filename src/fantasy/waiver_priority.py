from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .market_fantasy import MarketFantasyBaseline, build_market_fantasy_baseline
from .models import FantasyLeagueState
from .waiver_fit import RosterNeedWaiverBoard, WaiverNeedMatch


MARKET_BACKED_ACTION = "MARKET_BACKED_ACTION"
ACTION_FIT = "ACTION_FIT"
MARKET_BACKED_WATCH = "MARKET_BACKED_WATCH"
WATCH_FIT = "WATCH_FIT"

_TIER_ORDER = {
    MARKET_BACKED_ACTION: 0,
    ACTION_FIT: 1,
    MARKET_BACKED_WATCH: 2,
    WATCH_FIT: 3,
}


@dataclass(frozen=True)
class WaiverPriorityCandidate:
    sleeper_player_id: str
    player_name: str
    position: str
    nfl_team: str
    status: str
    priority_tier: str
    action_slots: tuple[str, ...]
    watch_slots: tuple[str, ...]
    market_fantasy_points: float | None
    market_coverage: str | None
    market_component_count: int
    trend_count: int
    mine_elsewhere: tuple[str, ...]

    @property
    def market_backed(self) -> bool:
        return self.priority_tier in {
            MARKET_BACKED_ACTION,
            MARKET_BACKED_WATCH,
        }

    @property
    def urgent(self) -> bool:
        return bool(self.action_slots)

    @property
    def familiar(self) -> bool:
        return bool(self.mine_elsewhere)


@dataclass(frozen=True)
class WaiverPriorityBoard:
    candidates: tuple[WaiverPriorityCandidate, ...]

    @property
    def market_backed_count(self) -> int:
        return sum(1 for row in self.candidates if row.market_backed)

    @property
    def urgent_count(self) -> int:
        return sum(1 for row in self.candidates if row.urgent)


def build_market_waiver_priority_board(
    league: FantasyLeagueState,
    need_board: RosterNeedWaiverBoard,
    player_catalog: Mapping[str, Mapping[str, Any]],
    prop_rows: Iterable[Mapping[str, Any]],
    *,
    limit: int = 30,
) -> WaiverPriorityBoard:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 to 100")

    prop_rows = tuple(prop_rows)
    rows: list[WaiverPriorityCandidate] = []
    for match in need_board.matches:
        player = player_catalog.get(match.sleeper_player_id) or {}
        position = str(player.get("position") or match.position or "").strip().upper()
        baseline = build_market_fantasy_baseline(
            match.player_name,
            position,
            league.rules.scoring_settings,
            prop_rows,
        )
        usable_baseline = _usable_baseline(baseline)

        if match.action_slots:
            tier = (
                MARKET_BACKED_ACTION
                if usable_baseline is not None
                else ACTION_FIT
            )
        else:
            tier = (
                MARKET_BACKED_WATCH
                if usable_baseline is not None
                else WATCH_FIT
            )

        rows.append(
            WaiverPriorityCandidate(
                sleeper_player_id=match.sleeper_player_id,
                player_name=match.player_name,
                position=match.position,
                nfl_team=match.nfl_team,
                status=match.status,
                priority_tier=tier,
                action_slots=match.action_slots,
                watch_slots=match.watch_slots,
                market_fantasy_points=(
                    usable_baseline.fantasy_points
                    if usable_baseline is not None
                    else None
                ),
                market_coverage=(
                    usable_baseline.coverage_status
                    if usable_baseline is not None
                    else (
                        baseline.coverage_status
                        if baseline is not None
                        else None
                    )
                ),
                market_component_count=(
                    baseline.component_count if baseline is not None else 0
                ),
                trend_count=match.trend_count,
                mine_elsewhere=match.mine_elsewhere,
            )
        )

    rows.sort(key=_priority_sort_key)
    return WaiverPriorityBoard(candidates=tuple(rows[:limit]))


def _usable_baseline(
    baseline: MarketFantasyBaseline | None,
) -> MarketFantasyBaseline | None:
    if baseline is None:
        return None
    if baseline.coverage_status not in {"FULL", "PARTIAL"}:
        return None
    return baseline


def _priority_sort_key(row: WaiverPriorityCandidate) -> tuple:
    return (
        _TIER_ORDER.get(row.priority_tier, 99),
        -len(row.action_slots),
        -(
            row.market_fantasy_points
            if row.market_fantasy_points is not None
            else -999.0
        ),
        0 if row.familiar else 1,
        -row.trend_count,
        row.player_name.casefold(),
        row.sleeper_player_id,
    )


def priority_label(tier: str) -> str:
    return {
        MARKET_BACKED_ACTION: "Investigate first · market-backed Action fit",
        ACTION_FIT: "Investigate · Action fit",
        MARKET_BACKED_WATCH: "Monitor first · market-backed Watch fit",
        WATCH_FIT: "Monitor · Watch fit",
    }.get(tier, str(tier).replace("_", " ").title())
