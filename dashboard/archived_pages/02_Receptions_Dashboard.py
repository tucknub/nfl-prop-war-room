from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (
    filter_by_multiselect,
    filter_by_search,
    first_existing_columns,
    inject_global_styles,
    metric_card,
    numeric_series,
    page_header,
    player_card,
    presentation_table,
    section_header,
    show_missing,
    sidebar_status,
    warning_banner,
    load_csv_safe,
)


MODEL_PATH = "outputs/google_sheets_receptions_historical_test.csv"


st.set_page_config(page_title="Receptions Projection Board", layout="wide")
inject_global_styles()
sidebar_status()
page_header(
    "Receptions Projection Board",
    "Historical-test projection board with raw and calibrated reception estimates.",
    "HISTORICAL TEST ONLY",
)
warning_banner(
    "Historical-test model board only",
    "Do not use this page as live betting output. Final Readiness must be GO before live use.",
)

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
with cards[0]:
    metric_card("Total Rows", f"{len(view):,}")
with cards[1]:
    metric_card("Unique Players", view["player_name"].nunique() if "player_name" in view.columns else "n/a")
with cards[2]:
    metric_card("Unique Teams", view["team"].nunique() if "team" in view.columns else "n/a")
with cards[3]:
    metric_card("Avg Calibrated", f"{calibrated.mean():.2f}" if not calibrated.empty else "n/a")
with cards[4]:
    metric_card("Top Projection", f"{calibrated.max():.2f}" if not calibrated.empty else "n/a")
with cards[5]:
    metric_card(
        "Historical-Test Rows",
        int(view.get("usage_status", pd.Series(dtype=str)).astype(str).eq("HISTORICAL TEST ONLY").sum()),
        "HISTORICAL TEST ONLY",
    )

section_header("Top Projected Players", "Top five by calibrated receptions projection.")
top_players = view.sort_values("calibrated_projection", ascending=False).head(5)
top_cols = st.columns(5)
for col, (_, row) in zip(top_cols, top_players.iterrows()):
    with col:
        player_card(
            str(row.get("player_name", "")),
            str(row.get("team", "")),
            str(row.get("position", "")),
            f"{pd.to_numeric(row.get('calibrated_projection'), errors='coerce'):.2f}",
            row.get("confidence_tier", ""),
        )

chart_left, chart_mid, chart_right = st.columns([1.4, 1, 1])
with chart_left:
    section_header("Top 15 Calibrated Projections")
    top_chart = (
        view.sort_values("calibrated_projection", ascending=False)
        .head(15)
        .set_index("player_name")["calibrated_projection"]
    )
    st.bar_chart(top_chart)
with chart_mid:
    section_header("Average By Position")
    if "position" in view.columns:
        pos = view.groupby("position")["calibrated_projection"].mean().sort_values(ascending=False)
        st.bar_chart(pos)
with chart_right:
    section_header("Team Distribution")
    if "team" in view.columns:
        st.bar_chart(view["team"].value_counts().sort_index())

section_header("Projection Table", "Clean view with raw columns still preserved.")
columns = first_existing_columns(
    view,
    [
        "overall_rank",
        "player_name",
        "team",
        "opponent",
        "position",
        "calibrated_projection",
        "raw_projection",
        "projected_team_pass_attempts",
        "projected_target_share",
        "projected_catch_rate",
        "estimated_routes",
        "confidence_tier",
        "flags",
        "usage_status",
    ],
)
table = view[columns].sort_values("calibrated_projection", ascending=False)
st.dataframe(presentation_table(table), use_container_width=True, hide_index=True)

with st.expander("Raw committed model CSV"):
    st.dataframe(df, use_container_width=True, hide_index=True)
