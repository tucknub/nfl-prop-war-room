from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable, Mapping, Sequence

from .lineup_check import FLEX_ELIGIBILITY, positions_eligible_for_slot
from .market_fantasy import MarketFantasyBaseline, build_market_fantasy_baseline
from .models import FantasyLeagueState, Roster


ACCEPT = "ACCEPT"
BALANCED = "BALANCED"
DECLINE = "DECLINE"
INCOMPLETE = "INCOMPLETE"

GOOD_FOR_BOTH = "GOOD_FOR_BOTH"
PLAUSIBLE = "PLAUSIBLE"
HARD_SELL = "HARD_SELL"

_USABLE_COVERAGE = {"FULL", "PARTIAL"}


@dataclass(frozen=True)
class MarketTradePlayer:
    sleeper_player_id: str
    name: str
    position: str
    fantasy_positions: tuple[str, ...]
    nfl_team: str
    market_fantasy_points: float | None
    coverage: str
    component_count: int

    @property
    def usable_market(self) -> bool:
        return (
            self.market_fantasy_points is not None
            and self.coverage in _USABLE_COVERAGE
        )


@dataclass(frozen=True)
class TradeLineupSnapshot:
    starter_slots: int
    covered_starters: int
    covered_points: float
    assignments: tuple[tuple[str, str, float], ...]

    @property
    def coverage_ratio(self) -> float:
        if self.starter_slots <= 0:
            return 0.0
        return self.covered_starters / self.starter_slots


@dataclass(frozen=True)
class TradeTeamImpact:
    roster_id: str
    team_name: str
    current: TradeLineupSnapshot
    post_trade: TradeLineupSnapshot
    lineup_delta: float
    roster_size_before: int
    roster_size_after: int
    depth_warnings_before: tuple[str, ...]
    depth_warnings_after: tuple[str, ...]


@dataclass(frozen=True)
class MarketTradeAnalysis:
    verdict: str
    confidence: str
    partner_fit: str
    my_team: TradeTeamImpact
    partner_team: TradeTeamImpact
    give_players: tuple[MarketTradePlayer, ...]
    receive_players: tuple[MarketTradePlayer, ...]
    give_market_points: float | None
    receive_market_points: float | None
    raw_asset_delta: float | None
    decision_edge: float | None
    traded_assets_fully_usable: bool
    minimum_lineup_coverage: float
    reason: str

    @property
    def mutual_lineup_gain(self) -> bool:
        return (
            self.my_team.lineup_delta > 0
            and self.partner_team.lineup_delta > 0
        )


