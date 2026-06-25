from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, sidebar_status, warning_banner


MARKET_STATUS_PATH = "outputs/markets/market_status.csv"
LADDER_TOP_PATH = "outputs/market_edges/receptions_line_ladder_top_by_line.csv"


st.set_page_config(page_title="Best Overall Board", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "Best Overall Board",
    "Multi-market rankings will appear here after more markets are active and validated.",
    "Planned / Not Built Yet",
)
warning_banner(
    "No bets here",
    "Best Overall requires multiple active markets and Final Readiness GO. Current output is a Receptions watchlist only.",
)

markets = load_csv_safe(MARKET_STATUS_PATH)
active = markets[markets["active"].astype(str).str.lower().eq("true")] if not markets.empty else pd.DataFrame()
cols = st.columns(3)
with cols[0]:
    metric_card("Active Markets", len(active), "PASS" if len(active) == 1 else "REVIEW")
with cols[1]:
    metric_card("Current Available Market", "Receptions", "built")
with cols[2]:
    metric_card("Best Overall Status", "Waiting", "NO-GO", "Needs multiple markets.")

st.markdown(
    """
    <div class="info-card">
    Current available market: Receptions only. The board below is a no-odds Receptions watchlist from the line ladder.
    It is not a bet list and it is not an edge board.
    </div>
    """,
    unsafe_allow_html=True,
)

section_header("Current Receptions Watchlist", "Top model over probabilities from the no-odds line ladder.")
ladder_top = load_csv_safe(LADDER_TOP_PATH)
if ladder_top.empty:
    st.warning(f"Missing file: `{LADDER_TOP_PATH}`.")
else:
    default_line = 3.5 if 3.5 in pd.to_numeric(ladder_top["line"], errors="coerce").dropna().tolist() else ladder_top["line"].iloc[0]
    selected_line = st.selectbox("Reception line", sorted(pd.to_numeric(ladder_top["line"], errors="coerce").dropna().unique()), index=0)
    view = ladder_top[pd.to_numeric(ladder_top["line"], errors="coerce").eq(float(selected_line))].head(15)
    st.dataframe(presentation_table(view), use_container_width=True, hide_index=True)

section_header("Future Market Rankings")
st.markdown(
    """
    <div class="info-card">
    Placeholder sections: Receiving Yards, Rushing Yards, Passing Yards, Completions, Pass Attempts, Carries,
    Targets, Anytime TD, Longest Reception, and Longest Rush. These remain Planned / Not Built Yet.
    </div>
    """,
    unsafe_allow_html=True,
)
