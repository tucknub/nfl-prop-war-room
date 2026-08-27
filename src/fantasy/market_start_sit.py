from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .lineup_check import LineupCheck, LineupPlayerFact
from .market_fantasy import MarketFantasyBaseline, build_market_fantasy_baseline


USABLE_COVERAGE = frozenset({"FULL", "PARTIAL"})
MIN_SWAP_EDGE = 1.0

SWAP = "SWAP"
KEEP = "KEEP"
CLOSE = "CLOSE"
FILL = "FILL"
INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class MarketStartSitPlayer:
    player_id: str
    name: str
    position: str
    status: str
    fantasy_points: float
    coverage: str
    event_label: str

    @property
    def usable(self) -> bool:
        return self.coverage in USABLE_COVERAGE


@dataclass(frozen=True)
class MarketStartSitAdvice:
    slot_index: int
    slot: str
    starter: MarketStartSitPlayer | None
    best_bench: MarketStartSitPlayer | None
    verdict: str
    edge_points: float | None
    reason: str


@dataclass(frozen=True)
class MarketStartSitBoard:
    slots: tuple[MarketStartSitAdvice, ...]

    @property
    def swap_count(self) -> int:
        return sum(1 for row in self.slots if row.verdict == SWAP)

    @property
    def fill_count(self) -> int:
        return sum(1 for row in self.slots if row.verdict == FILL)

    @property
    def actionable_count(self) -> int:
        return self.swap_count + self.fill_count


def build_market_start_sit_board(
    lineup: LineupCheck,
    scoring_settings: Mapping[str, Any],
    player_catalog: Mapping[str, Mapping[str, Any]],
    prop_rows: Iterable[Mapping[str, Any]],
) -> MarketStartSitBoard:
    rows = tuple(dict(row) for row in prop_rows)
    advice: list[MarketStartSitAdvice] = []

    for slot in lineup.slots:
        starter = _market_player(
            slot.starter,
            scoring_settings,
            player_catalog,
            rows,
        )
        alternatives = tuple(
            row
            for row in (
                _market_player(
                    player,
                    scoring_settings,
                    player_catalog,
                    rows,
                )
                for player in slot.eligible_alternatives
            )
            if row is not None
        )
        alternatives = tuple(
            sorted(
                alternatives,
                key=lambda row: (
                    0 if row.usable else 1,
                    -row.fantasy_points,
                    row.name.casefold(),
                ),
            )
        )
        best = next((row for row in alternatives if row.usable), None)

        verdict, edge, reason = _verdict(
            starter=starter,
            best_bench=best,
            slot_open=slot.starter is None,
        )
        advice.append(
            MarketStartSitAdvice(
                slot_index=slot.slot_index,
                slot=slot.slot,
                starter=starter,
                best_bench=best,
                verdict=verdict,
                edge_points=edge,
                reason=reason,
            )
        )

    return MarketStartSitBoard(slots=tuple(advice))


def _market_player(
    player: LineupPlayerFact | None,
    scoring_settings: Mapping[str, Any],
    player_catalog: Mapping[str, Mapping[str, Any]],
    prop_rows: tuple[Mapping[str, Any], ...],
) -> MarketStartSitPlayer | None:
    if player is None:
        return None
    catalog_row = player_catalog.get(player.player_id) or {}
    position = str(catalog_row.get("position") or player.position or "").strip().upper()
    baseline = build_market_fantasy_baseline(
        player.name,
        position,
        scoring_settings,
        prop_rows,
    )
    if baseline is None:
        return None
    return _from_baseline(player, baseline)


def _from_baseline(
    player: LineupPlayerFact,
    baseline: MarketFantasyBaseline,
) -> MarketStartSitPlayer:
    return MarketStartSitPlayer(
        player_id=player.player_id,
        name=player.name,
        position=player.position,
        status=player.status,
        fantasy_points=float(baseline.fantasy_points),
        coverage=baseline.coverage_status,
        event_label=baseline.event_label,
    )


def _verdict(
    *,
    starter: MarketStartSitPlayer | None,
    best_bench: MarketStartSitPlayer | None,
    slot_open: bool,
) -> tuple[str, float | None, str]:
    if slot_open:
        if best_bench is None:
            return (
                INCOMPLETE,
                None,
                "Open slot, but no eligible bench player has FULL/PARTIAL market coverage.",
            )
        return (
            FILL,
            None,
            f"Open slot: {best_bench.name} is the highest usable market-baseline bench option.",
        )

    if starter is None or not starter.usable:
        return (
            INCOMPLETE,
            None,
            "Current starter lacks FULL/PARTIAL market coverage, so no market swap verdict is made.",
        )
    if best_bench is None:
        return (
            KEEP,
            None,
            "No eligible bench player has FULL/PARTIAL market coverage.",
        )

    edge = best_bench.fantasy_points - starter.fantasy_points
    if edge >= MIN_SWAP_EDGE:
        return (
            SWAP,
            edge,
            f"{best_bench.name} has a market baseline {edge:.2f} points above {starter.name}.",
        )
    if edge <= -MIN_SWAP_EDGE:
        return (
            KEEP,
            edge,
            f"{starter.name} has a market baseline {abs(edge):.2f} points above the best covered bench option.",
        )
    return (
        CLOSE,
        edge,
        "Covered starter and bench baselines are within 1.00 fantasy point; treat this as a close call.",
    )


__all__ = [
    "CLOSE",
    "FILL",
    "INCOMPLETE",
    "KEEP",
    "MIN_SWAP_EDGE",
    "SWAP",
    "MarketStartSitAdvice",
    "MarketStartSitBoard",
    "MarketStartSitPlayer",
    "build_market_start_sit_board",
]
