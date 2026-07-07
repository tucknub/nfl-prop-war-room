from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import build_heatmap_styler, load_signal_csv, render_signal_table
from utils import inject_global_styles, load_markdown_safe, metric_card, page_header, section_header, show_table_or_missing, sidebar_status, warning_banner


RESULTS = "outputs/signal_boards/signal_weight_tuning_results.csv"
BY_FAMILY = "outputs/signal_boards/signal_weight_tuning_by_family.csv"
TIER_LIFT = "outputs/signal_boards/signal_weight_tuning_tier_lift.csv"
RECOMMENDATIONS = "outputs/signal_boards/signal_weight_tuning_recommendations.csv"
RECOMMENDED_YAML = "outputs/signal_boards/recommended_signal_weight_profile.yaml"


st.set_page_config(page_title="Signal Weight Tuning Lab", layout="wide")
inject_global_styles()
sidebar_status()

page_header("Signal Weight Tuning Lab", "Research-only comparison of challenger signal formulas against historical outcomes.", "HISTORICAL TEST ONLY")
warning_banner(
    "Research-only",
    "This page compares challenger signal formulas against historical outcomes. It does not create live betting output.",
)

results = load_signal_csv(RESULTS)
by_family = load_signal_csv(BY_FAMILY)
tier_lift = load_signal_csv(TIER_LIFT)
recommendations = load_signal_csv(RECOMMENDATIONS)
yaml_text = load_markdown_safe(RECOMMENDED_YAML)

best = by_family[by_family.get("recommendation", pd.Series(dtype=str)).astype(str).eq("TEST_CHALLENGER")] if not by_family.empty else pd.DataFrame()
best_profiles = ", ".join(sorted(best["profile_name"].dropna().astype(str).unique())) if not best.empty else "current_v1"
profile_count = int(results["profile_name"].nunique()) if not results.empty and "profile_name" in results.columns else 0
family_count = int(results["market_family"].nunique()) if not results.empty and "market_family" in results.columns else 0
test_count = int(by_family.get("recommendation", pd.Series(dtype=str)).astype(str).eq("TEST_CHALLENGER").sum()) if not by_family.empty else 0
keep_count = int(by_family.get("recommendation", pd.Series(dtype=str)).astype(str).eq("KEEP_CURRENT").sum()) if not by_family.empty else 0

cols = st.columns(5)
with cols[0]:
    metric_card("Profiles Tested", profile_count, "INFO")
with cols[1]:
    metric_card("Families", family_count, "INFO")
with cols[2]:
    metric_card("Test Challenger Rows", test_count, "CHECK" if test_count else "PASS")
with cols[3]:
    metric_card("Keep Current Rows", keep_count, "PASS")
with cols[4]:
    metric_card("Best Candidate Set", best_profiles, "INFO")

section_header("Champion vs Challenger", "Current production profile remains champion unless explicitly promoted later.")
render_signal_table(
    by_family,
    ["delta_tier_lift", "delta_score_correlation", "delta_top_vs_bottom_lift"],
    [
        "profile_name",
        "market_family",
        "delta_tier_lift",
        "delta_score_correlation",
        "delta_top_vs_bottom_lift",
        "delta_monotonicity",
        "recommendation",
        "notes",
    ],
    "Champion Comparison Table",
)

section_header("Market-Family Comparison")
render_signal_table(
    results,
    ["score_actual_correlation", "spearman_score_actual_correlation", "tier_lift", "top_vs_bottom_lift"],
    [
        "profile_name",
        "market_family",
        "row_count",
        "score_actual_correlation",
        "spearman_score_actual_correlation",
        "elite_or_strong_count",
        "tier_lift",
        "top_vs_bottom_lift",
        "monotonicity_status",
        "overfit_risk_flag",
        "dominant_component",
        "dominant_component_weight",
    ],
    "Profile Results",
)

section_header("Tier Lift Comparison")
render_signal_table(
    tier_lift,
    ["average_challenger_score", "average_actual_primary_value", "lift_vs_baseline"],
    [
        "profile_name",
        "market_family",
        "challenger_signal_tier",
        "row_count",
        "average_challenger_score",
        "average_actual_primary_value",
        "baseline_average_actual",
        "lift_vs_baseline",
    ],
    "Tier Lift By Profile",
)

section_header("Component Recommendations", "Research guidance for later score review.")
component_rows = recommendations[recommendations.get("recommendation_scope", pd.Series(dtype=str)).astype(str).eq("component")] if not recommendations.empty else recommendations
render_signal_table(
    component_rows,
    ["correlation_with_actual", "current_weight"],
    [
        "market_family",
        "component_name",
        "current_weight",
        "historical_usefulness_flag",
        "correlation_with_actual",
        "double_count_risk",
        "recommendation",
        "notes",
    ],
    "Component Recommendation Table",
)

section_header("Recommended Challenger YAML", "Not applied to production.")
if yaml_text:
    st.code(yaml_text, language="yaml")
else:
    st.warning(f"Missing file: `{RECOMMENDED_YAML}`")

section_header("Notes")
st.markdown(
    """
    <div class="info-card">
    Historical only. No pricing or line-movement logic. Challenger profiles are not automatically promoted.
    Use this lab to guide future score-weight review after more historical and live-context data is available.
    </div>
    """,
    unsafe_allow_html=True,
)
