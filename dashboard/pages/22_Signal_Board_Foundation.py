from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import build_heatmap_styler, load_signal_csv, render_signal_table
from utils import inject_global_styles, metric_card, page_header, presentation_table, section_header, show_table_or_missing, sidebar_status, warning_banner


MASTER = "outputs/signal_boards/player_week_signal_master.csv"
SLATE = "outputs/signal_boards/slate_signal_board.csv"
RECEIVING = "outputs/signal_boards/receiving_signal_board.csv"
RUSHING = "outputs/signal_boards/rushing_signal_board.csv"
PASSING = "outputs/signal_boards/passing_signal_board.csv"
BLOCKED = "outputs/signal_boards/blocked_review_board.csv"
INVENTORY = "outputs/signal_boards/signal_data_inventory.csv"

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

SLATE_COLUMNS = [
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
    "data_quality_score",
    "top_signal_reason",
    "review_reason",
]


st.set_page_config(page_title="Signal Board Foundation", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "Signal Board Foundation",
    "Administrative view of the source signal layer that powers the user-facing heatmap boards.",
    "LIMITED V1",
)
warning_banner(
    "LIMITED V1 - projections and sourced context only",
    "Opponent fit, weather, game script, practice trends, and live role/injury data remain limited until real sources are loaded.",
)

master = load_signal_csv(MASTER)
slate = load_signal_csv(SLATE)
receiving = load_signal_csv(RECEIVING)
rushing = load_signal_csv(RUSHING)
passing = load_signal_csv(PASSING)
blocked = load_signal_csv(BLOCKED)
inventory = load_signal_csv(INVENTORY)

unavailable_metrics = 0
if not inventory.empty and "available_now" in inventory.columns:
    unavailable_metrics = int((~inventory["available_now"].astype(str).str.lower().isin(["yes", "true", "1"])).sum())

review_block_rows = 0
if not master.empty and "signal_tier" in master.columns:
    review_block_rows = int(master["signal_tier"].astype(str).isin(["REVIEW", "BLOCKED", "INSUFFICIENT_DATA"]).sum())

cols = st.columns(7)
with cols[0]:
    metric_card("Master Rows", len(master), "PASS" if len(master) else "FAIL")
with cols[1]:
    metric_card("Slate Rows", len(slate), "PASS" if len(slate) else "FAIL")
with cols[2]:
    metric_card("Receiving Rows", len(receiving), "PASS" if len(receiving) else "FAIL")
with cols[3]:
    metric_card("Rushing Rows", len(rushing), "PASS" if len(rushing) else "FAIL")
with cols[4]:
    metric_card("Passing Rows", len(passing), "PASS" if len(passing) else "FAIL")
with cols[5]:
    metric_card("Unavailable Metrics", unavailable_metrics, "NEEDS SOURCE" if unavailable_metrics else "PASS")
with cols[6]:
    metric_card("Review/Block Rows", review_block_rows, "REVIEW" if review_block_rows else "PASS")

section_header("Top 25 Slate Signals", "Compact heatmap preview from the slate signal board.")
if slate.empty:
    show_table_or_missing(slate, SLATE)
else:
    render_signal_table(
        slate.sort_values("overall_signal_score", ascending=False).head(25),
        SCORE_COLUMNS,
        SLATE_COLUMNS,
        "Slate Heatmap Preview",
        "Scores are read from the existing signal board output.",
    )

section_header("Signal Data Inventory", "Availability and reliability for the current signal inputs.")
if inventory.empty:
    show_table_or_missing(inventory, INVENTORY)
else:
    inventory_columns = [
        col
        for col in [
            "metric_name",
            "available_now",
            "implementation_status",
            "reliability_tier",
            "source",
            "notes",
        ]
        if col in inventory.columns
    ]
    styled = build_heatmap_styler(
        inventory[inventory_columns],
        [],
        ["available_now", "implementation_status", "reliability_tier"],
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

section_header("Board Output Inventory")
inventory_rows = pd.DataFrame(
    [
        {"board": "Master", "file": MASTER, "rows": len(master), "purpose": "Source-of-truth player-week signal table"},
        {"board": "Slate", "file": SLATE, "rows": len(slate), "purpose": "Top-level player signal view"},
        {"board": "Receiving", "file": RECEIVING, "rows": len(receiving), "purpose": "Receiving player signal view"},
        {"board": "Rushing", "file": RUSHING, "rows": len(rushing), "purpose": "Rushing player signal view"},
        {"board": "Passing", "file": PASSING, "rows": len(passing), "purpose": "Quarterback passing signal view"},
        {"board": "Review", "file": BLOCKED, "rows": len(blocked), "purpose": "Rows requiring review or blocked context"},
    ]
)
st.dataframe(presentation_table(inventory_rows), use_container_width=True, hide_index=True)
