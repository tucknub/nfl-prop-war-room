from __future__ import annotations

from dataclasses import dataclass
from statistics import median
import re
from typing import Any, Iterable, Mapping


SUPPORTED_MARKETS = {
    "passing_yards",
    "passing_tds",
    "interceptions",
    "rushing_yards",
    "receiving_yards",
    "receptions",
    "anytime_td",
    "rushing_tds",
    "receiving_tds",
}

DEFAULT_SCORING = {
    "pass_yd": 0.04,
    "pass_td": 4.0,
    "pass_int": -2.0,
    "rush_yd": 0.1,
    "rush_td": 6.0,
    "rec": 0.0,
    "rec_yd": 0.1,
    "rec_td": 6.0,
}


@dataclass(frozen=True)
class MarketFantasyComponent:
    market: str
    label: str
    market_value: float
    value_type: str
    fantasy_points: float
    book_count: int


@dataclass(frozen=True)
class MarketFantasyBaseline:
    player_name: str
    event_label: str
    commence_time: str | None
    fantasy_points: float
    coverage_status: str
    components: tuple[MarketFantasyComponent, ...]
    fallback_scoring_keys: tuple[str, ...]

    @property
    def component_count(self) -> int:
        return len(self.components)


def build_market_fantasy_baseline(
    player_name: str,
    position: str,
    scoring_settings: Mapping[str, Any],
    prop_rows: Iterable[Mapping[str, Any]],
) -> MarketFantasyBaseline | None:
    normalized_name = _normalize_name(player_name)
    if not normalized_name:
        raise ValueError("player_name is required")

    player_rows = [
        dict(row)
        for row in prop_rows
        if _normalize_name(row.get("player")) == normalized_name
        and str(row.get("market") or "").strip().lower() in SUPPORTED_MARKETS
        and not _is_alt(row)
    ]
    if not player_rows:
        return None

    event_rows = _select_event(player_rows)
    if not event_rows:
        return None

    position = str(position or "").strip().upper()
    fallbacks: set[str] = set()
    components: list[MarketFantasyComponent] = []

    def score(key: str) -> float:
        if key not in scoring_settings:
            fallbacks.add(key)
            return DEFAULT_SCORING[key]
        try:
            return float(scoring_settings[key])
        except (TypeError, ValueError):
            fallbacks.add(key)
            return DEFAULT_SCORING[key]

    line_specs = (
        ("passing_yards", "Passing yards", "pass_yd"),
        ("passing_tds", "Passing TDs", "pass_td"),
        ("interceptions", "Interceptions", "pass_int"),
        ("rushing_yards", "Rushing yards", "rush_yd"),
        ("receiving_yards", "Receiving yards", "rec_yd"),
        ("receptions", "Receptions", "rec"),
    )
    for market, label, scoring_key in line_specs:
        consensus = _consensus_line(event_rows, market)
        if consensus is None:
            continue
        line, books = consensus
        factor = score(scoring_key)
        if abs(factor) < 1e-12:
            continue
        components.append(
            MarketFantasyComponent(
                market=market,
                label=label,
                market_value=line,
                value_type="CONSENSUS_LINE",
                fantasy_points=line * factor,
                book_count=books,
            )
        )

    anytime = _consensus_binary_probability(event_rows, "anytime_td")
    if anytime is not None:
        probability, books = anytime
        td_factor = _anytime_td_scoring_factor(position, score)
        if td_factor is not None and abs(td_factor) > 1e-12:
            components.append(
                MarketFantasyComponent(
                    market="anytime_td",
                    label="Anytime TD",
                    market_value=probability,
                    value_type="DEVIGGED_PROBABILITY",
                    fantasy_points=probability * td_factor,
                    book_count=books,
                )
            )
    else:
        for market, label, scoring_key in (
            ("rushing_tds", "Rushing TD", "rush_td"),
            ("receiving_tds", "Receiving TD", "rec_td"),
        ):
            probability = _consensus_binary_probability(event_rows, market)
            if probability is None:
                continue
            fair_prob, books = probability
            factor = score(scoring_key)
            if abs(factor) < 1e-12:
                continue
            components.append(
                MarketFantasyComponent(
                    market=market,
                    label=label,
                    market_value=fair_prob,
                    value_type="DEVIGGED_PROBABILITY",
                    fantasy_points=fair_prob * factor,
                    book_count=books,
                )
            )

    if not components:
        return None

    components.sort(key=lambda row: row.market)
    total = sum(row.fantasy_points for row in components)
    count = len(components)
    coverage = "FULL" if count >= 4 else ("PARTIAL" if count >= 2 else "THIN")
    first = event_rows[0]
    away = str(first.get("away_team") or "").strip()
    home = str(first.get("home_team") or "").strip()
    event_label = (
        f"{away} @ {home}"
        if away and home
        else away or home or str(first.get("event_id") or "NFL event")
    )

    return MarketFantasyBaseline(
        player_name=str(player_name).strip(),
        event_label=event_label,
        commence_time=(
            str(first.get("commence_time")).strip()
            if first.get("commence_time")
            else None
        ),
        fantasy_points=total,
        coverage_status=coverage,
        components=tuple(components),
        fallback_scoring_keys=tuple(sorted(fallbacks)),
    )


