from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

INDIANA_TZ = ZoneInfo("America/Indiana/Indianapolis")


def format_american(value: object) -> str:
    try:
        odds = int(float(value))
    except (TypeError, ValueError):
        return "—"
    return f"{odds:+d}"


def american_to_decimal(value: object) -> float | None:
    try:
        odds = int(float(value))
    except (TypeError, ValueError):
        return None
    if odds == 0:
        return None
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))


def fair_american_from_probability(probability_pct: object) -> int | None:
    try:
        probability = float(probability_pct) / 100
    except (TypeError, ValueError):
        return None
    if probability <= 0 or probability >= 1:
        return None
    decimal = 1 / probability
    if decimal >= 2:
        return round((decimal - 1) * 100)
    return round(-100 / (decimal - 1))


def expected_ev_pct(price: object, fair_probability_pct: object) -> float | None:
    decimal = american_to_decimal(price)
    try:
        fair_probability = float(fair_probability_pct) / 100
    except (TypeError, ValueError):
        return None
    if decimal is None or fair_probability <= 0 or fair_probability >= 1:
        return None
    return (fair_probability * decimal - 1) * 100


def probability_edge_points(row: dict) -> float | None:
    try:
        return float(row.get("edge_pct"))
    except (TypeError, ValueError):
        pass
    try:
        return float(row.get("fair_prob_pct")) - float(row.get("book_implied_pct"))
    except (TypeError, ValueError):
        return None


def game_name(row: dict) -> str:
    away = str(row.get("away_team") or "").strip()
    home = str(row.get("home_team") or "").strip()
    if away and home:
        return f"{away} @ {home}"
    return away or home or str(row.get("event") or "Game").strip() or "Game"


def _parse_datetime(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def local_start_label(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Start time unavailable"
    parsed = _parse_datetime(value)
    if parsed is None:
        return raw
    local = parsed.astimezone(INDIANA_TZ)
    hour = local.strftime("%I").lstrip("0") or "12"
    return f"{local.strftime('%a %b')} {local.day} · {hour}:{local.strftime('%M %p')} ET"


def event_phase_label(value: object) -> str:
    """Return a conservative NFL phase label when it can be inferred safely from the date.

    NFL games in July/August are preseason. Other months remain unlabeled rather than
    guessing regular season versus postseason without authoritative schedule metadata.
    """
    parsed = _parse_datetime(value)
    if parsed is None:
        return ""
    return "PRESEASON" if parsed.month in {7, 8} else ""


def value_tier(ev_pct: float | None) -> str:
    if ev_pct is None:
        return "UNRATED"
    if ev_pct >= 12:
        return "PREMIUM PRICE"
    if ev_pct >= 7:
        return "STRONG PRICE"
    if ev_pct >= 3:
        return "POSITIVE PRICE"
    if ev_pct > 0:
        return "THIN EDGE"
    return "PASS"
