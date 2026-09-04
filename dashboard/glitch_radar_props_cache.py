from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

try:
    from glitch_radar_props_feed import analyze_props, fetch_full_props
except ImportError:  # package import path used by pytest
    from dashboard.glitch_radar_props_feed import analyze_props, fetch_full_props


PROP_SNAPSHOT_CACHE_SECONDS = 120
PROP_MAX_QUOTE_AGE_SECONDS = 120


@st.cache_data(ttl=PROP_SNAPSHOT_CACHE_SECONDS, show_spinner=False)
def shared_prop_snapshot(_key: str) -> dict:
    key = str(_key or "").strip()
    if not key:
        raise ValueError("ParlayAPI key is required for the shared prop snapshot")
    rows = fetch_full_props(key, max_age_sec=PROP_MAX_QUOTE_AGE_SECONDS)
    fresh_rows = []
    for row in rows:
        try:
            age_seconds = float(row.get("age_seconds"))
        except (TypeError, ValueError, AttributeError):
            continue
        if 0 <= age_seconds <= PROP_MAX_QUOTE_AGE_SECONDS:
            fresh_rows.append(row)
    if not fresh_rows:
        raise RuntimeError(
            "No player-prop quotes at or under 120 seconds old were returned; "
            "PropWar refuses to display stale or undated deep-prop data."
        )
    rows = fresh_rows
    result = analyze_props(rows)
    result["rows"] = rows
    result["fetched_at"] = datetime.now(timezone.utc).isoformat()
    result["max_quote_age_seconds"] = PROP_MAX_QUOTE_AGE_SECONDS
    return result


__all__ = ["PROP_MAX_QUOTE_AGE_SECONDS", "PROP_SNAPSHOT_CACHE_SECONDS", "shared_prop_snapshot"]
