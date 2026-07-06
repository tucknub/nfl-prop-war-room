from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (
    inject_global_styles,
    load_csv_safe,
    metric_card,
    page_header,
    presentation_table,
    section_header,
    show_table_or_missing,
    sidebar_status,
    warning_banner,
)


MAP = "outputs/odds/current_market_odds_map.csv"
STATUS = "outputs/odds/current_market_odds_status.csv"
REVIEW = "outputs/odds/current_market_odds_needs_review.csv"


st.set_page_config(page_title="Market Odds Mapping", layout="wide")
inject_global_styles()
sidebar_status()

page_header("Market Odds Mapping", "Sportsbook line and price normalization for future edge calculation.", "NO-GO")
warning_banner(
    "True edge calculation blocked until odds and all live gates are verified",
    "Odds mapping is a data gate. It does not create live betting output while Final Readiness is NO-GO.",
)

mapped = load_csv_safe(MAP)
status = load_csv_safe(STATUS)
review = load_csv_safe(REVIEW)


def value(column: str) -> int:
    if status.empty or column not in status.columns:
        return 0
    numeric = pd.to_numeric(status[column], errors="coerce").iloc[0]
    return 0 if pd.isna(numeric) else int(numeric)


overall = str(status.status.iloc[0]) if not status.empty and "status" in status.columns else "NEEDS DATA"
items = [
    ("Odds Rows Loaded", value("odds_rows_loaded"), overall),
    ("READY", value("ready_rows"), "READY"),
    ("NEEDS REVIEW", value("needs_review_rows"), "NEEDS REVIEW"),
    ("NEEDS DATA", value("needs_data_rows"), "NEEDS DATA"),
    ("BLOCKED", value("blocked_rows"), "BLOCKED"),
    ("Active Markets Covered", value("active_markets_covered"), "INFO"),
    ("Sportsbooks Loaded", value("sportsbooks_loaded"), "INFO"),
    ("Manual Overrides", value("manual_overrides"), "REVIEW"),
]

cols = st.columns(4)
for index, (label, metric, state) in enumerate(items):
    with cols[index % 4]:
        metric_card(label, metric, state)

st.markdown(
    '<div class="info-card">Model probability is only half the edge calculation. Odds mapping converts sportsbook lines and prices into implied probabilities so the system can compare model probability to market price.</div>',
    unsafe_allow_html=True,
)

section_header("Current Market Odds Map", f"Overall mapping status: {overall}")
show_table_or_missing(presentation_table(mapped), MAP)

section_header("Needs Review")
show_table_or_missing(presentation_table(review), REVIEW)

with st.expander("Market odds map status details"):
    show_table_or_missing(presentation_table(status), STATUS)
