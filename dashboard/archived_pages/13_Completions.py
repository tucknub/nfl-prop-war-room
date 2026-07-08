from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (filter_by_multiselect, filter_by_search, format_percent,
                   inject_global_styles, load_csv_safe, metric_card,
                   numeric_series, page_header, player_card,
                   presentation_table, section_header, show_missing,
                   sidebar_status, warning_banner)

BOARD = "outputs/google_sheets_completions_historical_test.csv"
LADDER = "outputs/market_edges/completions_line_ladder.csv"
ATTEMPTS = "outputs/google_sheets_pass_attempts_historical_test.csv"

st.set_page_config(page_title="Completions V1", layout="wide")
inject_global_styles()
sidebar_status()
page_header("Completions V1", "Historical-test QB completion projections and no-odds line ladder.", "HISTORICAL TEST ONLY")
warning_banner("Historical Test Only - Not Betting Ready", "Completions V1 is Research Only - No Odds. Final Readiness remains NO-GO.")
st.markdown('<div class="info-card"><strong>Formula:</strong> projected pass attempts x projected completion rate. Raw and calibrated projections remain visible.</div>', unsafe_allow_html=True)

df = load_csv_safe(BOARD)
if df.empty:
    show_missing(BOARD)
    st.stop()

view = df.copy()
filters = st.columns(3)
with filters[0]:
    view = filter_by_multiselect(view, "team", "Team")
with filters[1]:
    view = filter_by_multiselect(view, "confidence_bucket", "Confidence")
with filters[2]:
    view = filter_by_search(view, "player_name", "QB search")

values = numeric_series(view, "projected_completions_calibrated")
cards = st.columns(5)
with cards[0]: metric_card("Rows", len(view))
with cards[1]: metric_card("QBs", view["player_name"].nunique())
with cards[2]: metric_card("Teams", view["team"].nunique())
with cards[3]: metric_card("Avg Projection", f"{values.mean():.2f}" if not values.empty else "n/a")
with cards[4]: metric_card("Historical-Test Rows", int(view["usage_status"].astype(str).eq("HISTORICAL TEST ONLY").sum()), "HISTORICAL TEST ONLY")

section_header("Top QB Completion Projections")
top = view.sort_values("projected_completions_calibrated", ascending=False).head(5)
for col, (_, row) in zip(st.columns(5), top.iterrows()):
    with col:
        value = pd.to_numeric(row.get("projected_completions_calibrated"), errors="coerce")
        player_card(str(row.get("player_name", "")), str(row.get("team", "")), "QB", f"{value:.1f}", row.get("confidence_bucket", ""))

section_header("Projection Table")
show = ["overall_rank", "player_name", "team", "opponent_team", "projected_completions_calibrated", "projected_completions_raw", "projected_pass_attempts", "projected_completion_rate", "confidence_bucket", "quality_flags", "usage_status"]
st.dataframe(presentation_table(view[[c for c in show if c in view.columns]]), use_container_width=True, hide_index=True)

section_header("Passing Volume vs Efficiency", "Context only; this is not a betting classification.")
attempts = load_csv_safe(ATTEMPTS)
if attempts.empty:
    show_missing(ATTEMPTS)
else:
    attempt_col = "projected_pass_attempts_calibrated"
    joined = view.merge(attempts[[c for c in ["player_id", "player_name", "team", attempt_col] if c in attempts.columns]], on=[c for c in ["player_id", "player_name", "team"] if c in view.columns and c in attempts.columns], how="left")
    attempt_values = pd.to_numeric(joined.get(attempt_col), errors="coerce")
    rate_values = pd.to_numeric(joined.get("projected_completion_rate"), errors="coerce")
    attempt_cut = attempt_values.median(); rate_cut = rate_values.median()
    joined["volume_efficiency_profile"] = "Lower attempts / lower completion rate"
    joined.loc[(attempt_values >= attempt_cut) & (rate_values >= rate_cut), "volume_efficiency_profile"] = "High attempts / high completion rate"
    joined.loc[(attempt_values >= attempt_cut) & (rate_values < rate_cut), "volume_efficiency_profile"] = "High attempts / lower completion rate"
    joined.loc[(attempt_values < attempt_cut) & (rate_values >= rate_cut), "volume_efficiency_profile"] = "Lower attempts / efficient completions"
    context_cols = ["player_name", "team", attempt_col, "projected_completion_rate", "projected_completions_calibrated", "volume_efficiency_profile", "usage_status"]
    st.dataframe(presentation_table(joined[[c for c in context_cols if c in joined.columns]].sort_values("projected_completions_calibrated", ascending=False)), use_container_width=True, hide_index=True)

section_header("Completions Line Ladder", "Research Only - No Odds")
ladder = load_csv_safe(LADDER)
if ladder.empty:
    show_missing(LADDER)
else:
    lines = sorted(pd.to_numeric(ladder["line"], errors="coerce").dropna().unique())
    default = lines.index(22.5) if 22.5 in lines else 0
    line = st.selectbox("Completions line", lines, index=default)
    selected = ladder[pd.to_numeric(ladder["line"], errors="coerce").eq(float(line))].sort_values("model_over_probability", ascending=False).head(15)
    st.caption(f"Max over probability at {line}: {format_percent(selected['model_over_probability'].max())}")
    st.bar_chart(selected.set_index("player_name")["model_over_probability"])
    st.dataframe(presentation_table(selected), use_container_width=True, hide_index=True)
