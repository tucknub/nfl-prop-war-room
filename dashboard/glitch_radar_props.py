from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Iterable

import httpx

try:
    from glitch_radar_books import canonical_book, is_user_book, USER_BOOKS
except ImportError:  # package import path used by pytest
    from dashboard.glitch_radar_books import canonical_book, is_user_book, USER_BOOKS

BASE = "https://parlay-api.com"
SPORT = "americanfootball_nfl"

# One /props request returns all books/markets and costs 3 free-tier credits.
PROP_CREDITS_PER_SCAN = 3

# Market families we care about first. The API can return additional markets;
# those rows are preserved and shown in coverage, but detectors use canonical families.
MARKET_ALIASES: dict[str, str] = {
    "player_pass_yds": "passing_yards",
    "player_pass_yards": "passing_yards",
    "player_pass_yds_alternate": "passing_yards",
    "player_pass_yards_alternate": "passing_yards",
    "player_rush_yds": "rushing_yards",
    "player_rush_yards": "rushing_yards",
    "player_rush_yds_alternate": "rushing_yards",
    "player_rush_yards_alternate": "rushing_yards",
    "player_reception_yds": "receiving_yards",
    "player_rec_yds": "receiving_yards",
    "player_receiving_yards": "receiving_yards",
    "player_reception_yds_alternate": "receiving_yards",
    "player_rec_yds_alternate": "receiving_yards",
    "player_receiving_yards_alternate": "receiving_yards",
    "player_receptions": "receptions",
    "player_receptions_alternate": "receptions",
    "player_pass_tds": "passing_tds",
    "player_rush_tds": "rushing_tds",
    "player_reception_tds": "receiving_tds",
    "player_rec_tds": "receiving_tds",
    "player_anytime_td": "anytime_td",
    "player_first_td": "first_td",
    "player_1st_td": "first_td",
    "player_first_touchdown_scorer": "first_td",
    "player_longest_rec": "longest_reception",
    "player_longest_reception": "longest_reception",
    "player_pass_completions": "pass_completions",
    "player_pass_attempts": "pass_attempts",
    "player_pass_interceptions": "interceptions",
    "player_ints_thrown": "interceptions",
}

ALT_MARKET_TOKENS = ("alternate", "milestone")

# Material line gap thresholds. These are candidate thresholds, not automatic bets.
LINE_GAP_THRESHOLDS: dict[str, float] = {
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


def american_decimal(odds: int) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))


def implied_probability(odds: int) -> float:
    return 1 / american_decimal(odds)


def canonical_market(value: object) -> str:
    raw = str(value or "").strip().lower()
    if raw in MARKET_ALIASES:
        return MARKET_ALIASES[raw]
    # Normalize common alternate suffixes to the base family where possible.
    for suffix in ("_alternate", "_alts"):
        if raw.endswith(suffix):
            base = raw[: -len(suffix)]
            return MARKET_ALIASES.get(base, base.replace("player_", ""))
    return raw.replace("player_", "")


def is_alt_market(row: dict[str, Any]) -> bool:
    market = str(row.get("market_key") or "").lower()
    return any(token in market for token in ALT_MARKET_TOKENS)


def normalize_prop_row(row: dict[str, Any]) -> dict[str, Any]:
    book = canonical_book(row.get("source_title") or row.get("source") or row.get("book"))
    market_key = str(row.get("market_key") or row.get("market") or "").strip().lower()
    return {
        "event_id": row.get("event_id"),
        "commence_time": row.get("commence_time"),
        "home_team": row.get("home_team"),
        "away_team": row.get("away_team"),
        "book": book,
        "source": row.get("source"),
        "player": str(row.get("player_name") or row.get("player") or "").strip(),
        "market_key": market_key,
        "market": canonical_market(market_key),
        "market_label": row.get("market_label") or market_key.replace("_", " ").title(),
        "line": _as_float(row.get("line")),
        "over_price": _as_int(row.get("over_price")),
        "under_price": _as_int(row.get("under_price")),
        "over_implied_prob": _as_float(row.get("over_implied_prob")),
        "under_implied_prob": _as_float(row.get("under_implied_prob")),
        "snapshot_time": row.get("snapshot_time"),
        "age_seconds": _as_float(row.get("age_seconds")),
    }


