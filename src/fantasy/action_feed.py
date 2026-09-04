from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .lineup_check import NEEDS_ACTION, build_lineup_check
from .market_start_sit import FILL, SWAP, build_market_start_sit_board
from .market_waivers import HIGH, LOW, MEDIUM, build_market_ranked_waivers
from .models import FantasyLeagueState, LeagueTransaction, MatchupTeam
from .sleeper import SleeperTrendingPlayer


PRIORITY_HIGH = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW = "LOW"

LINEUP = "LINEUP"
WAIVER = "WAIVER"
TRADE = "TRADE"
HEALTH = "HEALTH"

_PRIORITY_SCORE = {
    PRIORITY_HIGH: 300.0,
    PRIORITY_MEDIUM: 200.0,
    PRIORITY_LOW: 100.0,
}
_TYPE_SCORE = {
    LINEUP: 40.0,
    WAIVER: 30.0,
    TRADE: 20.0,
    HEALTH: 10.0,
}

MIN_LOW_WAIVER_FEED_EDGE = 2.0


@dataclass(frozen=True)
class WeeklyActionItem:
    platform_league_id: str
    league_name: str
    priority: str
    action_type: str
    title: str
    action: str
    detail: str
    impact_points: float | None
    confidence: str
    score: float
    player_ids: tuple[str, ...] = ()
    partner_roster_id: str | None = None
    faab_range: str | None = None
    faab_target: str | None = None


@dataclass(frozen=True)
class WeeklyActionFeed:
    actions: tuple[WeeklyActionItem, ...]
    scanned_leagues: int
    drafted_leagues: int
    errors: tuple[str, ...]

    @property
    def high_count(self) -> int:
        return sum(1 for row in self.actions if row.priority == PRIORITY_HIGH)

    @property
    def medium_count(self) -> int:
        return sum(1 for row in self.actions if row.priority == PRIORITY_MEDIUM)

    @property
    def actionable_league_count(self) -> int:
        return len({row.platform_league_id for row in self.actions})


def build_weekly_action_feed(
    leagues: Iterable[FantasyLeagueState],
    player_catalog: Mapping[str, Mapping[str, Any]],
    prop_rows: Iterable[Mapping[str, Any]],
    *,
    current_week: int = 0,
    trends: Iterable[SleeperTrendingPlayer] = (),
    matchups_by_league: Mapping[str, MatchupTeam | None] | None = None,
    transactions_by_league: Mapping[str, Iterable[LeagueTransaction]] | None = None,
    limit: int = 30,
) -> WeeklyActionFeed:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 to 100")

    league_rows = tuple(leagues)
    prop_snapshot = tuple(dict(row) for row in prop_rows)
    trend_rows = tuple(trends)
    matchup_map = dict(matchups_by_league or {})
    transaction_map = dict(transactions_by_league or {})

    actions: list[WeeklyActionItem] = []
    errors: list[str] = []
    drafted = 0

    for league in league_rows:
        if (
            league.status == "pre_draft"
            or not league.ownership_ready
            or not league.my_platform_roster_id
        ):
            continue
        drafted += 1
        try:
            actions.extend(
                _league_actions(
                    league,
                    player_catalog,
                    prop_snapshot,
                    current_week=max(0, int(current_week or 0)),
                    trends=trend_rows,
                    matchup=matchup_map.get(league.platform_league_id),
                    transactions=tuple(
                        transaction_map.get(league.platform_league_id, ())
                    ),
                    all_leagues=league_rows,
                )
            )
        except Exception as exc:
            errors.append(
                f"{league.name or league.platform_league_id}: {exc}"
            )

    deduped: dict[tuple[Any, ...], WeeklyActionItem] = {}
    for row in actions:
        key = (
            row.platform_league_id,
            row.action_type,
            row.title,
            row.player_ids,
            row.partner_roster_id,
        )
        incumbent = deduped.get(key)
        if incumbent is None or row.score > incumbent.score:
            deduped[key] = row

    ranked = sorted(
        deduped.values(),
        key=lambda row: (
            -row.score,
            row.league_name.casefold(),
            row.title.casefold(),
        ),
    )
    return WeeklyActionFeed(
        actions=tuple(ranked[:limit]),
        scanned_leagues=len(league_rows),
        drafted_leagues=drafted,
        errors=tuple(errors),
    )


