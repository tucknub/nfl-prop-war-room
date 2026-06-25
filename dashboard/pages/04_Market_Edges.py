from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import apply_global_styles, first_existing_columns, load_csv_safe, show_table_or_missing, value_from_status


EDGES_PATH = "outputs/market_edges/receptions_market_edges.csv"
BLOCKERS_PATH = "outputs/market_edges/receptions_market_edge_blockers.csv"


st.set_page_config(page_title="Market Edges", layout="wide")
apply_global_styles()
st.title("Market Edges")

readiness = value_from_status("final_live_readiness")
if readiness != "GO":
    st.warning("Final readiness is not GO. Never display anything here as a bet.")

edges = load_csv_safe(EDGES_PATH)
blockers = load_csv_safe(BLOCKERS_PATH)

if edges.empty:
    st.error("No market edges available because odds/gates are missing.")
    st.subheader("Blockers")
    show_table_or_missing(blockers, BLOCKERS_PATH)
else:
    columns = first_existing_columns(
        edges,
        [
            "player",
            "player_name",
            "team",
            "market",
            "line",
            "sportsbook",
            "model_over_probability",
            "implied_over_probability",
            "over_edge",
            "best_side",
            "best_edge",
            "price_grade",
            "usage_status",
        ],
    )
    st.dataframe(edges[columns], use_container_width=True, hide_index=True)
