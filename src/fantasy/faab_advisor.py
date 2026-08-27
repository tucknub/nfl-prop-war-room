from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Iterable, Sequence

from .market_waivers import HIGH, LOW, MEDIUM, MarketWaiverBoard, MarketWaiverCandidate
from .models import FantasyLeagueState, LeagueTransaction


_NEED_BASE = {
    HIGH: 48.0,
    MEDIUM: 30.0,
    LOW: 16.0,
}
_TARGET_CAP = {
    HIGH: 50.0,
    MEDIUM: 28.0,
    LOW: 12.0,
}
_MAX_CAP = {
    HIGH: 60.0,
    MEDIUM: 38.0,
    LOW: 18.0,
}


@dataclass(frozen=True)
class FaabAdvice:
    candidate: MarketWaiverCandidate
    score: float
    recommended_pct: float
    range_low_pct: float
    range_high_pct: float
    aggressive_pct: float
    max_pct: float
    recommended_bid: int
    range_low_bid: int
    range_high_bid: int
    aggressive_bid: int
    max_bid: int
    competition: str
    confidence: str
    comparable_supply: int
    budget_limited: bool
    reason: str


@dataclass(frozen=True)
class FaabAdviceBoard:
    enabled: bool
    starting_budget: int | None
    budget_used: int | None
    remaining_budget: int | None
    live_balance: bool
    historical_bid_count: int
    historical_median_pct: float | None
    historical_p75_pct: float | None
    advice: tuple[FaabAdvice, ...]
    reason: str = ""

    @property
    def budget_used_pct(self) -> float | None:
        if self.starting_budget is None or self.budget_used is None:
            return None
        return (self.budget_used / self.starting_budget) * 100.0


def build_faab_advice_board(
    league: FantasyLeagueState,
    market_waivers: MarketWaiverBoard,
    *,
    current_week: int = 0,
    transactions: Iterable[LeagueTransaction] = (),
    limit: int = 20,
) -> FaabAdviceBoard:
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer from 1 to 100")

    starting_budget = _positive_int(league.rules.waiver_budget)
    if starting_budget is None:
        return FaabAdviceBoard(
            enabled=False,
            starting_budget=None,
            budget_used=None,
            remaining_budget=None,
            live_balance=False,
            historical_bid_count=0,
            historical_median_pct=None,
            historical_p75_pct=None,
            advice=(),
            reason="This league does not expose a positive FAAB waiver budget.",
        )

    budget_used = _live_budget_used(league)
    live_balance = budget_used is not None
    remaining_budget = (
        max(0, starting_budget - budget_used)
        if budget_used is not None
        else None
    )

    historical_pcts = _historical_bid_pcts(transactions, starting_budget)
    historical_median_pct = (
        float(median(historical_pcts)) if historical_pcts else None
    )
    historical_p75_pct = (
        _percentile(historical_pcts, 0.75) if historical_pcts else None
    )

    candidates = tuple(market_waivers.candidates)
    trend_counts = tuple(max(0, int(row.trend_count)) for row in candidates)

    advice_rows = tuple(
        _build_advice(
            candidate,
            candidates=candidates,
            trend_counts=trend_counts,
            starting_budget=starting_budget,
            remaining_budget=remaining_budget,
            live_balance=live_balance,
            team_count=max(0, int(league.team_count or 0)),
            current_week=max(0, int(current_week or 0)),
            historical_bid_count=len(historical_pcts),
            historical_p75_pct=historical_p75_pct,
        )
        for candidate in candidates[:limit]
    )

    return FaabAdviceBoard(
        enabled=True,
        starting_budget=starting_budget,
        budget_used=budget_used,
        remaining_budget=remaining_budget,
        live_balance=live_balance,
        historical_bid_count=len(historical_pcts),
        historical_median_pct=historical_median_pct,
        historical_p75_pct=historical_p75_pct,
        advice=advice_rows,
    )


