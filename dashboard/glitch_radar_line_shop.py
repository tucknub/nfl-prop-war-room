from __future__ import annotations

from collections import defaultdict
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

# Used only to rank threshold advantages across unlike market units.
MARKET_GAP_SCALE: dict[str, float] = {
    "passing_yards": 10.0,
    "rushing_yards": 5.0,
    "receiving_yards": 5.0,
    "receptions": 1.0,
    "pass_completions": 1.0,
    "pass_attempts": 2.0,
    "longest_reception": 3.0,
    "passing_tds": 0.5,
    "rushing_tds": 0.5,
    "receiving_tds": 0.5,
    "interceptions": 0.5,
}


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


def _is_dfs(book: object) -> bool:
    return _norm(book).casefold() in DFS_REFERENCE_BOOKS


def _event_key(row: dict[str, Any]) -> tuple[str, str, str]:
    commence = _norm(row.get("commence_time"))
    away = _norm(row.get("away_team")).casefold()
    home = _norm(row.get("home_team")).casefold()
    if commence or away or home:
        return (commence, away, home)
    return (_norm(row.get("event_id")), "", "")


def _family_key(row: dict[str, Any]) -> tuple:
    return (
        _event_key(row),
        canonical_player_label(row.get("player")).casefold(),
        _norm(row.get("market")).casefold(),
    )


def build_line_shop_watches(
    rows: Iterable[dict[str, Any]],
    *,
    max_price_cost_points: float = 3.0,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Find easier thresholds at roughly comparable prices across real books.

    For OVER, a lower threshold is better. For UNDER, a higher threshold is better.
    A candidate is retained when the easier threshold is available at one of the owner's
    books and its implied-probability cost is no more than `max_price_cost_points` worse
    than the comparison price. DFS pick'em midpoint pricing is excluded.

    This is line-shopping context, not an EV estimate or sportsbook-error classification.
    """
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for source in rows:
        row = dict(source)
        if _is_dfs(row.get("book")):
            continue
        if _as_float(row.get("line")) is None:
            continue
        if not canonical_player_label(row.get("player")) or not _norm(row.get("market")):
            continue
        groups[_family_key(row)].append(row)

    best_by_candidate: dict[tuple, dict[str, Any]] = {}
    max_cost = float(max_price_cost_points) / 100.0

    for group in groups.values():
        books = {_norm(row.get("book")).casefold() for row in group if row.get("book")}
        if len(books) < 2:
            continue

        for candidate in group:
            if not is_user_book(candidate.get("book")):
                continue
            candidate_line = _as_float(candidate.get("line"))
            if candidate_line is None:
                continue

            for side in ("over", "under"):
                candidate_price = _as_int(candidate.get(f"{side}_price"))
                if candidate_price in (None, 0):
                    continue
                candidate_prob = _implied(int(candidate_price))

                for peer in group:
                    if _norm(peer.get("book")).casefold() == _norm(candidate.get("book")).casefold():
                        continue
                    peer_line = _as_float(peer.get("line"))
                    peer_price = _as_int(peer.get(f"{side}_price"))
                    if peer_line is None or peer_price in (None, 0) or abs(peer_line - candidate_line) < 1e-9:
                        continue

                    threshold_better = candidate_line < peer_line if side == "over" else candidate_line > peer_line
                    if not threshold_better:
                        continue

                    peer_prob = _implied(int(peer_price))
                    price_cost = candidate_prob - peer_prob
                    if price_cost > max_cost:
                        continue

                    gap = abs(candidate_line - peer_line)
                    market = _norm(candidate.get("market")).casefold()
                    scale = MARKET_GAP_SCALE.get(market, 1.0)
                    normalized_gap = gap / scale if scale > 0 else gap
                    # Reward bigger threshold advantages and prices that are no worse than the peer.
                    score = normalized_gap + max(0.0, -price_cost * 10.0)
                    key = (
                        _event_key(candidate),
                        canonical_player_label(candidate.get("player")).casefold(),
                        market,
                        _norm(candidate.get("book")).casefold(),
                        side,
                    )
                    watch = {
                        "type": "line_shop_watch",
                        "book": candidate.get("book"),
                        "peer_book": peer.get("book"),
                        "event_id": candidate.get("event_id"),
                        "away_team": candidate.get("away_team"),
                        "home_team": candidate.get("home_team"),
                        "commence_time": candidate.get("commence_time"),
                        "player": canonical_player_label(candidate.get("player")),
                        "market": candidate.get("market"),
                        "market_label": candidate.get("market_label"),
                        "side": side,
                        "book_line": candidate_line,
                        "book_price": candidate_price,
                        "peer_line": peer_line,
                        "peer_price": peer_price,
                        "line_advantage": gap,
                        "price_cost_points": price_cost * 100.0,
                        "normalized_line_advantage": normalized_gap,
                        "score": score,
                        "book_market_key": candidate.get("market_key"),
                        "peer_market_key": peer.get("market_key"),
                    }
                    current = best_by_candidate.get(key)
                    if current is None or float(watch["score"]) > float(current.get("score") or 0):
                        best_by_candidate[key] = watch

    results = list(best_by_candidate.values())
    results.sort(
        key=lambda row: (
            float(row.get("score") or 0),
            float(row.get("normalized_line_advantage") or 0),
            -float(row.get("price_cost_points") or 0),
        ),
        reverse=True,
    )
    return results[: max(0, int(limit))]


__all__ = ["build_line_shop_watches"]
