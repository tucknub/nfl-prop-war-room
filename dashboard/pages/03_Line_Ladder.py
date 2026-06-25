from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import apply_global_styles, filter_by_multiselect, filter_by_search, format_percent, load_csv_safe, show_missing


LADDER_PATH = "outputs/market_edges/receptions_line_ladder.csv"
TOP_PATH = "outputs/market_edges/receptions_line_ladder_top_by_line.csv"


st.set_page_config(page_title="Line Ladder", layout="wide")
apply_global_styles()
st.title("Line Ladder")
st.warning("Line ladder is research only. It is not betting edge because sportsbook odds are not required here.")

ladder = load_csv_safe(LADDER_PATH)
top = load_csv_safe(TOP_PATH)
if ladder.empty:
    show_missing(LADDER_PATH)
    st.stop()

view = ladder.copy()
filters = st.columns(5)
with filters[0]:
    view = filter_by_multiselect(view, "line", "Line")
with filters[1]:
    view = filter_by_multiselect(view, "team", "Team")
with filters[2]:
    view = filter_by_multiselect(view, "position", "Position")
with filters[3]:
    min_prob = st.slider("Minimum over probability", 0.0, 1.0, 0.0, 0.01)
    view = view[pd.to_numeric(view["model_over_probability"], errors="coerce").fillna(0) >= min_prob]
with filters[4]:
    view = filter_by_search(view, "player_name")

cards = st.columns(4)
cards[0].metric("Rows", f"{len(view):,}")
cards[1].metric("Players", view["player_name"].nunique() if "player_name" in view.columns else "n/a")
cards[2].metric("Lines", view["line"].nunique() if "line" in view.columns else "n/a")
cards[3].metric("Max over probability", format_percent(view["model_over_probability"].max()))

st.subheader("Top By Line")
if top.empty:
    show_missing(TOP_PATH)
else:
    top_view = top.copy()
    selected_lines = sorted(view["line"].dropna().unique().tolist()) if "line" in view.columns else []
    if selected_lines and "line" in top_view.columns:
        top_view = top_view[top_view["line"].isin(selected_lines)]
    st.dataframe(top_view, use_container_width=True, hide_index=True)

st.subheader("Full Ladder")
st.dataframe(
    view.sort_values(["line", "model_over_probability"], ascending=[True, False]),
    use_container_width=True,
    hide_index=True,
)
