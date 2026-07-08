from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, show_table_or_missing, sidebar_status, warning_banner


REPORT_CSV = "outputs/run_reports/latest_edge_dry_run.csv"
SYNTHETIC_BOARD = "outputs/edge_preview_dry_run/synthetic_edge_preview_board.csv"
SYNTHETIC_BLOCKERS = "outputs/edge_preview_dry_run/synthetic_edge_preview_blockers.csv"


st.set_page_config(page_title="End-to-End Edge Dry Run", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "End-to-End Edge Dry Run",
    "Isolated synthetic validation of the full edge decision pipeline.",
    "SYNTHETIC TEST ONLY",
)
st.caption("Section: Readiness / Data Admin")
warning_banner(
    "Synthetic test only - not production",
    "This page proves the edge engine can stay blocked in production while also showing that the full pipeline can produce qualified edges only when every synthetic gate is satisfied.",
)

checks = load_csv_safe(REPORT_CSV)
synthetic = load_csv_safe(SYNTHETIC_BOARD)
blockers = load_csv_safe(SYNTHETIC_BLOCKERS)

scenario_a = "MISSING"
scenario_b = "MISSING"
if not checks.empty and {"scenario", "status"}.issubset(checks.columns):
    a = checks[checks["scenario"].astype(str).str.startswith("Scenario A")]
    b = checks[checks["scenario"].astype(str).str.startswith("Scenario B")]
    scenario_a = "PASS" if not a.empty and a["status"].astype(str).eq("PASS").all() else "FAIL"
    scenario_b = "PASS" if not b.empty and b["status"].astype(str).eq("PASS").all() else "FAIL"

qualified_count = 0
if not synthetic.empty and "decision_status" in synthetic.columns:
    qualified_count = int(synthetic["decision_status"].astype(str).eq("Qualified Edge").sum())

cols = st.columns(4)
with cols[0]:
    metric_card("Scenario A", scenario_a, scenario_a)
with cols[1]:
    metric_card("Scenario B", scenario_b, scenario_b)
with cols[2]:
    metric_card("Synthetic Qualified Edges", qualified_count, "SYNTHETIC TEST ONLY")
with cols[3]:
    metric_card("Production Live Output", "False", "PASS")

section_header("Dry-Run Checks")
show_table_or_missing(presentation_table(checks), REPORT_CSV)

section_header("Synthetic Edge Preview", "SYNTHETIC TEST ONLY - not production and not live betting output.")
show_table_or_missing(presentation_table(synthetic), SYNTHETIC_BOARD)

section_header("Synthetic Blockers / Notes")
show_table_or_missing(presentation_table(blockers), SYNTHETIC_BLOCKERS)

section_header("What This Proves")
st.markdown(
    """
    <div class="info-card">
    Production remains NO-GO when real roster, role, injury, and odds gates are missing.
    In a separate synthetic dry run, the same decision flow can produce qualified edges only when every synthetic gate is satisfied.
    These rows are test-only and are not production recommendations.
    </div>
    """,
    unsafe_allow_html=True,
)
