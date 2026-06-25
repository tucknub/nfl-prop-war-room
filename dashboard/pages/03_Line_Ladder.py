from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (
    filter_by_multiselect,
    filter_by_search,
    format_percent,
    inject_global_styles,
    load_csv_safe,
    metric_card,
    page_header,
    player_card,
    presentation_table,
    section_header,
    show_missing,
    sidebar_status,
    warning_banner,
)


LADDER_PATH = "outputs/market_edges/receptions_line_ladder.csv"
TOP_PATH = "outputs/market_edges/receptions_line_ladder_top_by_line.csv"


st.set_page_config(page_title="Reception Line Ladder", layout="wide")
inject_global_styles()
sidebar_status()
page_header(
    "Reception Line Ladder",
    "Model-only probability ladder. Research only - odds are not included.",
    "HISTORICAL TEST ONLY",
)
warning_banner(
    "Odds required for betting edge",
    "The ladder shows model probabilities for common lines, but sportsbook prices are still required before edge can be calculated.",
)

ladder = load_csv_safe(LADDER_PATH)
top = load_csv_safe(TOP_PATH)
if ladder.empty:
    show_missing(LADDER_PATH)
    st.stop()

view = ladder.copy()
available_lines = sorted(pd.to_numeric(view["line"], errors="coerce").dropna().unique().tolist())
default_index = available_lines.index(3.5) if 3.5 in available_lines else 0
selected_line = st.selectbox("Primary line", available_lines, index=default_index)

filters = st.columns(4)
with filters[0]:
    view = filter_by_multiselect(view, "team", "Team")
with filters[1]:
    view = filter_by_multiselect(view, "position", "Position")
with filters[2]:
    min_prob = st.slider("Minimum over probability", 0.0, 1.0, 0.0, 0.01)
    view = view[pd.to_numeric(view["model_over_probability"], errors="coerce").fillna(0) >= min_prob]
with filters[3]:
    view = filter_by_search(view, "player_name")

selected = view[pd.to_numeric(view["line"], errors="coerce").eq(float(selected_line))].copy()

cards = st.columns(4)
with cards[0]:
    metric_card("Rows", f"{len(view):,}")
with cards[1]:
    metric_card("Players", view["player_name"].nunique() if "player_name" in view.columns else "n/a")
with cards[2]:
    metric_card("Lines", view["line"].nunique() if "line" in view.columns else "n/a")
with cards[3]:
    metric_card("Max Over Probability", format_percent(view["model_over_probability"].max()))

section_header(f"Top 10 At {selected_line}", "Highest model over probability for the selected reception line.")
top_selected = selected.sort_values("model_over_probability", ascending=False).head(10)
card_cols = st.columns(5)
for idx, (_, row) in enumerate(top_selected.head(5).iterrows()):
    with card_cols[idx]:
        player_card(
            str(row.get("player_name", "")),
            str(row.get("team", "")),
            str(row.get("position", "")),
            format_percent(row.get("model_over_probability")),
            row.get("usage_status", ""),
        )

chart, table_col = st.columns([1.2, 1])
with chart:
    section_header("Selected-Line Probability Chart")
    chart_data = top_selected.set_index("player_name")["model_over_probability"]
    st.bar_chart(chart_data)
with table_col:
    section_header("Selected-Line Table")
    cols = [
        "player_name",
        "team",
        "position",
        "line",
        "calibrated_projection",
        "model_over_probability",
        "model_under_probability",
        "confidence_tier",
        "usage_status",
    ]
    st.dataframe(presentation_table(top_selected[[c for c in cols if c in top_selected.columns]]), use_container_width=True, hide_index=True)

section_header("Top By Line", "Top 25 players for each common reception line.")
if top.empty:
    show_missing(TOP_PATH)
else:
    st.dataframe(presentation_table(top), use_container_width=True, hide_index=True)

with st.expander("Full ladder table"):
    st.dataframe(
        presentation_table(view.sort_values(["line", "model_over_probability"], ascending=[True, False])),
        use_container_width=True,
        hide_index=True,
    )
