from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import filter_minimum, filter_multiselect, load_signal_csv, render_signal_table
from utils import inject_global_styles, page_header, sidebar_status, warning_banner


PATH = "outputs/signal_boards/blocked_review_board.csv"
SCORE_COLUMNS = ["overall_signal_score"]
DISPLAY_COLUMNS = [
    "player_name",
    "team",
    "opponent",
    "position",
    "signal_tier",
    "overall_signal_score",
    "red_flag_count",
    "missing_signal_count",
    "roster_status",
    "role_status",
    "injury_status",
    "readiness_status",
    "recent_form_reliability",
    "defense_fit_reliability",
    "game_environment_reliability",
    "context_data_quality",
    "signal_explanation",
    "recommended_user_action",
    "top_positive_driver_1",
    "top_negative_driver_1",
    "review_reason",
    "blocked_reason",
    "top_signal_reason",
]


st.set_page_config(page_title="Blocked / Review Board", layout="wide")
inject_global_styles()
sidebar_status()

page_header("Blocked / Review Board", "Rows that need more context before they should be trusted.", "REVIEW")
st.caption("Section: Main Signal Workflow")
warning_banner(
    "HISTORICAL TEST ONLY - NOT LIVE BETTING READY",
    "A red or review player is not automatically bad at football. It means the signal is incomplete, risky, or missing key context.",
)
st.caption("Use Player Signal Drilldown to inspect drivers and recent history for any player.")

df = load_signal_csv(PATH)
if df.empty:
    st.warning(f"Missing or empty file: `{PATH}`")
    st.stop()

with st.sidebar:
    st.markdown("### Review Filters")
    view = df.copy()
    view = filter_multiselect(view, "blocked_reason", "Blocked reason")
    view = filter_multiselect(view, "review_reason", "Review reason")
    view = filter_minimum(view, "missing_signal_count", "Minimum missing signal count", 0.0)
    view = filter_multiselect(view, "team", "Team")
    view = filter_multiselect(view, "position", "Position")
    view = filter_multiselect(view, "recent_form_reliability", "Recent form reliability")
    view = filter_multiselect(view, "defense_fit_reliability", "Defense fit reliability")
    view = filter_multiselect(view, "game_environment_reliability", "Game environment reliability")

review_rows = int(view["signal_tier"].astype(str).isin(["REVIEW", "INSUFFICIENT_DATA"]).sum()) if "signal_tier" in view.columns else len(view)
blocked_rows = int(view["signal_tier"].astype(str).eq("BLOCKED").sum()) if "signal_tier" in view.columns else 0
missing_total = int(pd.to_numeric(view.get("missing_signal_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
red_total = int(pd.to_numeric(view.get("red_flag_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())

cols = st.columns(4)
with cols[0]:
    st.metric("Rows", len(view))
with cols[1]:
    st.metric("Review Rows", review_rows)
with cols[2]:
    st.metric("Blocked Rows", blocked_rows)
with cols[3]:
    st.metric("Missing / Red Flags", f"{missing_total} / {red_total}")

st.markdown(
    """
    <div class="info-card">
    Use this board to fix missing current context, stale role information, uncertain injury state, or incomplete signal sources.
    It is a review queue, not a downgrade list.
    </div>
    """,
    unsafe_allow_html=True,
)

render_signal_table(
    view.sort_values(["red_flag_count", "missing_signal_count", "overall_signal_score"], ascending=[False, False, True]).head(500),
    SCORE_COLUMNS,
    DISPLAY_COLUMNS,
    "Blocked / Review Heatmap",
)
