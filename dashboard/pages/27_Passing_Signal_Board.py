from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import filter_minimum, filter_multiselect, load_signal_csv, render_signal_table
from utils import inject_global_styles, metric_card, page_header, sidebar_status, warning_banner


PATH = "outputs/signal_boards/passing_signal_board.csv"
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
    "passing_yards_projection",
    "pass_attempts_projection",
    "completions_projection",
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


st.set_page_config(page_title="Passing Signal Board", layout="wide")
inject_global_styles()
sidebar_status()

page_header("Passing Signal Board", "Quarterback passing signals from projections and sourced context.", "HISTORICAL TEST ONLY")
warning_banner("HISTORICAL TEST ONLY - NOT LIVE BETTING READY", "This is a quarterback signal research page, not a betting page.")

df = load_signal_csv(PATH)
if df.empty:
    st.warning(f"Missing or empty file: `{PATH}`")
    st.stop()

with st.sidebar:
    st.markdown("### Passing Filters")
    view = df.copy()
    view = filter_multiselect(view, "team", "Team")
    view = filter_multiselect(view, "opponent", "Opponent")
    view = filter_multiselect(view, "signal_tier", "Signal tier")
    view = filter_minimum(view, "passing_yards_projection", "Minimum passing yards projection", 0.0)
    view = filter_minimum(view, "pass_attempts_projection", "Minimum pass attempts projection", 0.0)

cols = st.columns(4)
with cols[0]:
    metric_card("Best QB Signal", top_name(view, "overall_signal_score"), "INFO")
with cols[1]:
    metric_card("Best Passing Yards", top_name(view, "passing_yards_projection"), "INFO")
with cols[2]:
    metric_card("Best Pass Volume", top_name(view, "pass_attempts_projection"), "INFO")
with cols[3]:
    risk = pd.to_numeric(view.get("red_flag_count", pd.Series(dtype=float)), errors="coerce")
    risk_name = view.loc[risk.idxmax()].get("player_name", "n/a") if risk.notna().any() else "n/a"
    metric_card("Most Review Risk", risk_name, "REVIEW")

render_signal_table(
    view.sort_values("overall_signal_score", ascending=False).head(300),
    SCORE_COLUMNS,
    DISPLAY_COLUMNS,
    "Passing Heatmap",
)
