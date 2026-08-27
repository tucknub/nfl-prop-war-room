from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Iterable, Mapping


BASELINE = "BASELINE"
NEW = "NEW"
IMPROVED = "IMPROVED"
WORSENED = "WORSENED"
UNCHANGED = "UNCHANGED"
REAPPEARED = "REAPPEARED"
DISAPPEARED = "DISAPPEARED"
FRESH = "FRESH"
AGING = "AGING"
STALE = "STALE"

MAX_KNOWN_RECORDS = 2500
MAX_RECENT_CHANGES = 500


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
        "schema_version": 2,
        "last_scan_at": None,
        "scan_count": 0,
        "active": {},
        "known": {},
        "disappeared": [],
        "recent_changes": [],
    }


def _parse_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def freshness_status(
    last_seen: object,
    *,
    now: datetime | None = None,
    fresh_minutes: float = 15.0,
    stale_minutes: float = 30.0,
) -> str:
    parsed = _parse_datetime(last_seen)
    if parsed is None:
        return STALE
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    age_minutes = max(
        0.0,
        (current.astimezone(timezone.utc) - parsed).total_seconds() / 60.0,
    )
    if age_minutes <= fresh_minutes:
        return FRESH
    if age_minutes <= stale_minutes:
        return AGING
    return STALE


def _change_event(record: Mapping[str, Any], *, changed_at: str) -> dict[str, Any]:
    return {
        "key": str(record.get("key") or ""),
        "kind": str(record.get("kind") or ""),
        "status": str(record.get("status") or ""),
        "book": str(record.get("book") or ""),
        "event": str(record.get("event") or ""),
        "away_team": str(record.get("away_team") or ""),
        "home_team": str(record.get("home_team") or ""),
        "market": str(record.get("market") or ""),
        "side": str(record.get("side") or ""),
        "threshold": record.get("threshold"),
        "opening_price": _price(record.get("opening_price")),
        "previous_price": _price(record.get("previous_price")),
        "current_price": _price(record.get("current_price")),
        "first_seen": str(record.get("first_seen") or ""),
        "last_seen": str(record.get("last_seen") or ""),
        "changed_at": changed_at,
    }


def _bounded_known(
    known: Mapping[str, Mapping[str, Any]],
    active_keys: set[str],
) -> dict[str, dict[str, Any]]:
    rows = [
        (str(key), dict(value))
        for key, value in known.items()
        if isinstance(value, Mapping)
    ]
    rows.sort(
        key=lambda item: str(item[1].get("last_seen") or ""),
        reverse=True,
    )
    selected: dict[str, dict[str, Any]] = {}
    for key, row in rows:
        if key in active_keys:
            selected[key] = row
    for key, row in rows:
        if len(selected) >= MAX_KNOWN_RECORDS:
            break
        selected.setdefault(key, row)
    return selected


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
    recent_changes = [
        dict(row)
        for row in list(previous_state.get("recent_changes") or [])
        if isinstance(row, Mapping)
    ]

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
            opening_price = _price(
                prior_active.get("opening_price")
                if prior_active.get("opening_price") is not None
                else prior_active.get("current_price")
            )
            seen_count = int(prior_active.get("seen_count") or 1) + 1
        elif prior_known is not None:
            previous_price = _price(prior_known.get("current_price"))
            status = REAPPEARED
            first_seen = str(prior_known.get("first_seen") or current_scan)
            opening_price = _price(
                prior_known.get("opening_price")
                if prior_known.get("opening_price") is not None
                else prior_known.get("current_price")
            )
            seen_count = int(prior_known.get("seen_count") or 0) + 1
        else:
            previous_price = None
            status = BASELINE if scan_count == 1 else NEW
            first_seen = current_scan
            opening_price = current_price
            seen_count = 1

        record = {
            **observation,
            "status": status,
            "first_seen": first_seen,
            "last_seen": current_scan,
            "opening_price": opening_price,
            "previous_price": previous_price,
            "current_price": current_price,
            "seen_count": seen_count,
        }
        active[key] = record
        known[key] = dict(record)
        if status in {NEW, IMPROVED, WORSENED, REAPPEARED}:
            recent_changes.append(
                _change_event(record, changed_at=current_scan)
            )

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
        recent_changes.append(
            _change_event(record, changed_at=current_scan)
        )

    recent_changes = recent_changes[-MAX_RECENT_CHANGES:]
    known = _bounded_known(known, set(active))

    return {
        "schema_version": 2,
        "last_scan_at": current_scan,
        "scan_count": scan_count,
        "active": active,
        "known": known,
        "disappeared": disappeared,
        "recent_changes": recent_changes,
    }


class MarketHistoryStore:
    """Thread-safe process-level scan memory for the owner-only radar."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._state = empty_market_history()

    def update(
        self,
        observations: Mapping[str, Mapping[str, Any]],
        *,
        fetched_at: str,
    ) -> dict[str, Any]:
        with self._lock:
            self._state = update_market_history(
                self._state,
                observations,
                fetched_at=fetched_at,
            )
            return deepcopy(self._state)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._state)


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


def recent_history_changes(
    state: Mapping[str, Any],
    *,
    limit: int = 50,
) -> tuple[dict[str, Any], ...]:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
        raise ValueError("limit must be a non-negative integer")
    rows = [
        dict(row)
        for row in list(state.get("recent_changes") or [])
        if isinstance(row, Mapping)
    ]
    rows.reverse()
    return tuple(rows[:limit])


__all__ = [
    "BASELINE",
    "NEW",
    "IMPROVED",
    "WORSENED",
    "UNCHANGED",
    "REAPPEARED",
    "DISAPPEARED",
    "FRESH",
    "AGING",
    "STALE",
    "build_market_observations",
    "empty_market_history",
    "ev_opportunity_key",
    "glitch_opportunity_key",
    "MarketHistoryStore",
    "freshness_status",
    "history_for_key",
    "history_summary",
    "recent_history_changes",
    "update_market_history",
]
