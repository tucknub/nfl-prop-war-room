from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, sidebar_status, warning_banner


MARKET_STATUS_PATH = "outputs/markets/market_status.csv"
LADDER_TOP_PATH = "outputs/market_edges/receptions_line_ladder_top_by_line.csv"
EDGE_WATCHLIST_PATH = "outputs/edge_preview/no_odds_watchlist.csv"
EDGE_BLOCKERS_PATH = "outputs/edge_preview/edge_preview_blockers.csv"


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
    "Best Overall requires odds, gates, and comparable active markets. Current output is research-only watchlists.",
)

markets = load_csv_safe(MARKET_STATUS_PATH)
active = markets[markets["active"].astype(str).str.lower().eq("true")] if not markets.empty else pd.DataFrame()
cols = st.columns(3)
with cols[0]:
    metric_card("Active Markets", len(active), "PASS" if len(active) == 1 else "REVIEW")
with cols[1]:
    metric_card("Available Markets", "7 historical-test markets", "built_historical_test")
with cols[2]:
    metric_card("Best Overall Status", "Waiting", "NO-GO", "Needs multiple markets.")

watchlist = load_csv_safe(EDGE_WATCHLIST_PATH)
edge_blockers = load_csv_safe(EDGE_BLOCKERS_PATH)
with st.container():
    section_header("Edge Preview Summary", "Research Only - No Odds - Historical Test Only.")
    summary_cols = st.columns(3)
    with summary_cols[0]:
        metric_card("Preview Watchlist Rows", len(watchlist), "Research Only")
    with summary_cols[1]:
        metric_card("Preview Blockers", len(edge_blockers), "NO-GO")
    with summary_cols[2]:
        metric_card("Qualified Edges", 0, "BLOCKED")
    if not watchlist.empty:
        preview_cols = ["market_display_name", "player_name", "team", "position", "line", "model_projection", "model_over_probability", "usage_status"]
        st.dataframe(presentation_table(watchlist[[c for c in preview_cols if c in watchlist.columns]].head(35)), use_container_width=True, hide_index=True)

st.markdown(
    """
    <div class="info-card">
    Current available markets: Receptions, Receiving Yards, Rushing Yards, Carries, Pass Attempts, Completions, and Passing Yards.
    The boards below are no-odds watchlists from line ladders.
    They are not bet lists and they are not edge boards.
    </div>
    """,
    unsafe_allow_html=True,
)

section_header("Current Receptions Watchlist", "Research Only - No Odds.")
ladder_top = load_csv_safe(LADDER_TOP_PATH)
if ladder_top.empty:
    st.warning(f"Missing file: `{LADDER_TOP_PATH}`.")
else:
    default_line = 3.5 if 3.5 in pd.to_numeric(ladder_top["line"], errors="coerce").dropna().tolist() else ladder_top["line"].iloc[0]
    selected_line = st.selectbox("Reception line", sorted(pd.to_numeric(ladder_top["line"], errors="coerce").dropna().unique()), index=0)
    view = ladder_top[pd.to_numeric(ladder_top["line"], errors="coerce").eq(float(selected_line))].head(15)
    st.dataframe(presentation_table(view), use_container_width=True, hide_index=True)

section_header("Current Receiving Yards Watchlist", "Research Only - No Odds.")
receiving_top = load_csv_safe("outputs/market_edges/receiving_yards_line_ladder_top_by_line.csv")
if receiving_top.empty:
    st.warning("Receiving Yards line ladder not available yet.")
else:
    ry_lines = sorted(pd.to_numeric(receiving_top["line"], errors="coerce").dropna().unique())
    ry_index = ry_lines.index(39.5) if 39.5 in ry_lines else 0
    ry_line = st.selectbox("Receiving yards line", ry_lines, index=ry_index)
    ry_view = receiving_top[pd.to_numeric(receiving_top["line"], errors="coerce").eq(float(ry_line))].head(15)
    st.dataframe(presentation_table(ry_view), use_container_width=True, hide_index=True)