def analyze_market_trade(
    league: FantasyLeagueState,
    player_catalog: Mapping[str, Mapping[str, Any]],
    prop_rows: Iterable[Mapping[str, Any]],
    *,
    partner_roster_id: str,
    give_player_ids: Sequence[str],
    receive_player_ids: Sequence[str],
) -> MarketTradeAnalysis:
    if not league.ownership_ready:
        raise ValueError("Live league ownership is required to analyze a trade.")

    my_roster = _my_roster(league)
    if my_roster is None:
        raise ValueError("Your roster could not be identified.")

    partner_id = str(partner_roster_id or "").strip()
    if not partner_id:
        raise ValueError("partner_roster_id is required")
    if partner_id == my_roster.platform_roster_id:
        raise ValueError("Trade partner must be another roster.")

    partner = next(
        (
            roster
            for roster in league.rosters
            if roster.platform_roster_id == partner_id
        ),
        None,
    )
    if partner is None:
        raise ValueError("Trade partner was not found in this league.")

    give_ids = _normalize_trade_ids(give_player_ids, "give_player_ids")
    receive_ids = _normalize_trade_ids(
        receive_player_ids,
        "receive_player_ids",
    )
    if set(give_ids).intersection(receive_ids):
        raise ValueError("The same player cannot appear on both trade sides.")

    my_ids = set(_roster_player_ids(my_roster))
    partner_ids = set(_roster_player_ids(partner))
    missing_give = tuple(player_id for player_id in give_ids if player_id not in my_ids)
    missing_receive = tuple(
        player_id for player_id in receive_ids if player_id not in partner_ids
    )
    if missing_give:
        raise ValueError("Every give player must currently be on your roster.")
    if missing_receive:
        raise ValueError(
            "Every receive player must currently be on the selected partner roster."
        )

    all_relevant_ids = tuple(
        dict.fromkeys(
            (
                *_roster_player_ids(my_roster),
                *_roster_player_ids(partner),
            )
        )
    )
    market_players = {
        player_id: _market_player(
            player_id,
            player_catalog,
            league.rules.scoring_settings,
            prop_rows,
        )
        for player_id in all_relevant_ids
    }

    my_post_ids = tuple(
        dict.fromkeys(
            (
                *(player_id for player_id in _roster_player_ids(my_roster) if player_id not in set(give_ids)),
                *receive_ids,
            )
        )
    )
    partner_post_ids = tuple(
        dict.fromkeys(
            (
                *(player_id for player_id in _roster_player_ids(partner) if player_id not in set(receive_ids)),
                *give_ids,
            )
        )
    )

    my_current_lineup = _optimize_market_lineup(
        league.rules.starter_positions,
        tuple(
            market_players[player_id]
            for player_id in _roster_player_ids(my_roster)
            if player_id in market_players
        ),
    )
    my_post_lineup = _optimize_market_lineup(
        league.rules.starter_positions,
        tuple(
            market_players[player_id]
            for player_id in my_post_ids
            if player_id in market_players
        ),
    )
    partner_current_lineup = _optimize_market_lineup(
        league.rules.starter_positions,
        tuple(
            market_players[player_id]
            for player_id in _roster_player_ids(partner)
            if player_id in market_players
        ),
    )
    partner_post_lineup = _optimize_market_lineup(
        league.rules.starter_positions,
        tuple(
            market_players[player_id]
            for player_id in partner_post_ids
            if player_id in market_players
        ),
    )

    my_impact = TradeTeamImpact(
        roster_id=my_roster.platform_roster_id,
        team_name=_team_name(league, my_roster),
        current=my_current_lineup,
        post_trade=my_post_lineup,
        lineup_delta=my_post_lineup.covered_points - my_current_lineup.covered_points,
        roster_size_before=len(_roster_player_ids(my_roster)),
        roster_size_after=len(my_post_ids),
        depth_warnings_before=_depth_warnings(
            league.rules.starter_positions,
            _roster_player_ids(my_roster),
            player_catalog,
        ),
        depth_warnings_after=_depth_warnings(
            league.rules.starter_positions,
            my_post_ids,
            player_catalog,
        ),
    )
    partner_impact = TradeTeamImpact(
        roster_id=partner.platform_roster_id,
        team_name=_team_name(league, partner),
        current=partner_current_lineup,
        post_trade=partner_post_lineup,
        lineup_delta=(
            partner_post_lineup.covered_points
            - partner_current_lineup.covered_points
        ),
        roster_size_before=len(_roster_player_ids(partner)),
        roster_size_after=len(partner_post_ids),
        depth_warnings_before=_depth_warnings(
            league.rules.starter_positions,
            _roster_player_ids(partner),
            player_catalog,
        ),
        depth_warnings_after=_depth_warnings(
            league.rules.starter_positions,
            partner_post_ids,
            player_catalog,
        ),
    )

    give_players = tuple(market_players[player_id] for player_id in give_ids)
    receive_players = tuple(
        market_players[player_id] for player_id in receive_ids
    )
    traded_assets_fully_usable = all(
        row.usable_market for row in (*give_players, *receive_players)
    )
    give_market_points = _market_sum(give_players)
    receive_market_points = _market_sum(receive_players)
    raw_asset_delta = (
        receive_market_points - give_market_points
        if give_market_points is not None and receive_market_points is not None
        else None
    )

    coverage_values = (
        my_current_lineup.coverage_ratio,
        my_post_lineup.coverage_ratio,
        partner_current_lineup.coverage_ratio,
        partner_post_lineup.coverage_ratio,
    )
    minimum_lineup_coverage = min(coverage_values, default=0.0)

    verdict, confidence, partner_fit, decision_edge, reason = _verdict(
        my_impact=my_impact,
        partner_impact=partner_impact,
        raw_asset_delta=raw_asset_delta,
        traded_assets_fully_usable=traded_assets_fully_usable,
        minimum_lineup_coverage=minimum_lineup_coverage,
        give_players=give_players,
        receive_players=receive_players,
    )

    return MarketTradeAnalysis(
        verdict=verdict,
        confidence=confidence,
        partner_fit=partner_fit,
        my_team=my_impact,
        partner_team=partner_impact,
        give_players=give_players,
        receive_players=receive_players,
        give_market_points=give_market_points,
        receive_market_points=receive_market_points,
        raw_asset_delta=raw_asset_delta,
        decision_edge=decision_edge,
        traded_assets_fully_usable=traded_assets_fully_usable,
        minimum_lineup_coverage=minimum_lineup_coverage,
        reason=reason,
    )


