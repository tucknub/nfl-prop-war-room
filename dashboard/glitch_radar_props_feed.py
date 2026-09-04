from __future__ import annotations

from typing import Any

import httpx

try:
    from glitch_radar_books import canonical_book
    from glitch_radar_props import PROP_CREDITS_PER_SCAN, analyze_props, canonical_market
except ImportError:  # package import path used by pytest
    from dashboard.glitch_radar_books import canonical_book
    from dashboard.glitch_radar_props import PROP_CREDITS_PER_SCAN, analyze_props, canonical_market

BASE = "https://parlay-api.com"
SPORT = "americanfootball_nfl"


def _float(value: object) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_feed_row(row: dict[str, Any]) -> dict[str, Any]:
    """Accept both documented ParlayAPI prop row naming conventions.

    Current docs use bookmaker/bookmaker_title/player/canonical_event_id/last_update.
    Older response-shape docs use source/source_title/player_name/event_id/snapshot_time.
    """
    book = canonical_book(
        row.get("bookmaker_title")
        or row.get("source_title")
        or row.get("bookmaker")
        or row.get("source")
        or row.get("book")
    )
    market_key = str(row.get("market_key") or "").strip().lower()
    market_display = row.get("market_label") or row.get("market")
    source = row.get("bookmaker") or row.get("source")
    return {
        "event_id": row.get("canonical_event_id") or row.get("event_id"),
        "commence_time": row.get("commence_time"),
        "home_team": row.get("home_team"),
        "away_team": row.get("away_team"),
        "book": book,
        "source": source,
        "player": str(row.get("player") or row.get("player_name") or "").strip(),
        "market_key": market_key,
        "market": canonical_market(market_key),
        "market_label": market_display or market_key.replace("_", " ").title(),
        "line": _float(row.get("line")),
        "over_price": _int(row.get("over_price")),
        "under_price": _int(row.get("under_price")),
        "over_implied_prob": _float(row.get("over_implied_prob")),
        "under_implied_prob": _float(row.get("under_implied_prob")),
        "snapshot_time": row.get("snapshot_time") or row.get("last_update"),
        "age_seconds": _float(row.get("age_seconds")),
    }


def normalize_feed_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = []
        for key in ("props", "data", "results", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value
                break
    else:
        rows = []
    return [normalize_feed_row(row) for row in rows if isinstance(row, dict)]


def fetch_full_props(api_key: str, *, max_age_sec: int = 120) -> list[dict[str, Any]]:
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("ParlayAPI key is required for deep prop scans")

    response = httpx.get(
        f"{BASE}/v1/sports/{SPORT}/props",
        params={"limit": 10000, "maxAgeSec": int(max_age_sec)},
        headers={"X-API-Key": key, "User-Agent": "PropWar-Glitch-Radar/2.0"},
        timeout=35.0,
        follow_redirects=True,
    )
    if response.status_code == 401:
        raise RuntimeError("ParlayAPI key was rejected")
    if response.status_code in {402, 403}:
        raise RuntimeError("ParlayAPI free credits are exhausted for this billing month or access is not enabled")
    if response.status_code == 429:
        raise RuntimeError("ParlayAPI rate limit reached")
    response.raise_for_status()
    return normalize_feed_payload(response.json())


__all__ = [
    "PROP_CREDITS_PER_SCAN",
    "analyze_props",
    "fetch_full_props",
    "normalize_feed_payload",
    "normalize_feed_row",
]