def _build_advice(
    candidate: MarketWaiverCandidate,
    *,
    candidates: Sequence[MarketWaiverCandidate],
    trend_counts: Sequence[int],
    starting_budget: int,
    remaining_budget: int | None,
    live_balance: bool,
    team_count: int,
    current_week: int,
    historical_bid_count: int,
    historical_p75_pct: float | None,
) -> FaabAdvice:
    need_base = _NEED_BASE.get(candidate.need, 16.0)
    improvement = candidate.expected_lineup_improvement
    improvement_score = (
        min(max(float(improvement or 0.0), 0.0), 10.0) * 2.0
    )

    coverage_score = 7.0 if candidate.coverage == "FULL" else 3.0

    demand_percentile = _rank_percentile(
        max(0, int(candidate.trend_count)),
        trend_counts,
    )
    demand_score = demand_percentile * 10.0

    comparable_supply = _comparable_supply(candidate, candidates)
    scarcity_score = (
        8.0
        if comparable_supply == 0
        else 5.5
        if comparable_supply == 1
        else 3.0
        if comparable_supply <= 3
        else 0.0
    )

    team_pressure = _team_pressure(team_count)
    team_score = team_pressure * 5.0

    history_pressure = _history_pressure(historical_p75_pct)
    history_score = history_pressure * 7.0

    season_score = _season_spend_score(current_week)

    score = min(
        100.0,
        need_base
        + improvement_score
        + coverage_score
        + demand_score
        + scarcity_score
        + team_score
        + history_score
        + season_score,
    )

    raw_target_pct = max(1.0, 45.0 * (score / 100.0) ** 2)
    target_pct = min(_TARGET_CAP.get(candidate.need, 12.0), raw_target_pct)
    low_pct = max(0.0, target_pct * 0.78)
    high_pct = min(
        _TARGET_CAP.get(candidate.need, 12.0),
        max(target_pct, target_pct * 1.12),
    )
    aggressive_pct = min(
        _MAX_CAP.get(candidate.need, 18.0),
        max(high_pct, target_pct * 1.30),
    )
    max_pct = min(
        _MAX_CAP.get(candidate.need, 18.0),
        max(aggressive_pct, target_pct * 1.55),
    )

    low_bid = _bid_from_pct(low_pct, starting_budget)
    target_bid = _bid_from_pct(target_pct, starting_budget, odd_nudge=True)
    high_bid = _bid_from_pct(high_pct, starting_budget, odd_nudge=True)
    aggressive_bid = _bid_from_pct(
        aggressive_pct,
        starting_budget,
        odd_nudge=True,
    )
    max_bid = _bid_from_pct(max_pct, starting_budget)

    uncapped = (low_bid, target_bid, high_bid, aggressive_bid, max_bid)
    if live_balance and remaining_budget is not None:
        low_bid, target_bid, high_bid, aggressive_bid, max_bid = (
            min(value, remaining_budget) for value in uncapped
        )
    budget_limited = (
        live_balance
        and remaining_budget is not None
        and any(value > remaining_budget for value in uncapped)
    )

    competition_pressure = (
        demand_percentile * 0.45
        + history_pressure * 0.35
        + team_pressure * 0.20
    )
    competition = (
        "HIGH"
        if competition_pressure >= 0.67
        else "MEDIUM"
        if competition_pressure >= 0.35
        else "LOW"
    )

    confidence_points = 0
    if candidate.coverage == "FULL":
        confidence_points += 2
    elif candidate.coverage == "PARTIAL":
        confidence_points += 1
    if live_balance:
        confidence_points += 1
    if historical_bid_count >= 3:
        confidence_points += 1
    confidence = (
        "HIGH"
        if confidence_points >= 4
        else "MEDIUM"
        if confidence_points >= 2
        else "LOW"
    )

    reason_parts = [
        f"{candidate.need} roster need",
        (
            f"{float(improvement):+.2f} expected lineup points"
            if improvement is not None
            else "unquantified starter comparison"
        ),
        f"{candidate.coverage} market coverage",
    ]
    if candidate.trend_count > 0:
        reason_parts.append(f"{candidate.trend_count:,} Sleeper adds")
    reason_parts.append(
        "scarce comparable supply"
        if comparable_supply <= 1
        else f"{comparable_supply} comparable alternatives"
    )
    if historical_p75_pct is not None:
        reason_parts.append(
            f"recent league P75 winning bid {historical_p75_pct:.1f}%"
        )
    if budget_limited:
        reason_parts.append("capped by live remaining FAAB")

    return FaabAdvice(
        candidate=candidate,
        score=score,
        recommended_pct=target_pct,
        range_low_pct=low_pct,
        range_high_pct=high_pct,
        aggressive_pct=aggressive_pct,
        max_pct=max_pct,
        recommended_bid=target_bid,
        range_low_bid=low_bid,
        range_high_bid=high_bid,
        aggressive_bid=aggressive_bid,
        max_bid=max_bid,
        competition=competition,
        confidence=confidence,
        comparable_supply=comparable_supply,
        budget_limited=budget_limited,
        reason=" · ".join(reason_parts),
    )


