from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import apply_global_styles, load_markdown_safe, resolve_path


REPORTS = [
    "outputs/run_reports/latest_receptions_pipeline_report.md",
    "outputs/run_reports/latest_receptions_safety_validation.md",
    "outputs/run_reports/latest_forward_projection_dry_run.md",
    "outputs/run_reports/latest_market_edge_report.md",
    "outputs/run_reports/latest_line_ladder_report.md",
    "outputs/run_reports/STABLE_RECEPTIONS_V1_HISTORICAL_TEST_SNAPSHOT.md",
    "outputs/run_reports/STABLE_RECEPTIONS_V1_NEXT_STEPS.md",
]


st.set_page_config(page_title="Run Reports", layout="wide")
apply_global_styles()
st.title("Run Reports")

for report in REPORTS:
    path = resolve_path(report)
    with st.expander(path.name, expanded=False):
        text = load_markdown_safe(report)
        if not text:
            st.warning(f"Missing file: `{path}`")
        else:
            st.markdown(text)