section_header("Current Rushing Yards Watchlist", "Research Only - No Odds. Historical Test Only.")
rushing_top = load_csv_safe("outputs/market_edges/rushing_yards_line_ladder_top_by_line.csv")
if rushing_top.empty:
    st.warning("Rushing Yards line ladder not available yet.")
else:
    rush_lines = sorted(pd.to_numeric(rushing_top["line"], errors="coerce").dropna().unique())
    rush_index = rush_lines.index(39.5) if 39.5 in rush_lines else 0
    rush_line = st.selectbox("Rushing yards line", rush_lines, index=rush_index)
    rush_view = rushing_top[pd.to_numeric(rushing_top["line"], errors="coerce").eq(float(rush_line))].head(15)
    st.dataframe(presentation_table(rush_view), use_container_width=True, hide_index=True)

section_header("Current Carries Watchlist", "Research Only - No Odds. Historical Test Only.")
carries_top=load_csv_safe("outputs/market_edges/carries_line_ladder_top_by_line.csv")
if carries_top.empty: st.warning("Carries line ladder not available yet.")
else:
    carry_lines=sorted(pd.to_numeric(carries_top["line"],errors="coerce").dropna().unique()); carry_index=carry_lines.index(12.5) if 12.5 in carry_lines else 0
    carry_line=st.selectbox("Carries line",carry_lines,index=carry_index)
    carry_view=carries_top[pd.to_numeric(carries_top["line"],errors="coerce").eq(float(carry_line))].head(15)
    st.dataframe(presentation_table(carry_view),use_container_width=True,hide_index=True)

section_header("Current Pass Attempts Watchlist", "Research Only - No Odds. Historical Test Only.")
pass_top=load_csv_safe("outputs/market_edges/pass_attempts_line_ladder_top_by_line.csv")
if pass_top.empty:st.warning("Pass Attempts line ladder not available yet.")
else:
    pass_lines=sorted(pd.to_numeric(pass_top["line"],errors="coerce").dropna().unique());pass_index=pass_lines.index(31.5) if 31.5 in pass_lines else 0;pass_line=st.selectbox("Pass attempts line",pass_lines,index=pass_index);pass_view=pass_top[pd.to_numeric(pass_top["line"],errors="coerce").eq(float(pass_line))].head(15);st.dataframe(presentation_table(pass_view),use_container_width=True,hide_index=True)

section_header("Current Completions Watchlist", "Research Only - No Odds. Historical Test Only.")
completions_top=load_csv_safe("outputs/market_edges/completions_line_ladder_top_by_line.csv")
if completions_top.empty:st.warning("Completions line ladder not available yet.")
else:
    completion_lines=sorted(pd.to_numeric(completions_top["line"],errors="coerce").dropna().unique());completion_index=completion_lines.index(22.5) if 22.5 in completion_lines else 0;completion_line=st.selectbox("Completions line",completion_lines,index=completion_index);completion_view=completions_top[pd.to_numeric(completions_top["line"],errors="coerce").eq(float(completion_line))].head(15);st.dataframe(presentation_table(completion_view),use_container_width=True,hide_index=True)

section_header("Current Passing Yards Watchlist", "Research Only - No Odds. Historical Test Only.")
passing_yards_top=load_csv_safe("outputs/market_edges/passing_yards_line_ladder_top_by_line.csv")
if passing_yards_top.empty:st.warning("Passing Yards line ladder not available yet.")
else:
    passing_yards_lines=sorted(pd.to_numeric(passing_yards_top["line"],errors="coerce").dropna().unique());passing_yards_index=passing_yards_lines.index(249.5) if 249.5 in passing_yards_lines else 0;passing_yards_line=st.selectbox("Passing yards line",passing_yards_lines,index=passing_yards_index);passing_yards_view=passing_yards_top[pd.to_numeric(passing_yards_top["line"],errors="coerce").eq(float(passing_yards_line))].head(15);st.dataframe(presentation_table(passing_yards_view),use_container_width=True,hide_index=True)

section_header("Future Market Rankings")
st.markdown(
    """
    <div class="info-card">
    Placeholder sections: Targets, Anytime TD, Longest Reception, and Longest Rush.
    These remain Planned / Not Built Yet.
    </div>
    """,
    unsafe_allow_html=True,
)
