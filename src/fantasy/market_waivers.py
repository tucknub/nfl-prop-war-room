from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Any, Iterable, Mapping

from .lineup_check import (
    NEEDS_ACTION,
    WATCH,
    LineupCheck,
    LineupSlotCheck,
    positions_eligible_for_slot,
)
from .live_ownership import lookup_live_sleeper_player
from .market_fantasy import MarketFantasyBaseline, build_market_fantasy_baseline
from .models import FantasyLeagueState
from .roster_health import SERIOUS_STATUSES
from .sleeper import SleeperTrendingPlayer


FULL = "FULL"
PARTIAL = "PARTIAL"
USABLE_COVERAGE = frozenset({FULL, PARTIAL})

HIGH = "HIGH"
MEDIUM = "MEDIUM"
LOW = "LOW"
_NEED_ORDER = {HIGH: 0, MEDIUM: 1, LOW: 2}

MIN_UPGRADE_EDGE = 1.0
_SUPPORTED_POSITIONS = frozenset({"QB", "RB", "WR", "TE", "FB"})


@dataclass(frozen=True)
class MarketWaiverCandidate:
    sleeper_player_id: str
    player_name: str
    position: str
    nfl_team: str
    status: str
    need: str
    target_slot: str
    fit_slots: tuple[str, ...]
    market_fantasy_points: float
    coverage: str
    replacement_player: str
    replacement_fantasy_points: float | None
    expected_lineup_improvement: float | None
    trend_count: int = 0
    mine_elsewhere: tuple[str, ...] = ()
    reason: str = ""

    @property
    def familiar(self) -> bool:
        return bool(self.mine_elsewhere)

    @property
    def quantified_upgrade(self) -> bool:
        return (
            self.expected_lineup_improvement is not None
            and self.expected_lineup_improvement >= MIN_UPGRADE_EDGE
        )


@dataclass(frozen=True)
class MarketWaiverBoard:
    available_player_count: int
    market_covered_count: int
    candidates: tuple[MarketWaiverCandidate, ...]

    @property
    def high_need_count(self) -> int:
        return sum(1 for row in self.candidates if row.need == HIGH)

    @property
    def upgrade_count(self) -> int:
        return sum(1 for row in self.candidates if row.quantified_upgrade)

    @property
    def full_coverage_count(self) -> int:
        return sum(1 for row in self.candidates if row.coverage == FULL)


@dataclass(frozen=True)
class _TargetSlot:
    slot_index: int
    label: str
    need: str
    replacement_player: str
    replacement_fantasy_points: float | None
    expected_lineup_improvement: float | None


