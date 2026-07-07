from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, show_table_or_missing, sidebar_status, warning_banner


READINESS_PATH = "outputs/google_sheets/live_readiness_export.csv"
STATUS_PATH = "outputs/run_reports/latest_receptions_pipeline_status.csv"
BLOCKERS_PATH = "outputs/google_sheets/forward_projection_blockers.csv"
ROSTER_MAP_STATUS_PATH = "outputs/roster/current_roster_map_status.csv"
ROLE_MAP_STATUS_PATH = "outputs/roles/current_role_map_status.csv"
INJURY_MAP_STATUS_PATH = "outputs/injuries/current_injury_map_status.csv"
ODDS_MAP_STATUS_PATH = "outputs/odds/current_market_odds_status.csv"


st.set_page_config(page_title="Live Readiness", layout="wide")
inject_global_styles()
sidebar_status()

readiness = load_csv_safe(READINESS_PATH)
status = load_csv_safe(STATUS_PATH)
blockers = load_csv_safe(BLOCKERS_PATH)
roster_map_status = load_csv_safe(ROSTER_MAP_STATUS_PATH)
role_map_status = load_csv_safe(ROLE_MAP_STATUS_PATH)
injury_map_status = load_csv_safe(INJURY_MAP_STATUS_PATH)
odds_map_status = load_csv_safe(ODDS_MAP_STATUS_PATH)

if not readiness.empty and {"Gate", "Status"}.issubset(readiness.columns):
    final = readiness.loc[readiness["Gate"].eq("Final Betting Use"), "Status"]
    final_status = final.iloc[0] if not final.empty else "UNKNOWN"
    leakage = readiness.loc[readiness["Gate"].eq("History Audit"), "Status"]
    leakage_status = leakage.iloc[0] if not leakage.empty else "UNKNOWN"
else:
    final_row = status[status.get("check_name", "").astype(str).eq("final_live_readiness")] if not status.empty else status
    final_status = final_row["value"].iloc[0] if not final_row.empty and "value" in final_row.columns else "UNKNOWN"
    leakage_row = status[status.get("check_name", "").astype(str).eq("leakage_status")] if not status.empty else status
    leakage_status = leakage_row["value"].iloc[0] if not leakage_row.empty and "value" in leakage_row.columns else "UNKNOWN"

page_header("Live Readiness", "The control-room status board for projection and betting readiness.", final_status)

cards = st.columns(3)
with cards[0]:
    metric_card("Overall Status", final_status, final_status)
with cards[1]:
    metric_card("Leakage", leakage_status, leakage_status)
with cards[2]:
    metric_card("Blocked Gates", len(blockers) if not blockers.empty else 0, "NO-GO" if str(final_status) != "GO" else "GO")
metric_card("Edge Preview Board", "Research Only", "BLOCKED" if str(final_status) != "GO" else "REVIEW", "Preview rows cannot become actionable until Final Readiness is GO.")

if str(final_status) != "GO":
    warning_banner("HISTORICAL TEST ONLY - NOT LIVE BETTING READY", "Resolve every blocker and validate forward mode before treating this as live.")

section_header("Gate Table", "Action needed, current values, sources, and notes.")
show_table_or_missing(presentation_table(readiness), READINESS_PATH)

section_header("Current Roster Map")
roster_status = str(roster_map_status["status"].iloc[0]) if not roster_map_status.empty and "status" in roster_map_status.columns else "NEEDS DATA"
metric_card("Current Roster Map", roster_status, roster_status, "Historical teams cannot be used as current forward-projection teams without verification.")
role_status = str(role_map_status["status"].iloc[0]) if not role_map_status.empty and "status" in role_map_status.columns else "NEEDS DATA"
metric_card("Current Role Map", role_status, role_status, "A verified team is insufficient when projected workload remains unclear.")
injury_status = str(injury_map_status["status"].iloc[0]) if not injury_map_status.empty and "status" in injury_map_status.columns else "NEEDS DATA"
metric_card("Current Injury Map", injury_status, injury_status, "A verified role is insufficient when availability remains unclear.")
odds_status = str(odds_map_status["status"].iloc[0]) if not odds_map_status.empty and "status" in odds_map_status.columns else "NEEDS DATA"
metric_card("Market Odds Map", odds_status, odds_status, "True edge requires sportsbook lines, prices, and implied probabilities.")

section_header("Dashboard Zones")
st.markdown(
    """
    <div class="info-card">
    Signal Boards are user-facing research heatmaps. Model Outputs are debug/research tables.
    Readiness and Gate pages are the control-room safety layer. None of these pages can make the system live while Final Readiness is NO-GO.
    </div>
    """,
    unsafe_allow_html=True,
)

section_header("Blocking Gates")
show_table_or_missing(presentation_table(blockers), BLOCKERS_PATH)

if not readiness.empty:
    cols = [col for col in ["Gate", "Action Needed", "Current Value", "Source", "Notes"] if col in readiness.columns]
    if cols:
        section_header("Action Needed")
        st.dataframe(presentation_table(readiness[cols]), use_container_width=True, hide_index=True)