def _verdict(
    *,
    my_impact: TradeTeamImpact,
    partner_impact: TradeTeamImpact,
    raw_asset_delta: float | None,
    traded_assets_fully_usable: bool,
    minimum_lineup_coverage: float,
    give_players: Sequence[MarketTradePlayer],
    receive_players: Sequence[MarketTradePlayer],
) -> tuple[str, str, str, float | None, str]:
    if not traded_assets_fully_usable:
        missing = [
            row.name
            for row in (*give_players, *receive_players)
            if not row.usable_market
        ]
        return (
            INCOMPLETE,
            "LOW",
            PLAUSIBLE,
            None,
            "No verdict: traded assets without FULL/PARTIAL market coverage: "
            + ", ".join(missing),
        )

    if raw_asset_delta is None:
        return (
            INCOMPLETE,
            "LOW",
            PLAUSIBLE,
            None,
            "No verdict: both trade sides need usable market values.",
        )

    if minimum_lineup_coverage < 0.40:
        return (
            INCOMPLETE,
            "LOW",
            PLAUSIBLE,
            None,
            (
                "No verdict: too little of the legal starting lineup has "
                f"FULL/PARTIAL market coverage ({minimum_lineup_coverage:.0%} minimum)."
            ),
        )

    decision_edge = my_impact.lineup_delta + (0.35 * raw_asset_delta)
    partner_raw_delta = -raw_asset_delta
    partner_edge = partner_impact.lineup_delta + (0.35 * partner_raw_delta)

    verdict = (
        ACCEPT
        if decision_edge >= 1.0
        else DECLINE
        if decision_edge <= -1.0
        else BALANCED
    )
    partner_fit = (
        GOOD_FOR_BOTH
        if partner_edge >= 0.5
        else PLAUSIBLE
        if partner_edge >= -1.0
        else HARD_SELL
    )

    all_full = all(
        row.coverage == "FULL" for row in (*give_players, *receive_players)
    )
    confidence = (
        "HIGH"
        if all_full and minimum_lineup_coverage >= 0.75
        else "MEDIUM"
        if minimum_lineup_coverage >= 0.50
        else "LOW"
    )

    reason = (
        f"Your optimized market-covered starting lineup moves "
        f"{my_impact.lineup_delta:+.2f} points; raw traded-asset market value "
        f"moves {raw_asset_delta:+.2f}. Partner optimized lineup moves "
        f"{partner_impact.lineup_delta:+.2f}."
    )
    return verdict, confidence, partner_fit, decision_edge, reason


def _market_player(
    player_id: str,
    player_catalog: Mapping[str, Mapping[str, Any]],
    scoring_settings: Mapping[str, Any],
    prop_rows: Iterable[Mapping[str, Any]],
) -> MarketTradePlayer:
    player = player_catalog.get(player_id) or {}
    name = _player_name(player, player_id)
    position = str(player.get("position") or "").strip().upper() or "—"
    fantasy_positions = _fantasy_positions(player, position)

    baseline: MarketFantasyBaseline | None = None
    if position in {"QB", "RB", "WR", "TE", "FB"}:
        baseline = build_market_fantasy_baseline(
            name,
            position,
            scoring_settings,
            prop_rows,
        )

    return MarketTradePlayer(
        sleeper_player_id=player_id,
        name=name,
        position=position,
        fantasy_positions=fantasy_positions,
        nfl_team=str(player.get("team") or "FA").strip().upper() or "FA",
        market_fantasy_points=(
            baseline.fantasy_points if baseline is not None else None
        ),
        coverage=(
            baseline.coverage_status if baseline is not None else "MISSING"
        ),
        component_count=(
            baseline.component_count if baseline is not None else 0
        ),
    )


