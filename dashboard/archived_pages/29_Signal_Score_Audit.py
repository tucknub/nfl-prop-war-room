from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import build_heatmap_styler, load_signal_csv, render_signal_table
from utils import inject_global_styles, metric_card, page_header, section_header, show_table_or_missing, sidebar_status, warning_banner


SUMMARY = "outputs/signal_boards/signal_score_audit_summary.csv"
CORRELATIONS = "outputs/signal_boards/signal_score_component_correlations.csv"
DRIVERS = "outputs/signal_boards/signal_score_driver_audit.csv"
EXPLAIN = "outputs/signal_boards/signal_score_explainability.csv"
OUTCOME = "outputs/signal_boards/signal_score_outcome_audit.csv"
HISTORICAL_FAMILY = "outputs/signal_boards/historical_signal_market_family_audit.csv"


st.set_page_config(page_title="Signal Score Audit", layout="wide")
inject_global_styles()
sidebar_status()

page_header("Signal Score Audit", "Research-only audit of signal distributions, component behavior, drivers, and explanations.", "HISTORICAL TEST ONLY")
st.caption("Section: Research / Audit Lab")
warning_banner(
    "Research-only audit",
    "This page checks whether the signal system is behaving sensibly. It is not a betting board.",
)

summary = load_signal_csv(SUMMARY)
correlations = load_signal_csv(CORRELATIONS)
drivers = load_signal_csv(DRIVERS)
explain = load_signal_csv(EXPLAIN)
outcome = load_signal_csv(OUTCOME)
historical_family = load_signal_csv(HISTORICAL_FAMILY)

total_rows = int(summary["row_count"].sum()) if not summary.empty and "row_count" in summary.columns else 0
avg_score = pd.to_numeric(summary.get("average_overall_signal_score", pd.Series(dtype=float)), errors="coerce").mean() if not summary.empty else pd.NA
review_count = int(summary[[col for col in ["REVIEW_count", "BLOCKED_count", "INSUFFICIENT_DATA_count"] if col in summary.columns]].sum().sum()) if not summary.empty else 0
strong_count = int(summary[[col for col in ["ELITE_SIGNAL_count", "STRONG_SIGNAL_count", "GOOD_SIGNAL_count"] if col in summary.columns]].sum().sum()) if not summary.empty else 0
watch_count = int(summary["WATCH_count"].sum()) if not summary.empty and "WATCH_count" in summary.columns else 0
missing_rows = int(pd.to_numeric(drivers.get("top_negative_driver_1", pd.Series(dtype=str)).astype(str).str.contains("missing signal count", na=False), errors="coerce").fillna(0).sum()) if not drivers.empty else 0

cols = st.columns(5)
with cols[0]:
    metric_card("Audited Rows", total_rows, "INFO")
with cols[1]:
    metric_card("Strong/Good", strong_count, "GOOD_SIGNAL")
with cols[2]:
    metric_card("Watch", watch_count, "WATCH")
with cols[3]:
    metric_card("Review/Block", review_count, "REVIEW")
with cols[4]:
    metric_card("Average Score", f"{avg_score:.1f}" if pd.notna(avg_score) else "n/a", "INFO")

section_header("Score Distribution", "Board-level score distribution and structural flags.")
show_table_or_missing(summary, SUMMARY)

section_header("Component Correlations", "High absolute correlations can indicate possible double-counting risk.")
if correlations.empty:
    show_table_or_missing(correlations, CORRELATIONS)
else:
    view = correlations.copy()
    if "double_count_risk" in view.columns:
        view = view.sort_values(["double_count_risk", "abs_correlation"], ascending=[False, False])
    st.dataframe(build_heatmap_styler(view, ["correlation", "abs_correlation"], ["double_count_risk"]), use_container_width=True, hide_index=True)

section_header("Score Drivers", "Top positive and negative drivers by player.")
driver_columns = [
    "player_name",
    "team",
    "opponent",
    "position",
    "overall_signal_score",
    "signal_tier",
    "top_positive_driver_1",
    "top_positive_driver_2",
    "top_negative_driver_1",
    "top_negative_driver_2",
    "driver_notes",
]
render_signal_table(drivers.head(300), ["overall_signal_score"], driver_columns, "Driver Audit Table")

section_header("Explainability", "Plain-English summaries and signal-only recommended actions.")
explain_columns = [
    "player_name",
    "team",
    "opponent",
    "position",
    "market_family",
    "overall_signal_score",
    "signal_tier",
    "plain_english_summary",
    "data_limitations",
    "recommended_user_action",
]
render_signal_table(explain.head(300), ["overall_signal_score"], explain_columns, "Explainability Table")

section_header("Outcome Audit")
if not historical_family.empty:
    st.success("Historical signal backtest output is available. See the Historical Signal Backtest page for tier lift, component usefulness, and market-family audit details.")
    render_signal_table(
        historical_family,
        ["tier_lift", "score_actual_correlation"],
        [
            "market_family",
            "rows",
            "baseline_actual_average",
            "elite_or_strong_average_actual",
            "watch_or_review_average_actual",
            "tier_lift",
            "score_actual_correlation",
            "monotonicity_status",
        ],
        "Historical Backtest Summary",
    )
if outcome.empty:
    st.info("Historical outcome audit not yet available for this signal table.")
else:
    text = " ".join(outcome.fillna("").astype(str).agg(" ".join, axis=1).tolist())
    if "NEEDS HISTORICAL SIGNAL BACKTEST DATA" in text:
        st.info("Historical outcome audit not yet available for this signal table.")
    show_table_or_missing(outcome, OUTCOME)