def _select_event(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = _event_key(row)
        groups.setdefault(key, []).append(row)
    if not groups:
        return []

    def event_rank(item: tuple[str, list[dict[str, Any]]]) -> tuple[int, str, str]:
        key, group = item
        distinct = {
            str(row.get("market") or "").strip().lower()
            for row in group
            if str(row.get("market") or "").strip().lower() in SUPPORTED_MARKETS
        }
        times = sorted(
            str(row.get("commence_time") or "").strip()
            for row in group
            if str(row.get("commence_time") or "").strip()
        )
        commence = times[0] if times else "9999"
        return (-len(distinct), commence, key)

    selected_key, selected = sorted(groups.items(), key=event_rank)[0]
    return sorted(
        selected,
        key=lambda row: (
            str(row.get("market") or ""),
            str(row.get("book") or ""),
            float(row.get("line") or 0),
        ),
    )


def _consensus_line(
    rows: list[dict[str, Any]],
    market: str,
) -> tuple[float, int] | None:
    by_book: dict[str, list[float]] = {}
    for row in rows:
        if str(row.get("market") or "").strip().lower() != market:
            continue
        try:
            line = float(row.get("line"))
        except (TypeError, ValueError):
            continue
        book = str(row.get("book") or row.get("source") or "unknown").strip().lower()
        by_book.setdefault(book, []).append(line)
    if not by_book:
        return None
    book_lines = [median(values) for values in by_book.values() if values]
    if not book_lines:
        return None
    return float(median(book_lines)), len(book_lines)


def _consensus_binary_probability(
    rows: list[dict[str, Any]],
    market: str,
) -> tuple[float, int] | None:
    by_book: dict[str, list[float]] = {}
    for row in rows:
        if str(row.get("market") or "").strip().lower() != market:
            continue
        try:
            line = float(row.get("line"))
        except (TypeError, ValueError):
            line = 0.5
        if abs(line - 0.5) > 1e-6:
            continue

        over = _probability(row, "over")
        under = _probability(row, "under")
        if over is None or under is None or over + under <= 0:
            continue
        fair = over / (over + under)
        book = str(row.get("book") or row.get("source") or "unknown").strip().lower()
        by_book.setdefault(book, []).append(fair)

    if not by_book:
        return None
    values = [median(probs) for probs in by_book.values() if probs]
    if not values:
        return None
    return float(median(values)), len(values)


def _probability(row: Mapping[str, Any], side: str) -> float | None:
    direct = row.get(f"{side}_implied_prob")
    try:
        if direct is not None:
            value = float(direct)
            if 0 < value < 1:
                return value
    except (TypeError, ValueError):
        pass

    price = row.get(f"{side}_price")
    try:
        odds = int(float(price))
    except (TypeError, ValueError):
        return None
    if odds == 0:
        return None
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def _anytime_td_scoring_factor(position: str, score) -> float | None:
    if position == "QB":
        return score("rush_td")
    if position in {"WR", "TE"}:
        return score("rec_td")
    if position in {"RB", "FB"}:
        rush = score("rush_td")
        receiving = score("rec_td")
        if abs(rush - receiving) <= 1e-9:
            return rush
        return None
    return None


def _is_alt(row: Mapping[str, Any]) -> bool:
    key = str(row.get("market_key") or "").strip().lower()
    return "alternate" in key or "milestone" in key


def _event_key(row: Mapping[str, Any]) -> str:
    event_id = str(row.get("event_id") or "").strip()
    if event_id:
        return event_id
    return "|".join(
        (
            str(row.get("commence_time") or "").strip(),
            str(row.get("away_team") or "").strip().lower(),
            str(row.get("home_team") or "").strip().lower(),
        )
    )


def _normalize_name(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", text)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
