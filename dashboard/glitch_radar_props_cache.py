from __future__ import annotations

from datetime import datetime, timezone

import streamlit as st

try:
    from glitch_radar_props_feed import analyze_props, fetch_full_props
except ImportError:  # package import path used by pytest
    from dashboard.glitch_radar_props_feed import analyze_props, fetch_full_props


PROP_SNAPSHOT_CACHE_SECONDS = 10_800


@st.cache_data(ttl=PROP_SNAPSHOT_CACHE_SECONDS, show_spinner=False)
def shared_prop_snapshot(_key: str) -> dict:
    key = str(_key or "").strip()
    if not key:
        raise ValueError("ParlayAPI key is required for the shared prop snapshot")
    rows = fetch_full_props(key)
    result = analyze_props(rows)
    result["rows"] = rows
    result["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return result


__all__ = ["PROP_SNAPSHOT_CACHE_SECONDS", "shared_prop_snapshot"]