def normalize_props(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = None
        for key in ("props", "data", "results", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
        if rows is None:
            rows = []
    else:
        rows = []
    return [normalize_prop_row(row) for row in rows if isinstance(row, dict)]


def fetch_full_props(api_key: str, *, max_age_sec: int = 120) -> list[dict[str, Any]]:
    """Fetch all current NFL props in one 3-credit call.

    The request intentionally does not limit bookmakers because peer/reference books improve
    anomaly detection. Actionable recommendations are filtered later to USER_BOOKS.
    """
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("ParlayAPI key is required for deep prop scans")
    response = httpx.get(
        f"{BASE}/v1/sports/{SPORT}/props",
        params={"limit": 10000},
        headers={"X-API-Key": key, "User-Agent": "PropWar-Glitch-Radar/2.0"},
        timeout=35.0,
        follow_redirects=True,
    )
    if response.status_code == 401:
        raise RuntimeError("ParlayAPI key was rejected")
    if response.status_code == 402:
        raise RuntimeError("ParlayAPI free credits are exhausted for this billing month")
    if response.status_code == 429:
        raise RuntimeError("ParlayAPI rate limit reached")
    if 500 <= response.status_code <= 599:
        raise RuntimeError(
            f"ParlayAPI player-prop feed is temporarily unavailable (HTTP {response.status_code}). "
            "PropWar did not use stale or undated quotes."
        )
    response.raise_for_status()
    rows = normalize_props(response.json())
    fresh_rows = []
    for row in rows:
        age_seconds = _as_float(row.get("age_seconds"))
        if age_seconds is None:
            continue
        if 0 <= age_seconds <= float(max_age_sec):
            fresh_rows.append(row)
    return fresh_rows


def _event_key(row: dict[str, Any]) -> str:
    event_id = str(row.get("event_id") or "").strip()
    if event_id:
        return event_id
    return f"{str(row.get('away_team') or '').lower()}@{str(row.get('home_team') or '').lower()}"


def _exact_market_key(row: dict[str, Any]) -> tuple:
    return (
        _event_key(row),
        str(row.get("player") or "").lower(),
        str(row.get("market") or "").lower(),
        row.get("line"),
    )


def _family_key(row: dict[str, Any]) -> tuple:
    return (
        _event_key(row),
        str(row.get("player") or "").lower(),
        str(row.get("market") or "").lower(),
    )


def _side_price(row: dict[str, Any], side: str) -> int | None:
    return _as_int(row.get(f"{side}_price"))


def detect_prop_price_outliers(
    rows: Iterable[dict[str, Any]],
    *,
    min_books: int = 3,
    relative_prob_threshold: float = 0.25,
    payout_multiple_threshold: float = 1.60,
) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("line") is None or not row.get("player") or not row.get("market"):
            continue
        groups[_exact_market_key(row)].append(row)

    alerts: list[dict[str, Any]] = []
    for group in groups.values():
        distinct_books = {row.get("book") for row in group if row.get("book")}
        if len(distinct_books) < min_books:
            continue
        for side in ("over", "under"):
            priced = [(row, _side_price(row, side)) for row in group]
            priced = [(row, price) for row, price in priced if price not in (None, 0)]
            if len({row.get("book") for row, _ in priced}) < min_books:
                continue
            probabilities = [implied_probability(price) for _, price in priced]
            consensus = median(probabilities)
            peer_profit_values = [american_decimal(price) - 1 for _, price in priced]
            peer_profit_median = median(peer_profit_values)
            for row, price in priced:
                own_prob = implied_probability(price)
                rel = abs(own_prob - consensus) / consensus if consensus else 0
                own_profit = american_decimal(price) - 1
                payout_ratio = own_profit / peer_profit_median if peer_profit_median > 0 else 1
                raw_sign_mismatch = (
                    price > 0 and sum(other < 0 for _, other in priced if other != price) >= 2
                ) or (
                    price < 0 and sum(other > 0 for _, other in priced if other != price) >= 2
                )
                absolute_prob_gap = abs(own_prob - consensus)
                # American odds cross zero around even money. A small +/-
                # crossing is ordinary market dispersion, not a pricing error.
                sign_mismatch = raw_sign_mismatch and absolute_prob_gap >= 0.10
                if rel >= relative_prob_threshold or payout_ratio >= payout_multiple_threshold or sign_mismatch:
                    alerts.append(
                        {
                            "type": "prop_price_outlier",
                            "severity": (
                                "P0"
                                if payout_ratio >= 2.5
                                or (sign_mismatch and absolute_prob_gap >= 0.20)
                                else "P1"
                            ),
                            "book": row.get("book"),
                            "event_id": row.get("event_id"),
                            "away_team": row.get("away_team"),
                            "home_team": row.get("home_team"),
                            "commence_time": row.get("commence_time"),
                            "player": row.get("player"),
                            "market": row.get("market"),
                            "market_label": row.get("market_label"),
                            "line": row.get("line"),
                            "side": side,
                            "price": price,
                            "peer_median_implied_prob": consensus,
                            "relative_prob_deviation": rel,
                            "absolute_prob_gap_points": absolute_prob_gap * 100,
                            "profit_multiple_vs_peers": payout_ratio,
                            "sign_mismatch": sign_mismatch,
                            "actionable": is_user_book(row.get("book")),
                        }
                    )
    return sorted(
        alerts,
        key=lambda row: (
            row.get("severity") != "P0",
            not row.get("actionable", False),
            -(float(row.get("profit_multiple_vs_peers") or 0)),
        ),
    )


def detect_line_gaps(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find materially different prop thresholds across the owner's books."""
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not is_user_book(row.get("book")) or row.get("line") is None:
            continue
        groups[_family_key(row)].append(row)

    alerts: list[dict[str, Any]] = []
    for group in groups.values():
        market = str(group[0].get("market") or "")
        threshold = LINE_GAP_THRESHOLDS.get(market)
        if threshold is None:
            continue
        distinct_books = {row.get("book") for row in group}
        if len(distinct_books) < 2:
            continue
        low = min(group, key=lambda row: float(row.get("line")))
        high = max(group, key=lambda row: float(row.get("line")))
        gap = float(high.get("line")) - float(low.get("line"))
        if gap < threshold or low.get("book") == high.get("book"):
            continue
        alerts.append(
            {
                "type": "prop_line_gap",
                "severity": "P1" if gap >= threshold * 2 else "P2",
                "away_team": low.get("away_team"),
                "home_team": low.get("home_team"),
                "commence_time": low.get("commence_time"),
                "player": low.get("player"),
                "market": market,
                "market_label": low.get("market_label"),
                "low_book": low.get("book"),
                "low_line": low.get("line"),
                "low_over_price": low.get("over_price"),
                "low_under_price": low.get("under_price"),
                "high_book": high.get("book"),
                "high_line": high.get("line"),
                "high_over_price": high.get("over_price"),
                "high_under_price": high.get("under_price"),
                "line_gap": gap,
            }
        )
    return sorted(alerts, key=lambda row: float(row.get("line_gap") or 0), reverse=True)


def detect_ladder_violations(rows: Iterable[dict[str, Any]], *, tolerance: float = 0.015) -> list[dict[str, Any]]:
    """Flag harder OVER thresholds priced as more likely than easier thresholds at one book.

    For a normal over ladder, implied probability should decrease as the line increases.
    """
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not is_user_book(row.get("book")) or row.get("line") is None or row.get("over_price") in (None, 0):
            continue
        # Prefer explicit alt markets but accept multiple thresholds in the same family because
        # some books expose ladder rungs under the base market key.
        key = (_event_key(row), str(row.get("book")), str(row.get("player") or "").lower(), str(row.get("market") or ""))
        groups[key].append(row)

    alerts: list[dict[str, Any]] = []
    for group in groups.values():
        unique_lines = sorted({float(row.get("line")) for row in group})
        if len(unique_lines) < 2:
            continue
        by_line = {}
        for line in unique_lines:
            choices = [row for row in group if float(row.get("line")) == line and row.get("over_price") not in (None, 0)]
            if choices:
                by_line[line] = choices[0]
        ordered = [by_line[line] for line in unique_lines if line in by_line]
        for easier, harder in zip(ordered, ordered[1:]):
            easy_prob = implied_probability(int(easier.get("over_price")))
            hard_prob = implied_probability(int(harder.get("over_price")))
            if hard_prob > easy_prob + tolerance:
                alerts.append(
                    {
                        "type": "ladder_violation",
                        "severity": "P0" if hard_prob > easy_prob + 0.05 else "P1",
                        "book": easier.get("book"),
                        "away_team": easier.get("away_team"),
                        "home_team": easier.get("home_team"),
                        "commence_time": easier.get("commence_time"),
                        "player": easier.get("player"),
                        "market": easier.get("market"),
                        "market_label": easier.get("market_label"),
                        "easier_line": easier.get("line"),
                        "easier_over_price": easier.get("over_price"),
                        "easier_implied_prob": easy_prob,
                        "harder_line": harder.get("line"),
                        "harder_over_price": harder.get("over_price"),
                        "harder_implied_prob": hard_prob,
                        "probability_inversion_points": (hard_prob - easy_prob) * 100,
                    }
                )
    return sorted(alerts, key=lambda row: float(row.get("probability_inversion_points") or 0), reverse=True)


def detect_stale_props(
    rows: Iterable[dict[str, Any]],
    *,
    stale_seconds: float = 600,
    fresh_peer_seconds: float = 180,
) -> list[dict[str, Any]]:
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("line") is None:
            continue
        groups[_exact_market_key(row)].append(row)

    alerts: list[dict[str, Any]] = []
    for group in groups.values():
        fresh_peers = [
            row for row in group
            if row.get("age_seconds") is not None and float(row.get("age_seconds")) <= fresh_peer_seconds
        ]
        if not fresh_peers:
            continue
        for row in group:
            age = row.get("age_seconds")
            if not is_user_book(row.get("book")) or age is None or float(age) < stale_seconds:
                continue
            alerts.append(
                {
                    "type": "stale_prop",
                    "severity": "P2",
                    "book": row.get("book"),
                    "away_team": row.get("away_team"),
                    "home_team": row.get("home_team"),
                    "commence_time": row.get("commence_time"),
                    "player": row.get("player"),
                    "market": row.get("market"),
                    "market_label": row.get("market_label"),
                    "line": row.get("line"),
                    "over_price": row.get("over_price"),
                    "under_price": row.get("under_price"),
                    "age_seconds": age,
                    "fresh_peer_books": sorted({peer.get("book") for peer in fresh_peers if peer.get("book")}),
                    "freshest_peer_age_seconds": min(float(peer.get("age_seconds")) for peer in fresh_peers),
                }
            )
    return sorted(alerts, key=lambda row: float(row.get("age_seconds") or 0), reverse=True)


def prop_coverage(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    books = sorted({str(row.get("book")) for row in rows if row.get("book")})
    markets = sorted({str(row.get("market")) for row in rows if row.get("market")})
    players = {str(row.get("player")) for row in rows if row.get("player")}
    user_counts = {book: 0 for book in USER_BOOKS}
    for row in rows:
        book = canonical_book(row.get("book"))
        if book in user_counts:
            user_counts[book] += 1
    return {
        "rows": len(rows),
        "books": books,
        "markets": markets,
        "players": len(players),
        "user_book_rows": user_counts,
    }


def analyze_props(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    normalized = [normalize_prop_row(row) if "source_title" in row or "source" in row and "book" not in row else dict(row) for row in rows]
    return {
        "coverage": prop_coverage(normalized),
        "price_outliers": detect_prop_price_outliers(normalized),
        "line_gaps": detect_line_gaps(normalized),
        "ladder_violations": detect_ladder_violations(normalized),
        "stale_props": detect_stale_props(normalized),
    }
