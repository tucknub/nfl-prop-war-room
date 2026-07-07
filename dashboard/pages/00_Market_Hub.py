from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, sidebar_status, warning_banner


MARKET_STATUS_PATH = "outputs/markets/market_status.csv"
ROSTER_MAP_STATUS_PATH = "outputs/roster/current_roster_map_status.csv"
ROLE_MAP_STATUS_PATH = "outputs/roles/current_role_map_status.csv"
INJURY_MAP_STATUS_PATH = "outputs/injuries/current_injury_map_status.csv"
ODDS_MAP_STATUS_PATH = "outputs/odds/current_market_odds_status.csv"


st.set_page_config(page_title="Market Hub", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "NFL Prop War Room",
    "Multi-market NFL prop projection framework. Seven historical-test markets are active; additional markets are planned.",
    "HISTORICAL TEST ONLY",
)
warning_banner(
    "HISTORICAL TEST ONLY - NOT LIVE BETTING READY",
    "Receptions, Receiving Yards, Rushing Yards, Carries, Pass Attempts, Completions, and Passing Yards are historical-test models. They are not live betting outputs.",
)

markets = load_csv_safe(MARKET_STATUS_PATH)
roster_map_status = load_csv_safe(ROSTER_MAP_STATUS_PATH)
role_map_status = load_csv_safe(ROLE_MAP_STATUS_PATH)
injury_map_status = load_csv_safe(INJURY_MAP_STATUS_PATH)
odds_map_status = load_csv_safe(ODDS_MAP_STATUS_PATH)
if markets.empty:
    st.warning(f"Missing file: `{MARKET_STATUS_PATH}`. Run `python -m src.run_receptions_pipeline`.")
    st.stop()

section_header("Market Status", "Built and planned prop markets grouped by category.")
for category in ["Receiving", "Rushing", "Passing", "Touchdowns", "Long Plays"]:
    group = markets[markets["category"].astype(str).eq(category)]
    if group.empty:
        continue
    section_header(category)
    cols = st.columns(min(3, len(group)))
    for idx, (_, row) in enumerate(group.iterrows()):
        with cols[idx % len(cols)]:
            status = "ACTIVE" if bool(row.get("active")) else "Planned / Not Built Yet"
            metric_card(
                str(row.get("display_name", "")),
                str(row.get("projection_unit", "")),
                row.get("status", ""),
                f"{status}. {row.get('notes', '')}",
            )

section_header("Current Active Markets", "Receptions, Receiving Yards, Rushing Yards, Carries, Pass Attempts, Completions, and Passing Yards V1")
c1, c2, c3, c4 = st.columns(4)
with c1:
    metric_card("Active Models", "7", "built_historical_test")
with c2:
    metric_card("Mode", "Historical Test", "HISTORICAL TEST ONLY")
with c3:
    metric_card("Line Ladders", "Available", "PASS")
with c4:
    metric_card("Edge Engine", "Blocked", "NO-GO", "Missing odds and live gates.")
metric_card("Edge Preview Board", "Research Only", "BLOCKED", "Unified preview exists, but it is not a betting board while readiness is NO-GO.")

roster_status = str(roster_map_status["status"].iloc[0]) if not roster_map_status.empty and "status" in roster_map_status.columns else "NEEDS DATA"
section_header("Forward Team Context")
metric_card("Current Roster Map", roster_status, roster_status, "Current/projection teams must be verified independently from historical stat teams.")
role_status = str(role_map_status["status"].iloc[0]) if not role_map_status.empty and "status" in role_map_status.columns else "NEEDS DATA"
metric_card("Current Role Map", role_status, role_status, "Player workload and depth-chart roles must be verified independently from model math.")
injury_status = str(injury_map_status["status"].iloc[0]) if not injury_map_status.empty and "status" in injury_map_status.columns else "NEEDS DATA"
metric_card("Current Injury Map", injury_status, injury_status, "Player availability must be verified independently from projections.")
odds_status = str(odds_map_status["status"].iloc[0]) if not odds_map_status.empty and "status" in odds_map_status.columns else "NEEDS DATA"
metric_card("Market Odds Map", odds_status, odds_status, "Sportsbook lines and prices must be verified before any true edge calculation.")

st.markdown(
    """
    <div class="info-card">
    Dashboard pages available now: Signal Boards, Receptions, Receiving Yards, Rushing Yards, Carries,
    Pass Attempts, Completions, Passing Yards, line ladders, gates, and reports.
    Signal Boards are the user-facing research layer. Model pages remain debug/research.
    Readiness, identity, roster, role, injury, and market data pages remain admin/safety views.
    </div>
    """,
    unsafe_allow_html=True,
)

section_header("Future Markets Roadmap")
roadmap = [
    "1. Targets - receiving opportunity market adjacent to Receptions V1.",
    "2. Anytime TD - needs different event probability modeling.",
    "3. Longest Reception / Rush - needs long-play distribution modeling.",
]
st.markdown("<div class='info-card'>" + "<br>".join(roadmap) + "</div>", unsafe_allow_html=True)

with st.expander("Raw market registry export"):
    st.dataframe(presentation_table(markets), use_container_width=True, hide_index=True)
