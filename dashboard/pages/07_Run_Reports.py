from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_markdown_safe, metric_card, page_header, resolve_path, section_header, sidebar_status


REPORTS = [
    ("Pipeline Report", "outputs/run_reports/latest_receptions_pipeline_report.md", "Latest full pipeline run."),
    ("Safety Validation", "outputs/run_reports/latest_receptions_safety_validation.md", "Safety assertions and failure count."),
    ("Forward Dry Run", "outputs/run_reports/latest_forward_projection_dry_run.md", "Forward-mode blocker and fixture validation."),
    ("Market Edge Report", "outputs/run_reports/latest_market_edge_report.md", "Odds/edge state and blockers."),
    ("Market Odds Map Validation", "outputs/run_reports/latest_market_odds_map_validation.md", "Sportsbook odds mapping gate validation."),
    ("Edge Preview Board Report", "outputs/run_reports/latest_edge_preview_board_report.md", "Unified edge-preview board status."),
    ("Edge Preview Board Validation", "outputs/run_reports/latest_edge_preview_board_validation.md", "Safety validation for the edge preview board."),
    ("Edge Dry Run", "outputs/run_reports/latest_edge_dry_run.md", "Synthetic end-to-end edge decision validation."),
    ("Live Data Intake", "outputs/run_reports/latest_live_data_intake_report.md", "Real-data intake checklist and blockers."),
    ("Live Data Intake Validation", "outputs/run_reports/latest_live_data_intake_validation.md", "Safety validation for intake reporting."),
    ("Line Ladder Report", "outputs/run_reports/latest_line_ladder_report.md", "Odds-free ladder summary."),
    ("Stable Snapshot", "outputs/run_reports/STABLE_RECEPTIONS_V1_HISTORICAL_TEST_SNAPSHOT.md", "Rollback point before live data integration."),
    ("Next Steps", "outputs/run_reports/STABLE_RECEPTIONS_V1_NEXT_STEPS.md", "Safe next actions and do-not-do list."),
]


st.set_page_config(page_title="Run Reports & Audit Trail", layout="wide")
inject_global_styles()
sidebar_status()
page_header("Run Reports & Audit Trail", "Expandable reports for validation, blockers, and stable snapshot records.", "PASS")

section_header("Report Cards")
cols = st.columns(4)
for idx, (name, report, note) in enumerate(REPORTS):
    path = resolve_path(report)
    with cols[idx % 4]:
        metric_card(name, "Available" if path.exists() else "Missing", "PASS" if path.exists() else "FAIL", note)

section_header("Reports")
for name, report, note in REPORTS:
    path = resolve_path(report)
    with st.expander(name, expanded=False):
        st.caption(note)
        text = load_markdown_safe(report)
        if not text:
            st.warning(f"Missing file: `{path}`")
        else:
            preview = " ".join(text.strip().splitlines()[:3])
            st.info(preview[:240] + ("..." if len(preview) > 240 else ""))
            st.markdown(text)
