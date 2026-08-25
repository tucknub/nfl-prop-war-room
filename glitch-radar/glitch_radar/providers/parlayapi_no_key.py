import requests
from datetime import datetime, timezone
from ..models import Quote

BASE = "https://parlay-api.com"
SPORT = "americanfootball_nfl"

def _get(path, params=None, timeout=25):
    r = requests.get(f"{BASE}{path}", params=params or {}, timeout=timeout)
    if r.status_code == 429:
        raise RuntimeError("ParlayAPI no-auth rate limit reached (HTTP 429).")
    r.raise_for_status()
    return r.json()

def fetch_try(kind):
    if kind not in {"odds", "arbitrage", "ev", "middles"}:
        raise ValueError("Unsupported try endpoint")
    return _get(f"/v1/try/{SPORT}/{kind}")

def fetch_command_center(limit=50):
    return _get("/live/api/command_center", params={"sport": SPORT, "limit": max(1, min(int(limit), 50))})

def fetch_source_quality():
    return _get("/v1/meta/source-quality")

def fetch_parser_coverage():
    return _get("/v1/meta/parser-coverage", params={"sport_key": SPORT, "window_hours": 72})

def _events_from_try_odds(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in ("events", "data", "odds"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    for key in ("result", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []

def parse_try_odds(payload, timestamp=None):
    stamp = timestamp or datetime.now(timezone.utc).isoformat()
    quotes = []
    for event in _events_from_try_odds(payload):
        home = str(event.get("home_team", "") or "")
        away = str(event.get("away_team", "") or "")
        event_name = f"{away} @ {home}".strip(" @")
        for book in event.get("bookmakers", []) or []:
            book_name = str(book.get("title") or book.get("key") or "unknown")
            for market in book.get("markets", []) or []:
                mkey = str(market.get("key", "") or "").lower()
                for outcome in market.get("outcomes", []) or []:
                    price = outcome.get("price")
                    if price in (None, ""):
                        continue
                    try:
                        odds = int(float(price))
                    except (TypeError, ValueError):
                        continue
                    name = str(outcome.get("name", "") or "")
                    point = outcome.get("point")
                    try:
                        threshold = float(point) if point is not None else None
                    except (TypeError, ValueError):
                        threshold = None
                    participant = ""
                    side = ""
                    market_name = mkey
                    if mkey in ("h2h", "moneyline"):
                        market_name = "moneyline"
                        if name.lower() == home.lower():
                            side = "home"
                        elif name.lower() == away.lower():
                            side = "away"
                        else:
                            side = name.lower()
                    elif mkey in ("totals", "total"):
                        market_name = "game_total"
                        side = name.lower()
                    elif mkey in ("spreads", "spread"):
                        market_name = "spread"
                        participant = name
                        if name.lower() == home.lower():
                            side = "home"
                        elif name.lower() == away.lower():
                            side = "away"
                        else:
                            side = name.lower()
                    else:
                        market_name = mkey
                        side = name.lower()
                    quotes.append(Quote(
                        book=book_name,
                        event=event_name,
                        market=market_name,
                        participant=participant,
                        side=side,
                        threshold=threshold,
                        odds_american=odds,
                        period="game",
                        timestamp=stamp,
                        source="ParlayAPI no-auth",
                    ))
    return quotes

def demo_remaining(payload):
    if isinstance(payload, dict):
        return payload.get("demo_remaining_hour")
    return None
