from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Any

import httpx

try:
    from glitch_radar_enrich import enrich_ev_markets
except ImportError:  # package import path used by pytest
    from dashboard.glitch_radar_enrich import enrich_ev_markets

BASE = "https://parlay-api.com"
SPORT = "americanfootball_nfl"


@dataclass(frozen=True)
class Quote:
    book: str
    event: str
    market: str
    participant: str = ""
    side: str = ""
    threshold: float | None = None
    odds_american: int = 0
    timestamp: str = ""

    def identity(self) -> tuple:
        return (
            self.event.strip().lower(),
            self.market.strip().lower(),
            self.participant.strip().lower(),
            self.side.strip().lower(),
            self.threshold,
        )


def american_to_decimal(odds: int) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))


def decimal_to_american(decimal: float) -> int:
    if decimal <= 1:
        raise ValueError("Decimal odds must be greater than one")
    if decimal >= 2:
        return round((decimal - 1) * 100)
    return round(-100 / (decimal - 1))


def implied_probability(odds: int) -> float:
    return 1 / american_to_decimal(odds)


def evaluate_profit_boost(odds: int, fair_odds: int, boost_pct: float, stake: float) -> dict[str, float | int]:
    original_decimal = american_to_decimal(odds)
    boosted_decimal = 1 + (original_decimal - 1) * (1 + boost_pct)
    boosted_odds = decimal_to_american(boosted_decimal)
    fair_prob = implied_probability(fair_odds)
    ev_pct = fair_prob * boosted_decimal - 1
    return {
        "boosted_odds": boosted_odds,
        "ev_pct": ev_pct,
        "expected_value_dollars": stake * ev_pct,
    }


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    response = httpx.get(
        f"{BASE}{path}",
        params=params or {},
        timeout=25.0,
        follow_redirects=True,
        headers={"User-Agent": "PropWar-Glitch-Radar/1.0"},
    )
    if response.status_code == 429:
        raise RuntimeError("No-key feed rate limit reached. Try again after the current hourly window resets.")
    response.raise_for_status()
    return response.json()


def _safe(label: str, fn) -> tuple[Any, str | None]:
    try:
        return fn(), None
    except Exception as exc:
        return None, f"{label}: {exc}"


def _opportunities(payload: Any) -> list[dict]:
    if isinstance(payload, dict):
        rows = payload.get("opportunities")
        return rows if isinstance(rows, list) else []
    return []