def build_market_ranked_waivers(
    league: FantasyLeagueState,
    lineup: LineupCheck,
    player_catalog: Mapping[str, Mapping[str, Any]],
    prop_rows: Iterable[Mapping[str, Any]],
    *,
    all_leagues: Iterable[FantasyLeagueState] = (),
    trends: Iterable[SleeperTrendingPlayer] = (),
    limit: int = 50,
) -> MarketWaiverBoard:
    if not league.ownership_ready:
        raise ValueError(
            "Sleeper ownership is not ready; market-ranked waiver availability is unsafe"
        )
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("limit must be an integer from 1 to 200")

    rows = tuple(dict(row) for row in prop_rows)
    prop_names = {
        _normalize_name(row.get("player"))
        for row in rows
        if _normalize_name(row.get("player"))
    }
    trend_counts = {
        str(row.player_id): max(0, int(row.count))
        for row in trends
        if str(row.player_id or "").strip()
    }
    league_rows = tuple(all_leagues)
    slot_labels = _slot_labels(lineup)
    rostered = _rostered_player_ids(league)

    starter_cache: dict[str, MarketFantasyBaseline | None] = {}
    available_count = 0
    covered_count = 0
    ranked: list[MarketWaiverCandidate] = []

    for raw_player_id, raw_player in player_catalog.items():
        player_id = str(raw_player_id or "").strip()
        if not player_id or player_id in rostered or not isinstance(raw_player, Mapping):
            continue
        if raw_player.get("active") is False:
            continue

        position = str(raw_player.get("position") or "").strip().upper()
        if position not in _SUPPORTED_POSITIONS:
            continue

        raw_status = (
            str(raw_player.get("injury_status") or "").strip()
            or str(raw_player.get("status") or "").strip()
            or "Active"
        )
        normalized_status = raw_status.casefold()
        if normalized_status in SERIOUS_STATUSES or normalized_status in {
            "retired",
            "inactive",
        }:
            continue

        fantasy_positions = _fantasy_positions(raw_player)
        eligible_slots = tuple(
            (slot, slot_labels[slot.slot_index])
            for slot in lineup.slots
            if positions_eligible_for_slot(fantasy_positions, slot.slot)
        )
        if not eligible_slots:
            continue

        available_count += 1
        name = _player_name(raw_player, player_id)
        if prop_names and _normalize_name(name) not in prop_names:
            continue

        baseline = build_market_fantasy_baseline(
            name,
            position,
            league.rules.scoring_settings,
            rows,
        )
        if baseline is None or baseline.coverage_status not in USABLE_COVERAGE:
            continue
        covered_count += 1

        targets = tuple(
            _target_for_slot(
                slot,
                label,
                candidate_points=float(baseline.fantasy_points),
                scoring_settings=league.rules.scoring_settings,
                player_catalog=player_catalog,
                prop_rows=rows,
                starter_cache=starter_cache,
            )
            for slot, label in eligible_slots
        )
        viable_targets = tuple(target for target in targets if _keep_target(target))
        if not viable_targets:
            continue
        target = min(viable_targets, key=_target_sort_key)

        mine_elsewhere: tuple[str, ...] = ()
        if league_rows:
            cross = lookup_live_sleeper_player(league_rows, player_id)
            selected_name = league.name or league.platform_league_id
            mine_elsewhere = tuple(
                league_name
                for league_name in cross.mine_in
                if league_name != selected_name
            )

        fit_slots = tuple(label for _, label in eligible_slots)
        ranked.append(
            MarketWaiverCandidate(
                sleeper_player_id=player_id,
                player_name=name,
                position=position,
                nfl_team=str(raw_player.get("team") or "FA").strip().upper() or "FA",
                status=raw_status.replace("_", " ").title(),
                need=target.need,
                target_slot=target.label,
                fit_slots=fit_slots,
                market_fantasy_points=float(baseline.fantasy_points),
                coverage=baseline.coverage_status,
                replacement_player=target.replacement_player,
                replacement_fantasy_points=target.replacement_fantasy_points,
                expected_lineup_improvement=target.expected_lineup_improvement,
                trend_count=trend_counts.get(player_id, 0),
                mine_elsewhere=mine_elsewhere,
                reason=_reason(target),
            )
        )

    ranked.sort(key=_candidate_sort_key)
    return MarketWaiverBoard(
        available_player_count=available_count,
        market_covered_count=covered_count,
        candidates=tuple(ranked[:limit]),
    )


def _target_for_slot(
    slot: LineupSlotCheck,
    label: str,
    *,
    candidate_points: float,
    scoring_settings: Mapping[str, Any],
    player_catalog: Mapping[str, Mapping[str, Any]],
    prop_rows: tuple[Mapping[str, Any], ...],
    starter_cache: dict[str, MarketFantasyBaseline | None],
) -> _TargetSlot:
    need = (
        HIGH
        if slot.state == NEEDS_ACTION
        else MEDIUM
        if slot.state == WATCH
        else LOW
    )

    if slot.state == NEEDS_ACTION:
        return _TargetSlot(
            slot_index=slot.slot_index,
            label=label,
            need=need,
            replacement_player=(
                slot.starter.name if slot.starter is not None else "Open slot"
            ),
            replacement_fantasy_points=0.0,
            expected_lineup_improvement=candidate_points,
        )

    starter = slot.starter
    if starter is None:
        return _TargetSlot(
            slot_index=slot.slot_index,
            label=label,
            need=need,
            replacement_player="Open slot",
            replacement_fantasy_points=0.0,
            expected_lineup_improvement=candidate_points,
        )

    starter_baseline = _starter_baseline(
        starter.player_id,
        starter.name,
        starter.position,
        scoring_settings,
        player_catalog,
        prop_rows,
        starter_cache,
    )
    starter_points = (
        float(starter_baseline.fantasy_points)
        if starter_baseline is not None
        and starter_baseline.coverage_status in USABLE_COVERAGE
        else None
    )
    improvement = (
        candidate_points - starter_points
        if starter_points is not None
        else None
    )
    return _TargetSlot(
        slot_index=slot.slot_index,
        label=label,
        need=need,
        replacement_player=starter.name,
        replacement_fantasy_points=starter_points,
        expected_lineup_improvement=improvement,
    )


