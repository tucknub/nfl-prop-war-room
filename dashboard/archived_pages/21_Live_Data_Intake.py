from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, show_table_or_missing, sidebar_status, warning_banner


CHECKLIST = "outputs/data_intake/live_data_intake_checklist.csv"
STATUS = "outputs/data_intake/live_data_intake_status.csv"
BLOCKERS = "outputs/edge_preview/edge_preview_blockers.csv"

COMMANDS = """python -m src.run_prop_war_room_pipeline
python -m src.validate_receptions_safety
python -m src.validate_forward_projection_dry_run
python -m src.load.validate_current_roster_map
python -m src.load.validate_current_role_map
python -m src.load.validate_current_injury_map
python -m src.load.validate_market_odds_map
python -m src.export.validate_edge_preview_board
python -m src.validate_edge_dry_run"""


st.set_page_config(page_title="Live Data Intake", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "Live Data Intake",
    "Checklist and status workflow for loading real roster, role, injury, and odds data safely.",
    "NO-GO",
)
st.caption("Section: Readiness / Data Admin")
warning_banner(
    "This is the bridge from historical test to future live-readiness. It does not make the model live by itself.",
    "Only real non-template data can move live-context gates toward READY. Historical-test warnings remain in force.",
)

checklist = load_csv_safe(CHECKLIST)
status = load_csv_safe(STATUS)
blockers = load_csv_safe(BLOCKERS)

needs_data = int(status["current_status"].astype(str).eq("NEEDS DATA").sum()) if not status.empty and "current_status" in status.columns else 0
needs_review = int(status["current_status"].astype(str).eq("NEEDS REVIEW").sum()) if not status.empty and "current_status" in status.columns else 0
ready = int(status["current_status"].astype(str).eq("READY").sum()) if not status.empty and "current_status" in status.columns else 0
passing = int(status["current_status"].astype(str).eq("PASS").sum()) if not status.empty and "current_status" in status.columns else 0

cols = st.columns(5)
with cols[0]:
    metric_card("Gates Needing Data", needs_data, "NEEDS DATA")
with cols[1]:
    metric_card("Gates Needing Review", needs_review, "NEEDS REVIEW")
with cols[2]:
    metric_card("Gates Ready", ready, "READY" if ready else "NO-GO")
with cols[3]:
    metric_card("Validators Passing", passing, "PASS")
with cols[4]:
    metric_card("True Edge", "Blocked", "NO-GO")

section_header("Intake Checklist")
show_table_or_missing(presentation_table(checklist), CHECKLIST)

section_header("Current Intake Status")
show_table_or_missing(presentation_table(status), STATUS)

section_header("Files You Need To Fill")
if checklist.empty:
    show_table_or_missing(checklist, CHECKLIST)
else:
    file_rows = checklist[checklist["real_data_required"].astype(str).eq("Yes")].copy()
    cols_to_show = ["gate", "required_file_folder", "template_file", "required_columns", "notes"]
    st.dataframe(presentation_table(file_rows[[c for c in cols_to_show if c in file_rows.columns]]), use_container_width=True, hide_index=True)

section_header("Commands To Run After Filling Data")
st.code(COMMANDS, language="powershell")

section_header("What Still Blocks GO")
show_table_or_missing(presentation_table(blockers), BLOCKERS)