def _optimize_market_lineup(
    starter_positions: Sequence[str],
    players: Sequence[MarketTradePlayer],
) -> TradeLineupSnapshot:
    slots = tuple(str(slot).strip().upper() for slot in starter_positions)
    usable = tuple(
        sorted(
            (row for row in players if row.usable_market),
            key=lambda row: (
                -float(row.market_fantasy_points or 0.0),
                row.name.casefold(),
                row.sleeper_player_id,
            ),
        )
    )
    if not slots or not usable:
        return TradeLineupSnapshot(
            starter_slots=len(slots),
            covered_starters=0,
            covered_points=0.0,
            assignments=(),
        )

    @lru_cache(maxsize=None)
    def solve(
        slot_index: int,
        used_mask: int,
    ) -> tuple[float, int, tuple[tuple[str, str, float], ...]]:
        if slot_index >= len(slots):
            return 0.0, 0, ()

        slot = slots[slot_index]
        best = solve(slot_index + 1, used_mask)

        for index, player in enumerate(usable):
            bit = 1 << index
            if used_mask & bit:
                continue
            if not positions_eligible_for_slot(
                player.fantasy_positions or (player.position,),
                slot,
            ):
                continue

            next_score, next_count, next_assignments = solve(
                slot_index + 1,
                used_mask | bit,
            )
            points = float(player.market_fantasy_points or 0.0)
            candidate = (
                points + next_score,
                1 + next_count,
                ((slot, player.name, points), *next_assignments),
            )
            if _better_lineup(candidate, best):
                best = candidate

        return best

    score, count, assignments = solve(0, 0)
    return TradeLineupSnapshot(
        starter_slots=len(slots),
        covered_starters=count,
        covered_points=score,
        assignments=assignments,
    )


def _better_lineup(
    candidate: tuple[float, int, tuple[tuple[str, str, float], ...]],
    incumbent: tuple[float, int, tuple[tuple[str, str, float], ...]],
) -> bool:
    if candidate[0] > incumbent[0] + 1e-9:
        return True
    if incumbent[0] > candidate[0] + 1e-9:
        return False
    if candidate[1] != incumbent[1]:
        return candidate[1] > incumbent[1]
    return candidate[2] < incumbent[2]


def _depth_warnings(
    starter_positions: Sequence[str],
    player_ids: Sequence[str],
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> tuple[str, ...]:
    direct_requirements = Counter(
        str(slot).strip().upper()
        for slot in starter_positions
        if str(slot).strip().upper() not in FLEX_ELIGIBILITY
    )
    counts: Counter[str] = Counter()
    for player_id in player_ids:
        player = player_catalog.get(player_id) or {}
        position = str(player.get("position") or "").strip().upper()
        if position:
            counts[position] += 1

    warnings: list[str] = []
    for position, required in sorted(direct_requirements.items()):
        actual = counts.get(position, 0)
        if actual < required:
            warnings.append(
                f"{position} below direct starter demand ({actual}/{required})"
            )
        elif actual == required:
            warnings.append(
                f"{position} has no direct-slot cushion ({actual}/{required})"
            )
    return tuple(warnings)


def _market_sum(
    players: Sequence[MarketTradePlayer],
) -> float | None:
    if not players or not all(row.usable_market for row in players):
        return None
    return sum(float(row.market_fantasy_points or 0.0) for row in players)


def _normalize_trade_ids(
    values: Sequence[str],
    name: str,
) -> tuple[str, ...]:
    rows = tuple(
        dict.fromkeys(
            str(value or "").strip()
            for value in values
            if str(value or "").strip() not in {"", "0"}
        )
    )
    if not rows:
        raise ValueError(f"{name} must contain at least one player")
    if len(rows) > 4:
        raise ValueError(f"{name} supports at most four players")
    return rows


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


def _roster_player_ids(roster: Roster) -> tuple[str, ...]:
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


def _fantasy_positions(
    player: Mapping[str, Any],
    primary_position: str,
) -> tuple[str, ...]:
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
    return (primary_position,) if primary_position and primary_position != "—" else ()


def _team_name(
    league: FantasyLeagueState,
    roster: Roster,
) -> str:
    manager = next(
        (
            row
            for row in league.managers
            if row.platform_user_id == roster.platform_user_id
        ),
        None,
    )
    if manager is None:
        return f"Roster {roster.platform_roster_id}"
    return (
        manager.team_name
        or manager.display_name
        or f"Roster {roster.platform_roster_id}"
    )


def _player_name(
    player: Mapping[str, Any],
    player_id: str,
) -> str:
    full_name = str(player.get("full_name") or "").strip()
    if full_name:
        return full_name
    first = str(player.get("first_name") or "").strip()
    last = str(player.get("last_name") or "").strip()
    return f"{first} {last}".strip() or player_id


__all__ = [
    "ACCEPT",
    "BALANCED",
    "DECLINE",
    "INCOMPLETE",
    "GOOD_FOR_BOTH",
    "PLAUSIBLE",
    "HARD_SELL",
    "MarketTradePlayer",
    "TradeLineupSnapshot",
    "TradeTeamImpact",
    "MarketTradeAnalysis",
    "analyze_market_trade",
]