def _starter_baseline(
    player_id: str,
    player_name: str,
    position: str,
    scoring_settings: Mapping[str, Any],
    player_catalog: Mapping[str, Mapping[str, Any]],
    prop_rows: tuple[Mapping[str, Any], ...],
    cache: dict[str, MarketFantasyBaseline | None],
) -> MarketFantasyBaseline | None:
    if player_id in cache:
        return cache[player_id]
    catalog_row = player_catalog.get(player_id) or {}
    resolved_position = (
        str(catalog_row.get("position") or position or "").strip().upper()
    )
    baseline = build_market_fantasy_baseline(
        player_name,
        resolved_position,
        scoring_settings,
        prop_rows,
    )
    cache[player_id] = baseline
    return baseline


def _keep_target(target: _TargetSlot) -> bool:
    if target.need == HIGH:
        return True
    if target.need == MEDIUM:
        return (
            target.expected_lineup_improvement is None
            or target.expected_lineup_improvement >= 0.0
        )
    return (
        target.expected_lineup_improvement is not None
        and target.expected_lineup_improvement >= MIN_UPGRADE_EDGE
    )


def _target_sort_key(target: _TargetSlot) -> tuple[int, int, float, int]:
    improvement = target.expected_lineup_improvement
    return (
        _NEED_ORDER[target.need],
        0 if improvement is not None else 1,
        -(improvement if improvement is not None else 0.0),
        target.slot_index,
    )


def _candidate_sort_key(
    row: MarketWaiverCandidate,
) -> tuple[int, int, float, int, float, int, int, str, str]:
    improvement = row.expected_lineup_improvement
    return (
        _NEED_ORDER[row.need],
        0 if improvement is not None else 1,
        -(improvement if improvement is not None else 0.0),
        0 if row.coverage == FULL else 1,
        -row.market_fantasy_points,
        -row.trend_count,
        0 if row.familiar else 1,
        row.player_name.casefold(),
        row.sleeper_player_id,
    )


def _reason(target: _TargetSlot) -> str:
    improvement = target.expected_lineup_improvement
    if target.need == HIGH:
        return (
            f"{target.label} currently needs action; this is the best legal "
            "starter slot for the candidate."
        )
    if improvement is None:
        return (
            f"Fits the {target.label} watch need, but the current starter lacks "
            "FULL/PARTIAL market coverage for a numeric comparison."
        )
    return (
        f"Market baseline is {improvement:+.2f} points versus "
        f"{target.replacement_player} in {target.label}."
    )


def _slot_labels(lineup: LineupCheck) -> Mapping[int, str]:
    totals = Counter(row.slot for row in lineup.slots)
    seen: Counter[str] = Counter()
    labels: dict[int, str] = {}
    for row in lineup.slots:
        seen[row.slot] += 1
        labels[row.slot_index] = (
            row.slot
            if totals[row.slot] == 1
            else f"{row.slot} {seen[row.slot]}"
        )
    return labels


def _rostered_player_ids(league: FantasyLeagueState) -> set[str]:
    return {
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


def _normalize_name(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


__all__ = [
    "FULL",
    "HIGH",
    "LOW",
    "MEDIUM",
    "MIN_UPGRADE_EDGE",
    "PARTIAL",
    "MarketWaiverBoard",
    "MarketWaiverCandidate",
    "build_market_ranked_waivers",
]