def _league_actions(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
    prop_rows: tuple[Mapping[str, Any], ...],
    *,
    current_week: int,
    trends: tuple[SleeperTrendingPlayer, ...],
    matchup: MatchupTeam | None,
    transactions: tuple[LeagueTransaction, ...],
    all_leagues: tuple[FantasyLeagueState, ...],
) -> list[WeeklyActionItem]:
    league_name = league.name or league.platform_league_id
    lineup = build_lineup_check(
        league,
        player_catalog,
        matchup=matchup,
    )
    if lineup is None:
        return []

    rows: list[WeeklyActionItem] = []
    resolved_action_slots: set[int] = set()

    start_sit = build_market_start_sit_board(
        lineup,
        league.rules.scoring_settings,
        player_catalog,
        prop_rows,
    )
    for advice in start_sit.slots:
        if advice.verdict == FILL and advice.best_bench is not None:
            resolved_action_slots.add(advice.slot_index)
            player = advice.best_bench
            rows.append(
                _item(
                    league,
                    priority=PRIORITY_HIGH,
                    action_type=LINEUP,
                    title=f"Fill open {advice.slot} with {player.name}",
                    action=f"Move {player.name} into {advice.slot}.",
                    detail=advice.reason,
                    impact_points=None,
                    confidence=_coverage_confidence(player.coverage),
                    player_ids=(player.player_id,),
                    bonus=12.0,
                )
            )
        elif (
            advice.verdict == SWAP
            and advice.best_bench is not None
            and advice.starter is not None
        ):
            edge = float(advice.edge_points or 0.0)
            priority = (
                PRIORITY_HIGH if edge >= 3.0 else PRIORITY_MEDIUM
            )
            rows.append(
                _item(
                    league,
                    priority=priority,
                    action_type=LINEUP,
                    title=(
                        f"Start {advice.best_bench.name} over "
                        f"{advice.starter.name}"
                    ),
                    action=f"Swap your {advice.slot} starter.",
                    detail=advice.reason,
                    impact_points=edge,
                    confidence=min(
                        _coverage_confidence(advice.best_bench.coverage),
                        _coverage_confidence(advice.starter.coverage),
                        key=_confidence_rank,
                    ),
                    player_ids=(
                        advice.best_bench.player_id,
                        advice.starter.player_id,
                    ),
                    bonus=10.0,
                )
            )

    market_waivers = build_market_ranked_waivers(
        league,
        lineup,
        player_catalog,
        prop_rows,
        all_leagues=all_leagues,
        trends=trends,
        limit=20,
    )
    for candidate in market_waivers.candidates[:4]:
        priority = {
            HIGH: PRIORITY_HIGH,
            MEDIUM: PRIORITY_MEDIUM,
            LOW: PRIORITY_LOW,
        }.get(candidate.need, PRIORITY_LOW)
        improvement = candidate.expected_lineup_improvement
        if not waiver_candidate_visible_in_feed(candidate):
            continue
        faab_range = None
        faab_target = None
        confidence = _coverage_confidence(candidate.coverage)

        rows.append(
            _item(
                league,
                priority=priority,
                action_type=WAIVER,
                title=f"Add {candidate.player_name}",
                action=(
                    f"Review {candidate.player_name} for "
                    f"{candidate.target_slot}."
                ),
                detail=candidate.reason,
                impact_points=improvement,
                confidence=confidence,
                player_ids=(candidate.sleeper_player_id,),
                faab_range=faab_range,
                faab_target=faab_target,
                bonus=(8.0 if candidate.need == HIGH else 4.0),
            )
        )

    for slot in lineup.slots:
        if not slot.needs_action or slot.slot_index in resolved_action_slots:
            continue
        matching_waiver = any(
            row.action_type == WAIVER
            and row.priority == PRIORITY_HIGH
            and slot.slot in row.action
            for row in rows
        )
        if matching_waiver:
            continue
        starter_name = slot.starter.name if slot.starter else "open slot"
        rows.append(
            _item(
                league,
                priority=PRIORITY_HIGH,
                action_type=HEALTH,
                title=f"Fix {slot.slot}: {starter_name}",
                action="Review this starter slot before kickoff.",
                detail=slot.reason,
                impact_points=None,
                confidence="HIGH",
                player_ids=(
                    (slot.starter.player_id,)
                    if slot.starter is not None
                    else ()
                ),
            )
        )

    return rows


def waiver_candidate_visible_in_feed(candidate: Any) -> bool:
    if getattr(candidate, "need", None) != LOW:
        return True
    improvement = getattr(candidate, "expected_lineup_improvement", None)
    if improvement is None:
        return False
    return float(improvement) >= MIN_LOW_WAIVER_FEED_EDGE


def _item(
    league: FantasyLeagueState,
    *,
    priority: str,
    action_type: str,
    title: str,
    action: str,
    detail: str,
    impact_points: float | None,
    confidence: str,
    player_ids: tuple[str, ...] = (),
    partner_roster_id: str | None = None,
    faab_range: str | None = None,
    faab_target: str | None = None,
    bonus: float = 0.0,
) -> WeeklyActionItem:
    impact_bonus = min(max(float(impact_points or 0.0), 0.0), 10.0) * 3.0
    score = (
        _PRIORITY_SCORE.get(priority, 0.0)
        + _TYPE_SCORE.get(action_type, 0.0)
        + impact_bonus
        + float(bonus)
    )
    return WeeklyActionItem(
        platform_league_id=league.platform_league_id,
        league_name=league.name or league.platform_league_id,
        priority=priority,
        action_type=action_type,
        title=title,
        action=action,
        detail=detail,
        impact_points=impact_points,
        confidence=confidence,
        score=score,
        player_ids=player_ids,
        partner_roster_id=partner_roster_id,
        faab_range=faab_range,
        faab_target=faab_target,
    )


def _coverage_confidence(coverage: str) -> str:
    return "HIGH" if coverage == "FULL" else "MEDIUM" if coverage == "PARTIAL" else "LOW"


def _confidence_rank(value: str) -> int:
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(value, 0)


__all__ = [
    "HEALTH",
    "LINEUP",
    "MIN_LOW_WAIVER_FEED_EDGE",
    "PRIORITY_HIGH",
    "PRIORITY_LOW",
    "PRIORITY_MEDIUM",
    "TRADE",
    "WAIVER",
    "WeeklyActionFeed",
    "WeeklyActionItem",
    "waiver_candidate_visible_in_feed",
    "build_weekly_action_feed",
]
