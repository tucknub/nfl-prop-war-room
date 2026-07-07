from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import build_heatmap_styler, load_signal_csv, render_signal_table
from utils import inject_global_styles, metric_card, page_header, section_header, show_table_or_missing, sidebar_status, warning_banner


ROWS = "outputs/signal_boards/historical_signal_backtest_rows.csv"
SUMMARY = "outputs/signal_boards/historical_signal_backtest_summary.csv"
TIERS = "outputs/signal_boards/historical_signal_tier_lift.csv"
COMPONENTS = "outputs/signal_boards/historical_signal_component_audit.csv"
FAMILY = "outputs/signal_boards/historical_signal_market_family_audit.csv"
REPORT = "outputs/run_reports/latest_historical_signal_backtest_report.md"


st.set_page_config(page_title="Historical Signal Backtest", layout="wide")
inject_global_styles()
sidebar_status()

page_header("Historical Signal Backtest", "Research-only audit of whether historical signal scores align with past player production.", "HISTORICAL TEST ONLY")
warning_banner(
    "Research-only historical audit",
    "This checks whether signal scores align with actual past player production. It is not a betting board.",
)

rows = load_signal_csv(ROWS)
summary = load_signal_csv(SUMMARY)
tiers = load_signal_csv(TIERS)
components = load_signal_csv(COMPONENTS)
family = load_signal_csv(FAMILY)

seasons = sorted(pd.to_numeric(rows.get("season", pd.Series(dtype=float)), errors="coerce").dropna().astype(int).unique().tolist()) if not rows.empty else []
families = sorted(rows.get("market_family", pd.Series(dtype=str)).dropna().astype(str).unique().tolist()) if not rows.empty else []
strongest = "n/a"
weakest = "n/a"
monotonicity = "n/a"
if not family.empty:
    lift = pd.to_numeric(family.get("tier_lift", pd.Series(dtype=float)), errors="coerce")
    if lift.notna().any():
        strongest = str(family.loc[lift.idxmax(), "market_family"])
        weakest = str(family.loc[lift.idxmin(), "market_family"])
    monotonicity = "PASS" if family.get("monotonicity_status", pd.Series(dtype=str)).astype(str).eq("PASS").all() else "CHECK"

cols = st.columns(6)
with cols[0]:
    metric_card("Historical Rows", len(rows), "PASS" if len(rows) else "MISSING")
with cols[1]:
    metric_card("Seasons", ", ".join(map(str, seasons)) if seasons else "n/a", "INFO")
with cols[2]:
    metric_card("Families", len(families), "INFO", ", ".join(families))
with cols[3]:
    metric_card("Strongest Family", strongest, "INFO")
with cols[4]:
    metric_card("Weakest/Noisiest", weakest, "CHECK")
with cols[5]:
    metric_card("Monotonicity", monotonicity, monotonicity)

section_header("Tier Lift", "Checks whether stronger tiers produce better actual outcomes.")
render_signal_table(
    tiers,
    ["average_signal_score", "average_actual_primary_value", "lift_vs_baseline", "top_quartile_actual_rate"],
    [
        "market_family",
        "signal_tier",
        "row_count",
        "average_signal_score",
        "average_actual_primary_value",
        "median_actual_primary_value",
        "baseline_average_actual",
        "lift_vs_baseline",
        "top_quartile_actual_rate",
        "bottom_quartile_actual_rate",
        "notes",
    ],
    "Tier Lift Table",
)

section_header("Score Buckets", "Monotonicity check across score buckets.")
show_table_or_missing(build_heatmap_styler(summary, ["average_actual_primary_value", "lift_vs_baseline"], ["bucket_flags"]), SUMMARY)

section_header("Component Usefulness", "Component correlation and top/bottom quartile lift versus actual outcomes.")
render_signal_table(
    components,
    ["correlation_with_actual", "spearman_correlation_with_actual", "top_quartile_lift", "bottom_quartile_lift"],
    [
        "market_family",
        "component_name",
        "correlation_with_actual",
        "spearman_correlation_with_actual",
        "top_quartile_lift",
        "bottom_quartile_lift",
        "row_count",
        "usefulness_flag",
        "notes",
    ],
    "Component Usefulness Table",
)

section_header("Market-Family Audit", "Where the signal board appears strongest historically.")
render_signal_table(
    family,
    ["baseline_actual_average", "elite_or_strong_average_actual", "watch_or_review_average_actual", "tier_lift", "score_actual_correlation"],
    [
        "market_family",
        "rows",
        "baseline_actual_average",
        "elite_or_strong_average_actual",
        "watch_or_review_average_actual",
        "tier_lift",
        "score_actual_correlation",
        "monotonicity_status",
        "data_quality_notes",
    ],
    "Market Family Audit Table",
)

section_header("Rows Preview")
row_columns = [
    "season",
    "week",
    "player_name",
    "team",
    "opponent",
    "position",
    "market_family",
    "overall_signal_score",
    "signal_tier",
    "actual_primary_metric",
    "actual_primary_value",
    "backtest_usage_status",
    "data_limitations",
]
render_signal_table(rows.head(300), ["overall_signal_score", "actual_primary_value"], row_columns, "Historical Rows")