def _live_budget_used(league: FantasyLeagueState) -> int | None:
    roster_id = str(league.my_platform_roster_id or "").strip()
    if not roster_id:
        return None
    roster = next(
        (
            row
            for row in league.rosters
            if row.platform_roster_id == roster_id
        ),
        None,
    )
    if roster is None:
        return None
    return _nonnegative_int(roster.settings.get("waiver_budget_used"))


def _historical_bid_pcts(
    transactions: Iterable[LeagueTransaction],
    starting_budget: int,
) -> list[float]:
    values: list[float] = []
    for transaction in transactions:
        if transaction.transaction_type.casefold() != "waiver":
            continue
        if transaction.status.casefold() not in {
            "complete",
            "completed",
            "success",
            "successful",
        }:
            continue
        if not transaction.adds:
            continue
        bid = _nonnegative_float(transaction.waiver_bid)
        if bid is None:
            continue
        values.append((bid / starting_budget) * 100.0)
    return values


def _comparable_supply(
    candidate: MarketWaiverCandidate,
    candidates: Sequence[MarketWaiverCandidate],
) -> int:
    floor = candidate.market_fantasy_points - 2.0
    return sum(
        1
        for row in candidates
        if row.sleeper_player_id != candidate.sleeper_player_id
        and row.position == candidate.position
        and row.market_fantasy_points >= floor
    )


def _rank_percentile(value: int, values: Sequence[int]) -> float:
    if not values or max(values, default=0) <= 0:
        return 0.0
    below = sum(1 for row in values if row < value)
    equal = sum(1 for row in values if row == value)
    return min(1.0, max(0.0, (below + 0.5 * equal) / len(values)))


def _team_pressure(team_count: int) -> float:
    if team_count <= 8:
        return 0.0
    if team_count <= 10:
        return 0.25
    if team_count <= 12:
        return 0.55
    if team_count <= 14:
        return 0.80
    return 1.0


def _history_pressure(p75_pct: float | None) -> float:
    if p75_pct is None:
        return 0.0
    return min(1.0, max(0.0, p75_pct / 25.0))


def _season_spend_score(current_week: int) -> float:
    if current_week <= 0:
        return 0.0
    if current_week <= 4:
        return 0.0
    if current_week <= 8:
        return 1.5
    if current_week <= 12:
        return 3.0
    return 4.0


def _bid_from_pct(
    pct: float,
    starting_budget: int,
    *,
    odd_nudge: bool = False,
) -> int:
    if pct <= 0.0 or starting_budget <= 0:
        return 0
    amount = max(1, int(math.ceil((pct / 100.0) * starting_budget)))
    if odd_nudge and amount >= 5 and amount % 5 == 0:
        amount += 1
    return min(starting_budget, amount)


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        raise ValueError("values must not be empty")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = min(1.0, max(0.0, fraction)) * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _positive_int(value: object) -> int | None:
    parsed = _nonnegative_int(value)
    return parsed if parsed is not None and parsed > 0 else None


def _nonnegative_int(value: object) -> int | None:
    parsed = _nonnegative_float(value)
    if parsed is None:
        return None
    return max(0, int(round(parsed)))


def _nonnegative_float(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < 0:
        return None
    return parsed


__all__ = [
    "FaabAdvice",
    "FaabAdviceBoard",
    "build_faab_advice_board",
]
