from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import filter_minimum, filter_multiselect, inject_signal_css, load_signal_csv, render_signal_legend, render_signal_table, top_signal_cards
from utils import inject_global_styles, metric_card, page_header, sidebar_status, warning_banner


PATH = "outputs/signal_boards/rushing_signal_board.csv"
SCORE_COLUMNS = [
    "overall_signal_score",
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
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
    "rushing_yards_projection",
    "carries_projection",
    "l3_carries",
    "l5_carries",
    "l3_rushing_yards",
    "l5_rushing_yards",
    "opp_rushing_fit_score",
    "defense_fit_reliability",
    "rush_volume_environment",
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "role_availability_score",
    "volatility_score",
    "data_quality_score",
    "green_signal_count",
    "red_flag_count",
    "recommended_user_action",
    "top_signal_reason",
    "review_reason",
]


def top_name(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return "n/a"
    values = pd.to_numeric(df[column], errors="coerce")
    if not values.notna().any():
        return "n/a"
    row = df.loc[values.idxmax()]
    return f"{row.get('player_name', 'n/a')} ({values.max():.1f})"


st.set_page_config(page_title="Rushing Signal Board", layout="wide")
inject_global_styles()
inject_signal_css()
sidebar_status()

page_header("Rushing Signal Board", "Rushing player signals from projections and sourced context.", "HISTORICAL TEST ONLY")
st.caption("Section: Main Signal Workflow")
warning_banner("HISTORICAL TEST ONLY - NOT LIVE BETTING READY", "This is a signal research page, not a betting page.")
st.caption("Use Player Signal Drilldown to inspect drivers and recent history for any player.")
render_signal_legend()

df = load_signal_csv(PATH)
if df.empty:
    st.warning(f"Missing or empty file: `{PATH}`")
    st.stop()

with st.sidebar:
    st.markdown("### Rushing Filters")
    view = df.copy()
    view = filter_multiselect(view, "team", "Team")
    view = filter_multiselect(view, "opponent", "Opponent")
    view = filter_multiselect(view, "position", "Position")
    view = filter_multiselect(view, "signal_tier", "Signal tier")
    view = filter_multiselect(view, "recent_form_reliability", "Recent form reliability")
    view = filter_multiselect(view, "defense_fit_reliability", "Defense fit reliability")
    view = filter_multiselect(view, "rush_volume_environment", "Rush volume environment")
    view = filter_multiselect(view, "game_total_bucket", "Game total bucket")
    view = filter_multiselect(view, "spread_bucket", "Spread bucket")
    view = filter_minimum(view, "rushing_yards_projection", "Minimum rushing yards projection", 0.0)
    view = filter_minimum(view, "carries_projection", "Minimum carries projection", 0.0)

cols = st.columns(4)
with cols[0]:
    metric_card("Best Overall", top_name(view, "overall_signal_score"), "INFO")
with cols[1]:
    metric_card("Best Rush Yards", top_name(view, "rushing_yards_projection"), "INFO")
with cols[2]:
    metric_card("Best Workload Support", top_name(view, "carries_projection"), "INFO")
with cols[3]:
    risk = pd.to_numeric(view.get("red_flag_count", pd.Series(dtype=float)), errors="coerce")
    risk_name = view.loc[risk.idxmax()].get("player_name", "n/a") if risk.notna().any() else "n/a"
    metric_card("Most Review Risk", risk_name, "REVIEW")

top_signal_cards(view, count=5)
st.caption("Defense fit is reliability-adjusted and should not be treated as certain.")
render_signal_table(
    view.sort_values("overall_signal_score", ascending=False).head(300),
    SCORE_COLUMNS,
    DISPLAY_COLUMNS,
    "Rushing Heatmap",
)
