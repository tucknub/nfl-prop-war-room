from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import inject_signal_css
from utils import inject_global_styles, metric_card, page_header, section_header, sidebar_status, value_from_status, warning_banner


OUTPUT_ROOT = Path("outputs")


def load_csv(relative: str) -> pd.DataFrame:
    path = OUTPUT_ROOT / relative
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def show_table(relative: str, title: str, height: int = 320) -> None:
    df = load_csv(relative)
    st.markdown(f"**{title}**")
    if df.empty:
        st.info(f"Not available or empty: `outputs/{relative}`")
        return
    st.dataframe(df.head(500), use_container_width=True, hide_index=True, height=height)


st.set_page_config(page_title="Admin / Readiness", layout="wide")
inject_global_styles()
inject_signal_css()
sidebar_status()

readiness = value_from_status("final_live_readiness")
leakage = value_from_status("leakage_status")
live_output = value_from_status("live_betting_output_created")

page_header("Admin / Readiness", "Safety checks, gate status, identity checks, and current data maps.", readiness)
warning_banner("HISTORICAL TEST ONLY - NOT LIVE BETTING READY", "Readiness must remain NO-GO until every required gate is truly ready.")

cols = st.columns(3)
with cols[0]:
    metric_card("Final Readiness", readiness, readiness)
with cols[1]:
    metric_card("Leakage", leakage, leakage)
with cols[2]:
    metric_card("Live Output", live_output, live_output)

with st.expander("Live Readiness", expanded=True):
    section_header("Live Readiness")
    show_table("google_sheets/live_readiness_export.csv", "Live Readiness Export")
    show_table("google_sheets/forward_projection_blockers.csv", "Forward Projection Blockers")

with st.expander("Data Intake"):
    section_header("Data Intake")
    show_table("run_reports/latest_live_data_intake_validation.csv", "Live Data Intake Validation")
    show_table("data_intake/live_data_intake_status.csv", "Live Data Intake Status")

with st.expander("Roster Map"):
    section_header("Current Roster Map")
    show_table("roster/current_roster_map_status.csv", "Roster Map Status")
    show_table("roster/current_roster_needs_review.csv", "Roster Needs Review")
    show_table("roster/current_roster_map.csv", "Roster Map")

with st.expander("Role Map"):
    section_header("Current Role Map")
    show_table("roles/current_role_map_status.csv", "Role Map Status")
    show_table("roles/current_role_needs_review.csv", "Role Needs Review")
    show_table("roles/current_role_map.csv", "Role Map")

with st.expander("Injury Map"):
    section_header("Current Injury Map")
    show_table("injuries/current_injury_map_status.csv", "Injury Map Status")
    show_table("injuries/current_injury_needs_review.csv", "Injury Needs Review")
    show_table("injuries/current_injury_map.csv", "Injury Map")

with st.expander("Market Odds Map"):
    section_header("Market Odds Map")
    show_table("odds/current_market_odds_status.csv", "Market Odds Status")
    show_table("odds/current_market_odds_needs_review.csv", "Market Odds Needs Review")
    show_table("odds/current_market_odds_map.csv", "Market Odds Map")

with st.expander("Gate Status"):
    section_header("Gate Status")
    show_table("google_sheets/import_manifest.csv", "Google Sheets Import Manifest")
    show_table("gate_inputs_normalized/gate_input_status.csv", "Gate Input Status")

with st.expander("Identity Warnings"):
    section_header("Identity Warnings")
    show_table("identity/gate_identity_match_report.csv", "Gate Identity Match Report")
    show_table("identity/unmatched_gate_rows.csv", "Unmatched Gate Rows")
    show_table("identity/duplicate_name_warnings.csv", "Duplicate Name Warnings")

with st.expander("Edge Dry Run Status"):
    section_header("Edge Dry Run")
    show_table("run_reports/latest_edge_dry_run.csv", "Edge Dry Run Validation")
    show_table("market_edges/receptions_market_edge_blockers.csv", "Market Edge Blockers")