def _events(payload: Any) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("events", "data", "odds", "result", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def parse_odds(payload: Any) -> list[Quote]:
    stamp = datetime.now(timezone.utc).isoformat()
    quotes: list[Quote] = []
    for event in _events(payload):
        home = str(event.get("home_team") or "")
        away = str(event.get("away_team") or "")
        event_name = f"{away} @ {home}".strip(" @")
        for book in event.get("bookmakers", []) or []:
            book_name = str(book.get("title") or book.get("key") or "Unknown")
            for market in book.get("markets", []) or []:
                market_key = str(market.get("key") or "").lower()
                for outcome in market.get("outcomes", []) or []:
                    try:
                        price = int(float(outcome.get("price")))
                    except (TypeError, ValueError):
                        continue
                    name = str(outcome.get("name") or "")
                    point = outcome.get("point")
                    try:
                        threshold = float(point) if point is not None else None
                    except (TypeError, ValueError):
                        threshold = None

                    if market_key in {"h2h", "moneyline"}:
                        canonical_market = "moneyline"
                        participant = ""
                        side = "home" if name.lower() == home.lower() else "away" if name.lower() == away.lower() else name.lower()
                    elif market_key in {"totals", "total"}:
                        canonical_market = "game_total"
                        participant = ""
                        side = name.lower()
                    elif market_key in {"spreads", "spread"}:
                        canonical_market = "spread"
                        participant = name
                        side = "home" if name.lower() == home.lower() else "away" if name.lower() == away.lower() else name.lower()
                    else:
                        canonical_market = market_key
                        participant = ""
                        side = name.lower()

                    quotes.append(
                        Quote(
                            book=book_name,
                            event=event_name,
                            market=canonical_market,
                            participant=participant,
                            side=side,
                            threshold=threshold,
                            odds_american=price,
                            timestamp=stamp,
                        )
                    )
    return quotes


def _pack_quote(quote: Quote) -> dict[str, Any]:
    return {
        "book": quote.book,
        "event": quote.event,
        "market": quote.market,
        "participant": quote.participant,
        "side": quote.side,
        "threshold": quote.threshold,
        "odds_american": quote.odds_american,
        "timestamp": quote.timestamp,
    }


def detect_price_outliers(quotes: list[Quote], min_books: int = 3) -> list[dict[str, Any]]:
    groups: dict[tuple, list[Quote]] = {}
    for quote in quotes:
        groups.setdefault(quote.identity(), []).append(quote)

    alerts: list[dict[str, Any]] = []
    for group in groups.values():
        if len(group) < min_books:
            continue
        probabilities = [implied_probability(q.odds_american) for q in group]
        consensus = median(probabilities)
        for quote in group:
            own_probability = implied_probability(quote.odds_american)
            relative_deviation = abs(own_probability - consensus) / consensus if consensus else 0
            peer_profits = [american_to_decimal(q.odds_american) - 1 for q in group if q is not quote]
            peer_profit = median(peer_profits) if peer_profits else 0
            own_profit = american_to_decimal(quote.odds_american) - 1
            payout_ratio = own_profit / peer_profit if peer_profit > 0 else 1
            raw_sign_mismatch = (
                quote.odds_american > 0 and sum(q.odds_american < 0 for q in group) >= 2
            ) or (
                quote.odds_american < 0 and sum(q.odds_american > 0 for q in group) >= 2
            )
            absolute_prob_gap = abs(own_probability - consensus)
            # American odds cross zero around an even-money market. A +101 quote
            # beside -105 peers is normal market dispersion, not a pricing error.
            # Sign mismatch only becomes meaningful when the implied-probability
            # gap is large enough to matter.
            sign_mismatch = raw_sign_mismatch and absolute_prob_gap >= 0.10
            if relative_deviation >= 0.40 or payout_ratio >= 1.75 or sign_mismatch:
                alerts.append(
                    {
                        "type": "price_outlier",
                        "severity": (
                            "P0"
                            if payout_ratio >= 3
                            or (sign_mismatch and absolute_prob_gap >= 0.20)
                            else "P1"
                        ),
                        "quote": _pack_quote(quote),
                        "consensus_implied_prob": consensus,
                        "relative_prob_deviation": relative_deviation,
                        "absolute_prob_gap_points": absolute_prob_gap * 100,
                        "profit_multiple_vs_peers": payout_ratio,
                        "sign_mismatch": sign_mismatch,
                    }
                )
    return alerts


def build_snapshot() -> dict[str, Any]:
    errors: list[str] = []

    odds, err = _safe("odds", lambda: _get(f"/v1/try/{SPORT}/odds"))
    if err:
        errors.append(err)
    arbitrage, err = _safe("arbitrage", lambda: _get(f"/v1/try/{SPORT}/arbitrage"))
    if err:
        errors.append(err)
    middles, err = _safe("middles", lambda: _get(f"/v1/try/{SPORT}/middles"))
    if err:
        errors.append(err)
    ev, err = _safe("ev", lambda: _get(f"/v1/try/{SPORT}/ev"))
    if err:
        errors.append(err)
    command_center, err = _safe(
        "command_center",
        lambda: _get("/live/api/command_center", {"sport": SPORT, "limit": 50}),
    )
    if err:
        errors.append(err)

    quotes = parse_odds(odds or {})
    packed_quotes = [_pack_quote(q) for q in quotes]
    alerts = detect_price_outliers(quotes)
    books = sorted({q.book for q in quotes})
    ev_rows = enrich_ev_markets(_opportunities(ev), packed_quotes)

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "quotes": packed_quotes,
        "alerts": alerts,
        "arbs": _opportunities(arbitrage),
        "middles": _opportunities(middles),
        "ev": ev_rows,
        "books": books,
        "command_center": command_center or {},
        "demo_remaining_hour": odds.get("demo_remaining_hour") if isinstance(odds, dict) else None,
        "errors": errors,
    }
