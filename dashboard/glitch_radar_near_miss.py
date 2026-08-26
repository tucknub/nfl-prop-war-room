from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Iterable

try:
    from glitch_radar_books import is_user_book
    from glitch_radar_stale import canonical_player_label
except ImportError:  # package import path used by pytest
    from dashboard.glitch_radar_books import is_user_book
    from dashboard.glitch_radar_stale import canonical_player_label

DFS_REFERENCE_BOOKS = {
    "betr",
    "draftkings pick6",
    "pick6",
    "prizepicks",
    "sleeper",
    "underdog",
}

GLITCH_RELATIVE_PROB_THRESHOLD = 0.25
GLITCH_PAYOUT_MULTIPLE_THRESHOLD = 1.60


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def _as_float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _decimal(odds: int) -> float:
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))


def _implied(odds: int) -> float:
    return 1 / _decimal(odds)


def _event_key(row: dict[str, Any]) -> tuple[str, str, str]:
    """Use the normalized matchup signature for cross-book diagnostic grouping.

    The deep feed has had more than one documented event-id field over time. Team names and
    commence time are already normalized on prop rows and are the safer compatibility key for
    this non-settlement diagnostic surface.
    """
    commence = _norm(row.get("commence_time"))
    away = _norm(row.get("away_team")).casefold()
    home = _norm(row.get("home_team")).casefold()
    if commence or away or home:
        return (commence, away, home)
    event_id = _norm(row.get("canonical_event_id") or row.get("event_id"))
    return (event_id, "", "")


def _exact_key(row: dict[str, Any]) -> tuple:
    return (
        _event_key(row),
        canonical_player_label(row.get("player")).casefold(),
        _norm(row.get("market")).casefold(),
        _as_float(row.get("line")),
    )


def _is_dfs(book: object) -> bool:
    return _norm(book).casefold() in DFS_REFERENCE_BOOKS


def build_near_miss_anomalies(
    rows: Iterable[dict[str, Any]],
    *,
    min_books: int = 2,
    min_relative_prob_deviation: float = 0.01,
    min_payout_multiple: float = 1.02,
    limit: int = 30,
) -> list[dict[str, Any]]:
    """Rank the largest same-line discrepancies below the true glitch threshold.

    This is a diagnostic surface only. It intentionally excludes rows already large enough
    to satisfy the main glitch detector and excludes DFS pick'em midpoint pricing. Unlike the
    strict glitch detector, two real books are enough for a diagnostic comparison.
    """
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if _as_float(row.get("line")) is None:
            continue
        if not canonical_player_label(row.get("player")) or not _norm(row.get("market")):
            continue
        if _is_dfs(row.get("book")):
            continue
        groups[_exact_key(row)].append(dict(row))

    results: list[dict[str, Any]] = []
    for group in groups.values():
        distinct_books = {_norm(row.get("book")).casefold() for row in group if row.get("book")}
        if len(distinct_books) < min_books:
            continue
        for side in ("over", "under"):
            field = f"{side}_price"
            priced = [(row, _as_int(row.get(field))) for row in group]
            priced = [(row, price) for row, price in priced if price not in (None, 0)]
            priced_books = {_norm(row.get("book")).casefold() for row, _ in priced if row.get("book")}
            if len(priced_books) < min_books:
                continue
            probabilities = [_implied(int(price)) for _, price in priced]
            consensus = median(probabilities)
            peer_profit_median = median([_decimal(int(price)) - 1 for _, price in priced])
            for row, price in priced:
                if not is_user_book(row.get("book")):
                    continue
                own_prob = _implied(int(price))
                relative = abs(own_prob - consensus) / consensus if consensus else 0.0
                own_profit = _decimal(int(price)) - 1
                payout_multiple = own_profit / peer_profit_median if peer_profit_median > 0 else 1.0
                sign_mismatch = (
                    price > 0 and sum(other < 0 for _, other in priced if other != price) >= 2
                ) or (
                    price < 0 and sum(other > 0 for _, other in priced if other != price) >= 2
                )
                if sign_mismatch:
                    continue
                if relative >= GLITCH_RELATIVE_PROB_THRESHOLD or payout_multiple >= GLITCH_PAYOUT_MULTIPLE_THRESHOLD:
                    continue
                if relative < min_relative_prob_deviation and payout_multiple < min_payout_multiple:
                    continue
                proximity = max(
                    relative / GLITCH_RELATIVE_PROB_THRESHOLD,
                    payout_multiple / GLITCH_PAYOUT_MULTIPLE_THRESHOLD if payout_multiple > 1 else 0,
                )
                results.append(
                    {
                        "type": "prop_near_miss",
                        "book": row.get("book"),
                        "event_id": row.get("event_id"),
                        "away_team": row.get("away_team"),
                        "home_team": row.get("home_team"),
                        "commence_time": row.get("commence_time"),
                        "player": canonical_player_label(row.get("player")),
                        "market": row.get("market"),
                        "market_label": row.get("market_label"),
                        "line": _as_float(row.get("line")),
                        "side": side,
                        "price": price,
                        "num_books": len(priced_books),
                        "peer_median_implied_prob_pct": consensus * 100,
                        "book_implied_prob_pct": own_prob * 100,
                        "relative_prob_deviation_pct": relative * 100,
                        "payout_multiple_vs_peers": payout_multiple,
                        "glitch_threshold_proximity_pct": min(99.9, proximity * 100),
                        "peer_books": sorted(
                            {
                                _norm(peer.get("book"))
                                for peer, _ in priced
                                if peer.get("book") and _norm(peer.get("book")).casefold() != _norm(row.get("book")).casefold()
                            }
                        ),
                    }
                )

    results.sort(
        key=lambda row: (
            float(row.get("glitch_threshold_proximity_pct") or 0),
            float(row.get("relative_prob_deviation_pct") or 0),
            int(row.get("num_books") or 0),
        ),
        reverse=True,
    )
    return results[: max(0, int(limit))]


__all__ = ["build_near_miss_anomalies"]
