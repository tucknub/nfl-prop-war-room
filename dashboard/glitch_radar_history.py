from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping


BASELINE = "BASELINE"
NEW = "NEW"
IMPROVED = "IMPROVED"
WORSENED = "WORSENED"
UNCHANGED = "UNCHANGED"
REAPPEARED = "REAPPEARED"
DISAPPEARED = "DISAPPEARED"


def _text(value: object) -> str:
    return str(value or "").strip().casefold()


def _threshold(value: object) -> object:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value).strip()


def glitch_opportunity_key(alert: Mapping[str, Any]) -> str:
    quote = alert.get("quote") if isinstance(alert, Mapping) else {}
    quote = quote if isinstance(quote, Mapping) else {}
    parts = (
        "GLITCH",
        _text(quote.get("event")),
        _text(quote.get("market")),
        _text(quote.get("participant")),
        _text(quote.get("side")),
        repr(_threshold(quote.get("threshold"))),
        _text(quote.get("book")),
    )
    return "|".join(parts)


def ev_opportunity_key(row: Mapping[str, Any]) -> str:
    away = _text(row.get("away_team"))
    home = _text(row.get("home_team"))
    event = f"{away}@{home}" if away or home else _text(row.get("event"))
    parts = (
        "EV",
        event,
        _text(row.get("market") or "moneyline"),
        _text(row.get("selection") or row.get("side")),
        repr(_threshold(row.get("threshold"))),
        _text(row.get("book")),
    )
    return "|".join(parts)


def _price(value: object) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def build_market_observations(
    alerts: Iterable[Mapping[str, Any]],
    ev_rows: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    observations: dict[str, dict[str, Any]] = {}

    for alert in alerts:
        if not isinstance(alert, Mapping):
            continue
        quote = alert.get("quote")
        if not isinstance(quote, Mapping):
            continue
        key = glitch_opportunity_key(alert)
        observations[key] = {
            "key": key,
            "kind": "GLITCH",
            "price": _price(quote.get("odds_american")),
            "book": str(quote.get("book") or "").strip(),
            "event": str(quote.get("event") or "").strip(),
            "market": str(quote.get("market") or "").strip(),
            "side": str(quote.get("side") or "").strip(),
            "threshold": quote.get("threshold"),
        }

    for row in ev_rows:
        if not isinstance(row, Mapping):
            continue
        key = ev_opportunity_key(row)
        observations[key] = {
            "key": key,
            "kind": "EV",
            "price": _price(row.get("price")),
            "book": str(row.get("book") or "").strip(),
            "event": str(row.get("event") or "").strip(),
            "away_team": str(row.get("away_team") or "").strip(),
            "home_team": str(row.get("home_team") or "").strip(),
            "market": str(row.get("market") or "moneyline").strip(),
            "side": str(row.get("selection") or row.get("side") or "").strip(),
            "threshold": row.get("threshold"),
        }

    return observations


def empty_market_history() -> dict[str, Any]:
    return {
        "last_scan_at": None,
        "scan_count": 0,
        "active": {},
        "known": {},
        "disappeared": [],
    }


def update_market_history(
    state: Mapping[str, Any] | None,
    observations: Mapping[str, Mapping[str, Any]],
    *,
    fetched_at: str,
) -> dict[str, Any]:
    previous_state = deepcopy(dict(state or empty_market_history()))
    previous_scan = str(previous_state.get("last_scan_at") or "")
    current_scan = str(fetched_at or "").strip()

    # Streamlit reruns against the same cached snapshot should not create fake movement.
    if current_scan and previous_scan == current_scan:
        return previous_state

    previous_active = {
        str(key): dict(value)
        for key, value in dict(previous_state.get("active") or {}).items()
        if isinstance(value, Mapping)
    }
    known = {
        str(key): dict(value)
        for key, value in dict(previous_state.get("known") or {}).items()
        if isinstance(value, Mapping)
    }
    scan_count = int(previous_state.get("scan_count") or 0) + 1

    active: dict[str, dict[str, Any]] = {}
    for key, raw_observation in observations.items():
        observation = dict(raw_observation)
        prior_active = previous_active.get(key)
        prior_known = known.get(key)
        current_price = _price(observation.get("price"))

        if prior_active is not None:
            previous_price = _price(prior_active.get("current_price"))
            if (
                current_price is not None
                and previous_price is not None
                and current_price > previous_price
            ):
                status = IMPROVED
            elif (
                current_price is not None
                and previous_price is not None
                and current_price < previous_price
            ):
                status = WORSENED
            else:
                status = UNCHANGED
            first_seen = str(prior_active.get("first_seen") or current_scan)
            seen_count = int(prior_active.get("seen_count") or 1) + 1
        elif prior_known is not None:
            previous_price = _price(prior_known.get("current_price"))
            status = REAPPEARED
            first_seen = str(prior_known.get("first_seen") or current_scan)
            seen_count = int(prior_known.get("seen_count") or 0) + 1
        else:
            previous_price = None
            status = BASELINE if scan_count == 1 else NEW
            first_seen = current_scan
            seen_count = 1

        record = {
            **observation,
            "status": status,
            "first_seen": first_seen,
            "last_seen": current_scan,
            "previous_price": previous_price,
            "current_price": current_price,
            "seen_count": seen_count,
        }
        active[key] = record
        known[key] = dict(record)

    disappeared: list[dict[str, Any]] = []
    for key, prior in previous_active.items():
        if key in active:
            continue
        record = {
            **prior,
            "status": DISAPPEARED,
            "disappeared_at": current_scan,
        }
        disappeared.append(record)
        known[key] = dict(record)

    return {
        "last_scan_at": current_scan,
        "scan_count": scan_count,
        "active": active,
        "known": known,
        "disappeared": disappeared,
    }


def history_summary(state: Mapping[str, Any]) -> dict[str, int]:
    active = [
        row
        for row in dict(state.get("active") or {}).values()
        if isinstance(row, Mapping)
    ]
    return {
        "new": sum(row.get("status") in {NEW, REAPPEARED} for row in active),
        "improved": sum(row.get("status") == IMPROVED for row in active),
        "worsened": sum(row.get("status") == WORSENED for row in active),
        "disappeared": len(list(state.get("disappeared") or [])),
    }


def history_for_key(
    state: Mapping[str, Any],
    key: str,
) -> dict[str, Any] | None:
    row = dict(state.get("active") or {}).get(key)
    return dict(row) if isinstance(row, Mapping) else None


__all__ = [
    "BASELINE",
    "NEW",
    "IMPROVED",
    "WORSENED",
    "UNCHANGED",
    "REAPPEARED",
    "DISAPPEARED",
    "build_market_observations",
    "empty_market_history",
    "ev_opportunity_key",
    "glitch_opportunity_key",
    "history_for_key",
    "history_summary",
    "update_market_history",
]
