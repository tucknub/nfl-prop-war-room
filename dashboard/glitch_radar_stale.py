from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


DFS_REFERENCE_BOOKS = {
    "betr",
    "draftkings pick6",
    "pick6",
    "prizepicks",
    "sleeper",
    "underdog",
}


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


def _norm_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def canonical_player_label(value: object) -> str:
    """Normalize a feed player label without inventing roster identity.

    Current ParlayAPI docs expose a canonical player field, but this also tolerates
    older outcome-like labels that may end in `Over` or `Under`.
    """
    text = _norm_text(value)
    lowered = text.casefold()
    for suffix in (" over", " under"):
        if lowered.endswith(suffix):
            text = text[: -len(suffix)].rstrip()
            break
    return text


def _player_key(value: object) -> str:
    return canonical_player_label(value).casefold()


def _event_signature(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        _norm_text(row.get("commence_time")),
        _norm_text(row.get("away_team")).casefold(),
        _norm_text(row.get("home_team")).casefold(),
    )


def _same_line(left: object, right: object) -> bool:
    a = _as_float(left)
    b = _as_float(right)
    return a is not None and b is not None and abs(a - b) < 1e-9


def _matches_alert(row: dict[str, Any], alert: dict[str, Any]) -> bool:
    return (
        _event_signature(row) == _event_signature(alert)
        and _player_key(row.get("player")) == _player_key(alert.get("player"))
        and _norm_text(row.get("market")).casefold() == _norm_text(alert.get("market")).casefold()
        and _same_line(row.get("line"), alert.get("line"))
    )


def _is_dfs_reference(book: object) -> bool:
    return _norm_text(book).casefold() in DFS_REFERENCE_BOOKS


def _implied_probability(american_odds: int | None) -> float | None:
    if american_odds in (None, 0):
        return None
    odds = int(american_odds)
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def _best_price_peer(peers: list[dict[str, Any]], side: str) -> dict[str, Any] | None:
    priced = []
    field = f"{side}_price"
    for peer in peers:
        price = _as_int(peer.get(field))
        if price in (None, 0):
            continue
        priced.append((price, peer))
    if not priced:
        return None
    # For the same side/line, the numerically larger American price is always better
    # for the bettor: +120 > +105 > -105 > -120.
    return max(priced, key=lambda item: item[0])[1]


def _comparison(stale_price: object, peer: dict[str, Any] | None, side: str) -> dict[str, Any] | None:
    stale = _as_int(stale_price)
    if stale in (None, 0) or peer is None:
        return None
    peer_price = _as_int(peer.get(f"{side}_price"))
    if peer_price in (None, 0):
        return None
    stale_prob = _implied_probability(stale)
    peer_prob = _implied_probability(peer_price)
    if stale_prob is None or peer_prob is None:
        return None
    if stale > peer_price:
        status = "stale_better"
    elif stale < peer_price:
        status = "peer_better"
    else:
        status = "same"
    return {
        "status": status,
        "stale_price": stale,
        "peer_book": peer.get("book"),
        "peer_price": peer_price,
        "peer_age_seconds": _as_float(peer.get("age_seconds")),
        "implied_probability_gap_points": abs(stale_prob - peer_prob) * 100,
    }


def enrich_stale_alerts(
    alerts: Iterable[dict[str, Any]],
    rows: Iterable[dict[str, Any]],
    *,
    fresh_peer_seconds: float = 180,
) -> list[dict[str, Any]]:
    """Attach fresh comparable prices to stale alerts.

    DFS pick'em apps remain useful as movement/freshness context, but their default
    midpoint pricing is not treated as an apples-to-apples sportsbook price. An alert
    is retained only when at least one fresh sportsbook/exchange price peer exists.
    """
    all_rows = list(rows)
    enriched: list[dict[str, Any]] = []
    for source_alert in alerts:
        alert = dict(source_alert)
        stale_book = _norm_text(alert.get("book")).casefold()
        matching = [row for row in all_rows if _matches_alert(row, alert)]
        fresh = [
            row
            for row in matching
            if _as_float(row.get("age_seconds")) is not None
            and float(row.get("age_seconds")) <= fresh_peer_seconds
            and _norm_text(row.get("book")).casefold() != stale_book
        ]
        if not fresh:
            continue

        price_peers = [row for row in fresh if not _is_dfs_reference(row.get("book"))]
        dfs_peers = [row for row in fresh if _is_dfs_reference(row.get("book"))]
        if not price_peers:
            continue

        price_peers.sort(key=lambda row: float(row.get("age_seconds") or 1e12))
        freshest = price_peers[0]
        best_over = _best_price_peer(price_peers, "over")
        best_under = _best_price_peer(price_peers, "under")

        alert["fresh_peer_quotes"] = [
            {
                "book": row.get("book"),
                "over_price": _as_int(row.get("over_price")),
                "under_price": _as_int(row.get("under_price")),
                "age_seconds": _as_float(row.get("age_seconds")),
            }
            for row in price_peers
        ]
        alert["fresh_peer_books"] = sorted({_norm_text(row.get("book")) for row in price_peers if row.get("book")})
        alert["dfs_fresh_peer_books"] = sorted({_norm_text(row.get("book")) for row in dfs_peers if row.get("book")})
        alert["freshest_peer_book"] = freshest.get("book")
        alert["freshest_peer_over_price"] = _as_int(freshest.get("over_price"))
        alert["freshest_peer_under_price"] = _as_int(freshest.get("under_price"))
        alert["freshest_peer_age_seconds"] = _as_float(freshest.get("age_seconds"))
        alert["over_comparison"] = _comparison(alert.get("over_price"), best_over, "over")
        alert["under_comparison"] = _comparison(alert.get("under_price"), best_under, "under")
        enriched.append(alert)

    return sorted(enriched, key=lambda row: float(row.get("age_seconds") or 0), reverse=True)


def coverage_quality(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Return player-identity counts that are meaningful for cross-book comparison.

    Raw unique labels can be inflated by one-off source labels. The cross-book counts
    are a better headline for a comparison scanner because the identity was observed
    at two or more independent books for at least one current event.
    """
    player_rows = [
        row
        for row in rows
        if _player_key(row.get("player"))
        and _norm_text(row.get("market_key")).casefold().startswith("player_")
    ]

    raw_players = {_player_key(row.get("player")) for row in player_rows}
    books_by_player: dict[str, set[str]] = defaultdict(set)
    books_by_player_event: dict[tuple[tuple[str, str, str], str], set[str]] = defaultdict(set)
    player_events: set[tuple[tuple[str, str, str], str]] = set()

    for row in player_rows:
        player = _player_key(row.get("player"))
        book = _norm_text(row.get("book")).casefold()
        event_player = (_event_signature(row), player)
        player_events.add(event_player)
        if book:
            books_by_player[player].add(book)
            books_by_player_event[event_player].add(book)

    return {
        "raw_player_labels": len(raw_players),
        "player_event_identities": len(player_events),
        "cross_book_players": sum(1 for books in books_by_player.values() if len(books) >= 2),
        "cross_book_player_events": sum(1 for books in books_by_player_event.values() if len(books) >= 2),
    }


__all__ = [
    "canonical_player_label",
    "coverage_quality",
    "enrich_stale_alerts",
]
