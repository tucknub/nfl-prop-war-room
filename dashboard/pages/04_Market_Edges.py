from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (
    first_existing_columns,
    inject_global_styles,
    load_csv_safe,
    metric_card,
    page_header,
    presentation_table,
    section_header,
    show_table_or_missing,
    sidebar_status,
    value_from_status,
    warning_banner,
)


EDGES_PATH = "outputs/market_edges/receptions_market_edges.csv"
BLOCKERS_PATH = "outputs/market_edges/receptions_market_edge_blockers.csv"
ODDS_STATUS_PATH = "outputs/odds/current_market_odds_status.csv"


st.set_page_config(page_title="Market Edge Engine", layout="wide")
inject_global_styles()
sidebar_status()
readiness = value_from_status("final_live_readiness")
page_header("Market Edge Engine", "Sportsbook edge layer. Blocked until odds and live gates are ready.", readiness)

warning_banner(
    "Blocked - odds and live gates required",
    "The model can estimate probabilities, but it cannot calculate true betting edge until sportsbook lines and prices are loaded.",
)

edges = load_csv_safe(EDGES_PATH)
blockers = load_csv_safe(BLOCKERS_PATH)
odds_status_df = load_csv_safe(ODDS_STATUS_PATH)
odds_status = str(odds_status_df["status"].iloc[0]) if not odds_status_df.empty and "status" in odds_status_df.columns else "NEEDS DATA"

cards = st.columns(5)
with cards[0]:
    metric_card("Final Readiness", readiness, readiness)
with cards[1]:
    metric_card("Market Odds Map", odds_status, odds_status)
with cards[2]:
    metric_card("Roster Gate", "Missing", "NEEDS DATA")
with cards[3]:
    metric_card("Role Gate", "Missing", "NEEDS DATA")
with cards[4]:
    metric_card("Injury Gate", "Missing", "NEEDS DATA")

if edges.empty:
    section_header("Why This Page Is Empty", "No market edges available because odds/gates are missing.")
    show_table_or_missing(presentation_table(blockers), BLOCKERS_PATH)
else:
    if readiness != "GO":
        warning_banner("Review only", "Rows exist, but they are not betting edges unless Final Readiness is GO.")
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
    st.dataframe(presentation_table(edges[columns]), use_container_width=True, hide_index=True)
