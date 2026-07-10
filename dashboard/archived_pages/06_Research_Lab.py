from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import build_signal_heatmap, inject_signal_css
from utils import inject_global_styles, page_header, section_header, sidebar_status, warning_banner


OUTPUT_ROOT = Path("outputs")


def load_csv(relative: str) -> pd.DataFrame:
    path = OUTPUT_ROOT / relative
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def show_table(relative: str, title: str, score_columns: list[str] | None = None, height: int = 320) -> None:
    df = load_csv(relative)
    st.markdown(f"**{title}**")
    if df.empty:
        st.info(f"Not available: `outputs/{relative}`")
        return
    view = df.head(300)
    if score_columns:
        st.dataframe(build_signal_heatmap(view, [col for col in score_columns if col in view.columns]), use_container_width=True, hide_index=True, height=height)
    else:
        st.dataframe(view, use_container_width=True, hide_index=True, height=height)


def show_report(relative: str) -> None:
    path = OUTPUT_ROOT / relative
    if path.exists():
        st.markdown(path.read_text(encoding="utf-8", errors="replace"))
    else:
        st.info(f"Not available: `outputs/{relative}`")


st.set_page_config(page_title="Research Lab", layout="wide")
inject_global_styles()
inject_signal_css()
sidebar_status()

page_header("Research Lab", "Model validation, backtests, signal tuning, and run reports.", "HISTORICAL TEST ONLY")
warning_banner("Research-only workspace", "This page summarizes validation artifacts. It does not create live betting output.")

with st.expander("Signal Score Audit", expanded=True):
    section_header("Signal Score Audit")
    show_table("signal_boards/signal_score_audit_summary.csv", "Audit Summary")
    show_table("signal_boards/signal_score_component_correlations.csv", "Component Correlations")
    show_table("signal_boards/signal_score_driver_audit.csv", "Driver Audit", ["overall_signal_score"])

with st.expander("Historical Backtest"):
    section_header("Historical Backtest")
    show_table("signal_boards/historical_signal_backtest_summary.csv", "Backtest Summary")
    show_table("signal_boards/historical_signal_tier_lift.csv", "Tier Lift")
    show_table("signal_boards/historical_signal_market_family_audit.csv", "Market Family Audit")

with st.expander("Weight Tuning"):
    section_header("Signal Weight Tuning")
    show_table("signal_boards/signal_weight_tuning_results.csv", "Tuning Results")
    show_table("signal_boards/signal_weight_tuning_recommendations.csv", "Tuning Recommendations")

with st.expander("Champion vs Challenger"):
    section_header("Champion vs Challenger Preview")
    show_table("signal_boards/signal_challenger_preview_summary.csv", "Preview Summary")
    show_table("signal_boards/signal_challenger_top_movers.csv", "Top Movers", ["signal_score_delta"])

with st.expander("Reports"):
    section_header("Run Reports")
    for report in [
        "run_reports/latest_receptions_pipeline_report.md",
        "run_reports/latest_receptions_safety_validation.md",
        "run_reports/latest_forward_projection_dry_run.md",
        "run_reports/latest_signal_ux_polish_validation.md",
        "run_reports/latest_dashboard_navigation_validation.md",
    ]:
        st.markdown(f"#### {Path(report).name}")
        show_report(report)
