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
    warning_banner,
)


EDGE_PATH = "outputs/edge_preview/edge_preview_board.csv"
BLOCKERS_PATH = "outputs/edge_preview/edge_preview_blockers.csv"
WATCHLIST_PATH = "outputs/edge_preview/no_odds_watchlist.csv"


st.set_page_config(page_title="Edge Preview Board", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "Edge Preview Board",
    "Decision-style preview for how model probabilities, odds, and gates will combine later.",
    "NO-GO",
)
warning_banner(
    "NO-GO - EDGE PREVIEW ONLY",
    "This page shows how projections, model probabilities, odds, and gate checks will combine once real odds and live-context data are loaded. It is not a betting board.",
)

edge = load_csv_safe(EDGE_PATH)
blockers = load_csv_safe(BLOCKERS_PATH)
watchlist = load_csv_safe(WATCHLIST_PATH)

cols = st.columns(4)
with cols[0]:
    metric_card("True Edge Rows", len(edge), "BLOCKED" if edge.empty else "REVIEW")
with cols[1]:
    metric_card("Watchlist Rows", len(watchlist), "Research Only")
with cols[2]:
    metric_card("Blockers", len(blockers), "NO-GO")
with cols[3]:
    metric_card("Live Output", "False", "PASS")

section_header("Readiness / Blockers", "Every listed blocker must clear before a row can become actionable.")
show_table_or_missing(presentation_table(blockers), BLOCKERS_PATH)

section_header("No-Odds Watchlist By Market", "Research Only - No Odds - Historical Test Only.")
if watchlist.empty:
    show_table_or_missing(presentation_table(watchlist), WATCHLIST_PATH)
else:
    markets = sorted(watchlist["market_display_name"].dropna().astype(str).unique()) if "market_display_name" in watchlist.columns else []
    selected = st.multiselect("Markets", markets, default=markets)
    view = watchlist[watchlist["market_display_name"].astype(str).isin(selected)] if selected else watchlist
    columns = first_existing_columns(
        view,
        [
            "market_display_name",
            "player_name",
            "team",
            "position",
            "line",
            "model_projection",
            "model_over_probability",
            "decision_status",
            "usage_status",
            "notes",
        ],
    )
    st.dataframe(presentation_table(view[columns].head(250)), use_container_width=True, hide_index=True)

section_header("True Edge Table", "Rows remain blocked unless Final Readiness = GO.")
if edge.empty:
    st.info("No true edge rows exist because real sportsbook odds are not loaded.")
else:
    show_table_or_missing(presentation_table(edge), EDGE_PATH)

section_header("How Edge Works")
st.markdown(
    """
    <div class="info-card">
    Future true edge is calculated as model probability minus sportsbook implied probability.
    A row cannot become actionable until odds are matched, roster/role/injury/identity gates pass,
    leakage checks pass, and Final Readiness is GO.
    </div>
    """,
    unsafe_allow_html=True,
)

section_header("Before Actionable")
st.markdown(
    """
    <div class="info-card">
    Required: forward projection mode, Market Odds Map READY, Current Roster Map READY,
    Current Role Map READY, Current Injury Map READY, identity validation clean, safety validation PASS,
    and no live-output blocker.
    </div>
    """,
    unsafe_allow_html=True,
)
