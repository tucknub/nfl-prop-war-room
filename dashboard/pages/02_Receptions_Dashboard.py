from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (
    apply_global_styles,
    filter_by_multiselect,
    filter_by_search,
    first_existing_columns,
    load_csv_safe,
    numeric_series,
    show_missing,
)


MODEL_PATH = "outputs/google_sheets_receptions_historical_test.csv"


st.set_page_config(page_title="Receptions Dashboard", layout="wide")
apply_global_styles()
st.title("Receptions Dashboard")
st.warning("Historical-test model board only. Do not use as live betting output.")

df = load_csv_safe(MODEL_PATH)
if df.empty:
    show_missing(MODEL_PATH)
    st.stop()

view = df.copy()
view["raw_projection"] = view.get("projected_receptions_raw", pd.Series(index=view.index, dtype=float))
view["calibrated_projection"] = view.get("projected_receptions_calibrated", pd.Series(index=view.index, dtype=float))
view["confidence_tier"] = view.get("confidence_bucket", pd.Series(["Unknown"] * len(view), index=view.index))
view["flags"] = view.get("quality_flags", pd.Series([""] * len(view), index=view.index))
if "player" not in view.columns:
    view["player"] = view.get("player_name", pd.Series([""] * len(view), index=view.index))

filters = st.columns(5)
with filters[0]:
    view = filter_by_multiselect(view, "team", "Team")
with filters[1]:
    view = filter_by_multiselect(view, "position", "Position")
with filters[2]:
    view = filter_by_multiselect(view, "confidence_tier", "Confidence tier")
with filters[3]:
    view = filter_by_multiselect(view, "usage_status", "Usage status")
with filters[4]:
    view = filter_by_search(view, "player_name")

calibrated = numeric_series(view, "calibrated_projection")
cards = st.columns(6)
cards[0].metric("Rows", f"{len(view):,}")
cards[1].metric("Teams", view["team"].nunique() if "team" in view.columns else "n/a")
cards[2].metric("Avg calibrated", f"{calibrated.mean():.2f}" if not calibrated.empty else "n/a")
cards[3].metric("Top calibrated", f"{calibrated.max():.2f}" if not calibrated.empty else "n/a")
cards[4].metric("High confidence", int(view["confidence_tier"].astype(str).eq("High").sum()))
cards[5].metric(
    "Historical-test only",
    int(view.get("usage_status", pd.Series(dtype=str)).astype(str).eq("HISTORICAL TEST ONLY").sum()),
)

columns = first_existing_columns(
    view,
    [
        "overall_rank",
        "player",
        "player_name",
        "team",
        "opponent",
        "position",
        "raw_projection",
        "calibrated_projection",
        "projected_team_pass_attempts",
        "projected_target_share",
        "projected_catch_rate",
        "estimated_routes",
        "confidence_tier",
        "flags",
        "usage_status",
    ],
)
st.dataframe(view[columns].sort_values("calibrated_projection", ascending=False), use_container_width=True, hide_index=True)
