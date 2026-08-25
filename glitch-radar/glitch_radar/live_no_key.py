from .providers.parlayapi_no_key import (
    fetch_try, fetch_command_center, fetch_source_quality,
    parse_try_odds, demo_remaining,
)
from .engine import RadarEngine
from .nfl_markets import normalize_nfl_quotes

def _safe(label, fn):
    try:
        return fn(), None
    except Exception as e:
        return None, f"{label}: {e}"

def build_no_key_snapshot():
    errors = []

    odds, err = _safe("odds", lambda: fetch_try("odds"))
    if err: errors.append(err)

    arb, err = _safe("arbitrage", lambda: fetch_try("arbitrage"))
    if err: errors.append(err)

    ev, err = _safe("ev", lambda: fetch_try("ev"))
    if err: errors.append(err)

    middles, err = _safe("middles", lambda: fetch_try("middles"))
    if err: errors.append(err)

    command, err = _safe("command_center", lambda: fetch_command_center(50))
    if err: errors.append(err)

    quality, err = _safe("source_quality", fetch_source_quality)
    if err: errors.append(err)

    quotes = normalize_nfl_quotes(parse_try_odds(odds or {}))
    alerts = RadarEngine().scan(quotes) if quotes else []

    def pack(v):
        if hasattr(v, "__dict__"):
            return dict(v.__dict__)
        if isinstance(v, list):
            return [pack(x) for x in v]
        if isinstance(v, dict):
            return {k: pack(x) for k, x in v.items()}
        return v

    return {
        "mode": "no_key",
        "quotes": [pack(q) for q in quotes],
        "local_alerts": [pack(a) for a in alerts],
        "arbitrage": arb or {},
        "ev": ev or {},
        "middles": middles or {},
        "command_center": command or {},
        "source_quality": quality or {},
        "demo_remaining_hour": demo_remaining(odds or {}),
        "errors": errors,
    }
