from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import filter_minimum, filter_multiselect, load_signal_csv, render_signal_kpis, render_signal_table, top_signal_cards
from utils import inject_global_styles, page_header, sidebar_status, warning_banner


PATH = "outputs/signal_boards/slate_signal_board.csv"
SCORE_COLUMNS = [
    "overall_signal_score",
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "weather_score",
    "role_availability_score",
    "volatility_score",
    "data_quality_score",
]
DISPLAY_COLUMNS = [
    "player_name",
    "team",
    "opponent",
    "position",
    "overall_signal_score",
    "signal_tier",
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "weather_score",
    "role_availability_score",
    "volatility_score",
    "data_quality_score",
    "green_signal_count",
    "red_flag_count",
    "recent_form_reliability",
    "defense_fit_reliability",
    "game_total_bucket",
    "spread_bucket",
    "pass_volume_environment",
    "rush_volume_environment",
    "signal_explanation",
    "recommended_user_action",
    "top_positive_driver_1",
    "top_negative_driver_1",
    "top_signal_reason",
    "review_reason",
]


st.set_page_config(page_title="Slate Signal Board", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "Slate Signal Board",
    "Color-coded player signals from projections and available context. No odds. No betting output.",
    "HISTORICAL TEST ONLY",
)
warning_banner(
    "HISTORICAL TEST ONLY - NOT LIVE BETTING READY",
    "This is a research heatmap built from existing signal board files. It does not create live output.",
)
st.caption("Use Player Signal Drilldown to inspect drivers and recent history for any player.")

df = load_signal_csv(PATH)
if df.empty:
    st.warning(f"Missing or empty file: `{PATH}`")
    st.stop()

with st.sidebar:
    st.markdown("### Slate Filters")
    view = df.copy()
    market_family = st.selectbox("Market family", ["All", "Receiving", "Rushing", "Passing"])
    if market_family != "All":
        flag = f"{market_family.lower()}_market_available"
        if flag in view.columns:
            view = view[view[flag].astype(str).str.lower().isin(["true", "1", "yes"])]
    view = filter_multiselect(view, "position", "Position")
    view = filter_multiselect(view, "team", "Team")
    view = filter_multiselect(view, "signal_tier", "Signal tier")
    view = filter_multiselect(view, "recent_form_reliability", "Recent form reliability")
    view = filter_multiselect(view, "defense_fit_reliability", "Defense fit reliability")
    view = filter_multiselect(view, "game_total_bucket", "Game total bucket")
    view = filter_multiselect(view, "spread_bucket", "Spread bucket")
    view = filter_multiselect(view, "pass_volume_environment", "Pass volume environment")
    view = filter_multiselect(view, "rush_volume_environment", "Rush volume environment")
    view = filter_minimum(view, "overall_signal_score", "Minimum overall signal score", 0.0)
    if st.checkbox("Hide insufficient data", value=False) and "signal_tier" in view.columns:
        view = view[~view["signal_tier"].astype(str).eq("INSUFFICIENT_DATA")]
    if st.checkbox("Only low red flags", value=False) and "red_flag_count" in view.columns:
        red_flags = pd.to_numeric(view["red_flag_count"], errors="coerce").fillna(0)
        view = view[red_flags <= 1]

render_signal_kpis(view)
top_signal_cards(view, count=5)
st.caption("Defense fit is reliability-adjusted and should not be treated as certain.")
render_signal_table(
    view.sort_values("overall_signal_score", ascending=False).head(300),
    SCORE_COLUMNS,
    DISPLAY_COLUMNS,
    "Slate Heatmap",
    "Sorted by existing overall signal score. Missing columns are omitted safely.",
)
