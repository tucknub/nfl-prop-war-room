from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, show_table_or_missing, sidebar_status, warning_banner


MASTER = "outputs/signal_boards/player_week_signal_master.csv"
SLATE = "outputs/signal_boards/slate_signal_board.csv"
RECEIVING = "outputs/signal_boards/receiving_signal_board.csv"
RUSHING = "outputs/signal_boards/rushing_signal_board.csv"
PASSING = "outputs/signal_boards/passing_signal_board.csv"
BLOCKED = "outputs/signal_boards/blocked_review_board.csv"
INVENTORY = "outputs/signal_boards/signal_data_inventory.csv"


st.set_page_config(page_title="NFL Signal Board Foundation", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "NFL Signal Board Foundation",
    "Source-of-truth player-week signal layer for future heatmap and drilldown boards.",
    "LIMITED V1",
)
warning_banner(
    "Limited V1 - projections and available context only",
    "Opponent fit, weather, game script, practice trends, and live role/injury data are not fully sourced yet.",
)

master = load_csv_safe(MASTER)
slate = load_csv_safe(SLATE)
receiving = load_csv_safe(RECEIVING)
rushing = load_csv_safe(RUSHING)
passing = load_csv_safe(PASSING)
blocked = load_csv_safe(BLOCKED)
inventory = load_csv_safe(INVENTORY)

tiers = master["signal_tier"].astype(str) if not master.empty and "signal_tier" in master.columns else pd.Series(dtype=str)
missing_total = int(pd.to_numeric(master.get("missing_signal_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not master.empty else 0
live_context = "NEEDS DATA"
if not master.empty and {"roster_status", "role_status", "injury_status"}.issubset(master.columns):
    live_context = f"Roster {master['roster_status'].iloc[0]} / Role {master['role_status'].iloc[0]} / Injury {master['injury_status'].iloc[0]}"

cols = st.columns(5)
with cols[0]:
    metric_card("Master Rows", len(master), "PASS" if len(master) else "FAIL")
with cols[1]:
    metric_card("Strong/Good", int(tiers.isin(["ELITE_SIGNAL", "STRONG_SIGNAL", "GOOD_SIGNAL"]).sum()), "LIMITED V1")
with cols[2]:
    metric_card("Watch", int(tiers.eq("WATCH").sum()), "WATCH")
with cols[3]:
    metric_card("Review", int(tiers.isin(["REVIEW", "BLOCKED", "INSUFFICIENT_DATA"]).sum()), "REVIEW")
with cols[4]:
    metric_card("Missing Signals", missing_total, "NEEDS SOURCE")

metric_card("Live Context Status", live_context, "NEEDS DATA", "Production live roster, role, and injury gates are not loaded.")

st.markdown(
    '<div class="info-card">This is the source-of-truth signal layer. Future heatmap boards should be rendered from this master table, not recomputed independently.</div>',
    unsafe_allow_html=True,
)

section_header("Slate Signal Board")
show_table_or_missing(presentation_table(slate.head(150)), SLATE)

section_header("Receiving Signal Board")
show_table_or_missing(presentation_table(receiving.head(150)), RECEIVING)

section_header("Rushing Signal Board")
show_table_or_missing(presentation_table(rushing.head(150)), RUSHING)

section_header("Passing Signal Board")
show_table_or_missing(presentation_table(passing.head(150)), PASSING)

section_header("Blocked / Review Board")
show_table_or_missing(presentation_table(blocked.head(150)), BLOCKED)

section_header("Signal Data Inventory")
show_table_or_missing(presentation_table(inventory), INVENTORY)
