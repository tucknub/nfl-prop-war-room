from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

try:
    from glitch_radar_books import canonical_book, is_user_book
    from glitch_radar_live import implied_probability
    from glitch_radar_present import expected_ev_pct
except ImportError:
    from dashboard.glitch_radar_books import canonical_book, is_user_book
    from dashboard.glitch_radar_live import implied_probability
    from dashboard.glitch_radar_present import expected_ev_pct


BET = "BET"
WATCH = "WATCH"
PASS = "PASS"


@dataclass(frozen=True)
class RadarAction:
    action: str
    reason: str
    edge_points: float | None = None
    ev_pct: float | None = None


def glitch_action(alert: Mapping[str, Any]) -> RadarAction:
    quote = alert.get("quote") if isinstance(alert, Mapping) else {}
    quote = quote if isinstance(quote, Mapping) else {}
    try:
        price = int(float(quote.get("odds_american")))
        own_prob = implied_probability(price)
        consensus = float(alert.get("consensus_implied_prob"))
    except (TypeError, ValueError, ZeroDivisionError):
        return RadarAction(WATCH, "The anomaly is real enough to monitor, but the price edge could not be quantified.")

    edge_points = (consensus - own_prob) * 100
    severity = str(alert.get("severity") or "P2").upper()

    # Positive edge means this book is offering a lower implied probability / better payout
    # than peer consensus. Negative edge is an outlier in the wrong direction for the bettor.
    if edge_points <= 0:
        return RadarAction(
            PASS,
            "The book is off market in the wrong direction; the unusual price is worse than peer consensus.",
            edge_points=edge_points,
        )
    if edge_points >= 3.0 and severity in {"P0", "P1"}:
        return RadarAction(
            BET,
            "The flagged book is materially better than peer consensus, not merely different from it.",
            edge_points=edge_points,
        )
    return RadarAction(
        WATCH,
        "The flagged book is better than consensus, but the quantified gap is not strong enough for an automatic BET label.",
        edge_points=edge_points,
    )


def ev_action(row: Mapping[str, Any]) -> RadarAction:
    ev = expected_ev_pct(row.get("price"), row.get("fair_prob_pct"))
    if ev is None:
        return RadarAction(WATCH, "Fair-value inputs are incomplete, so the price should be monitored rather than acted on.", ev_pct=None)
    if ev >= 5.0:
        return RadarAction(BET, "Estimated EV is at least +5% versus the current fair estimate.", ev_pct=ev)
    if ev >= 1.0:
        return RadarAction(WATCH, "The price is positive EV, but below the +5% BET threshold.", ev_pct=ev)
    return RadarAction(PASS, "The estimated edge is below +1%.", ev_pct=ev)


def _same_quote_identity(a: Mapping[str, Any], b: Mapping[str, Any]) -> bool:
    def text(row: Mapping[str, Any], key: str) -> str:
        return str(row.get(key) or "").strip().casefold()

    def threshold(row: Mapping[str, Any]) -> object:
        value = row.get("threshold")
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return str(value).strip()

    return (
        text(a, "event"),
        text(a, "market"),
        text(a, "participant"),
        text(a, "side"),
        threshold(a),
    ) == (
        text(b, "event"),
        text(b, "market"),
        text(b, "participant"),
        text(b, "side"),
        threshold(b),
    )


def peer_prices_for_alert(
    alert: Mapping[str, Any],
    quotes: Iterable[Mapping[str, Any]],
    *,
    user_books_only: bool = True,
) -> tuple[dict[str, Any], ...]:
    flagged = alert.get("quote") if isinstance(alert, Mapping) else {}
    if not isinstance(flagged, Mapping):
        return ()

    flagged_book = canonical_book(flagged.get("book"))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in quotes:
        if not isinstance(raw, Mapping) or not _same_quote_identity(flagged, raw):
            continue
        book = canonical_book(raw.get("book"))
        if not book or book == flagged_book or book in seen:
            continue
        if user_books_only and not is_user_book(book):
            continue
        try:
            price = int(float(raw.get("odds_american")))
        except (TypeError, ValueError):
            continue
        seen.add(book)
        rows.append({"book": book, "price": price})

    rows.sort(key=lambda row: row["book"].casefold())
    return tuple(rows)


def peer_price_gap_range(
    flagged_price: object,
    peers: Iterable[Mapping[str, Any]],
) -> tuple[int, int] | None:
    try:
        flagged = int(float(flagged_price))
    except (TypeError, ValueError):
        return None

    gaps: list[int] = []
    for row in peers:
        try:
            peer = int(float(row.get("price")))
        except (TypeError, ValueError):
            continue
        gap = flagged - peer
        if gap > 0:
            gaps.append(gap)
    if not gaps:
        return None
    return min(gaps), max(gaps)


__all__ = [
    "BET",
    "WATCH",
    "PASS",
    "RadarAction",
    "ev_action",
    "glitch_action",
    "peer_price_gap_range",
    "peer_prices_for_alert",
]
