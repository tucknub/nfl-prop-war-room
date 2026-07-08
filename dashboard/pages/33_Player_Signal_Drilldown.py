from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import build_heatmap_styler, load_signal_csv, render_signal_table
from utils import inject_global_styles, metric_card, page_header, section_header, sidebar_status, warning_banner


PROFILES = "outputs/signal_boards/player_signal_profiles.csv"
MARKET = "outputs/signal_boards/player_signal_market_summary.csv"
CONTEXT = "outputs/signal_boards/player_signal_context_summary.csv"
HISTORY = "outputs/signal_boards/player_signal_recent_history.csv"
CHALLENGER = "outputs/signal_boards/signal_challenger_preview_rows.csv"


def clean_value(value: object, fallback: str = "NOT_AVAILABLE") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text and text.lower() != "nan" else fallback


def player_key(row: pd.Series) -> str:
    player_id = clean_value(row.get("player_id"), "")
    if player_id:
        return f"id::{player_id}"
    return f"name::{clean_value(row.get('player_name'), '')}|{clean_value(row.get('team'), '')}|{clean_value(row.get('position'), '')}"


def matching_rows(df: pd.DataFrame, selected: pd.Series) -> pd.DataFrame:
    if df.empty:
        return df
    player_id = clean_value(selected.get("player_id"), "")
    if player_id and "player_id" in df.columns:
        rows = df[df["player_id"].fillna("").astype(str).eq(player_id)]
        if not rows.empty:
            return rows
    mask = pd.Series(True, index=df.index)
    for col in ["player_name", "team"]:
        if col in df.columns:
            mask &= df[col].fillna("").astype(str).eq(clean_value(selected.get(col), ""))
    return df[mask]


def text_block(title: str, value: object) -> None:
    st.markdown(f"**{title}**")
    st.write(clean_value(value, ""))


st.set_page_config(page_title="Player Signal Drilldown", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "Player Signal Drilldown",
    "Single-player signal context, drivers, recent history, and challenger preview.",
    "HISTORICAL TEST ONLY",
)
st.caption("Section: Main Signal Workflow")
warning_banner(
    "Research-only player context",
    "No odds, no CLV, no betting output.",
)

profiles = load_signal_csv(PROFILES)
market = load_signal_csv(MARKET)
context = load_signal_csv(CONTEXT)
history = load_signal_csv(HISTORY)
challenger = load_signal_csv(CHALLENGER)

if profiles.empty:
    st.warning(f"Missing or empty file: `{PROFILES}`")
    st.stop()

view = profiles.copy()
with st.sidebar:
    st.markdown("### Player Filters")
    query = st.text_input("Search player name").strip().lower()
    if query and "player_name" in view.columns:
        view = view[view["player_name"].astype(str).str.lower().str.contains(query, na=False)]
    for col, label in [("team", "Team"), ("position", "Position"), ("signal_tier", "Signal tier")]:
        if col in view.columns:
            values = sorted(value for value in view[col].dropna().astype(str).unique() if value)
            selected_values = st.multiselect(label, values)
            if selected_values:
                view = view[view[col].astype(str).isin(selected_values)]

if view.empty:
    st.info("No players match the current filters.")
    st.stop()

view["_sort_score"] = pd.to_numeric(view.get("best_signal_score", view.get("overall_signal_score")), errors="coerce")
view = view.sort_values("_sort_score", ascending=False)
labels = {
    player_key(row): f"{clean_value(row.get('player_name'))} - {clean_value(row.get('team'), '')} - {clean_value(row.get('position'), '')} ({clean_value(row.get('signal_tier'), '')})"
    for _, row in view.iterrows()
}
selected_key = st.selectbox("Player", list(labels.keys()), format_func=lambda key: labels.get(key, key))
selected = view.loc[view.apply(player_key, axis=1).eq(selected_key)].iloc[0]

cols = st.columns(6)
with cols[0]:
    metric_card("Overall Signal", clean_value(selected.get("overall_signal_score")), clean_value(selected.get("signal_tier")))
with cols[1]:
    metric_card("Signal Tier", clean_value(selected.get("signal_tier")), clean_value(selected.get("signal_tier")))
with cols[2]:
    metric_card("Action", clean_value(selected.get("recommended_user_action")), clean_value(selected.get("readiness_status")))
with cols[3]:
    metric_card("Player", clean_value(selected.get("player_name")), f"{clean_value(selected.get('team'), '')} / {clean_value(selected.get('position'), '')}")
with cols[4]:
    metric_card("Opponent", clean_value(selected.get("opponent")), "INFO")
with cols[5]:
    metric_card("Readiness", clean_value(selected.get("readiness_status")), clean_value(selected.get("final_readiness")))

count_cols = st.columns(4)
with count_cols[0]:
    metric_card("Green", clean_value(selected.get("green_signal_count"), "0"), "PASS")
with count_cols[1]:
    metric_card("Yellow", clean_value(selected.get("yellow_signal_count"), "0"), "WATCH")
with count_cols[2]:
    metric_card("Red", clean_value(selected.get("red_flag_count"), "0"), "REVIEW")
with count_cols[3]:
    metric_card("Missing", clean_value(selected.get("missing_signal_count"), "0"), "NEEDS SOURCE")

section_header("Why This Player?")
text_block("Signal explanation", selected.get("signal_explanation"))
driver_cols = st.columns(2)
with driver_cols[0]:
    text_block("Top positive drivers", "; ".join(clean_value(selected.get(col), "") for col in ["top_positive_driver_1", "top_positive_driver_2", "top_positive_driver_3"] if clean_value(selected.get(col), "")))
with driver_cols[1]:
    text_block("Top negative drivers", "; ".join(clean_value(selected.get(col), "") for col in ["top_negative_driver_1", "top_negative_driver_2", "top_negative_driver_3"] if clean_value(selected.get(col), "")))
text_block("Review reason", selected.get("review_reason"))
text_block("Blocked reason", selected.get("blocked_reason"))
text_block("Data limitations", selected.get("data_limitations", "NOT_AVAILABLE"))

player_market = matching_rows(market, selected)
render_signal_table(
    player_market,
    [
        "overall_signal_score",
        "projection_score",
        "usage_foundation_score",
        "recent_form_score",
        "opponent_fit_score",
        "game_script_score",
        "role_availability_score",
        "volatility_score",
        "data_quality_score",
    ],
    [
        "market_family",
        "receptions_projection",
        "receiving_yards_projection",
        "rushing_yards_projection",
        "carries_projection",
        "pass_attempts_projection",
        "completions_projection",
        "passing_yards_projection",
        "overall_signal_score",
        "signal_tier",
        "recommended_user_action",
        "projection_score",
        "usage_foundation_score",
        "recent_form_score",
        "opponent_fit_score",
        "game_script_score",
        "role_availability_score",
        "volatility_score",
        "data_quality_score",
        "signal_explanation",
        "top_positive_driver_1",
        "top_negative_driver_1",
    ],
    "Market Family Summary",
    "Shows which current player-market family is strongest.",
)

player_context = matching_rows(context, selected)
render_signal_table(
    player_context,
    ["spread_line", "total_line", "team_implied_total", "opp_receiving_fit_score", "opp_rushing_fit_score", "opp_passing_fit_score", "context_data_quality"],
    [
        "team",
        "opponent",
        "spread_line",
        "total_line",
        "team_implied_total",
        "favorite_status",
        "spread_bucket",
        "game_total_bucket",
        "pass_volume_environment",
        "rush_volume_environment",
        "opp_receiving_fit_score",
        "opp_rushing_fit_score",
        "opp_passing_fit_score",
        "defense_fit_reliability",
        "defense_fit_sample_games",
        "recent_form_reliability",
        "game_environment_reliability",
        "context_data_quality",
        "context_notes",
    ],
    "Context Summary",
    "Game environment, defense fit, and reliability fields are shown only where sourced.",
)

player_history = matching_rows(history, selected)
section_header("Recent History", "Prior games only. Target week and future rows are excluded from this drilldown table.")
if player_history.empty:
    st.info("Recent history is NOT_AVAILABLE for this player or source file.")
else:
    history_cols = [
        "season",
        "week",
        "team",
        "opponent",
        "position",
        "targets",
        "receptions",
        "receiving_yards",
        "carries",
        "rushing_yards",
        "pass_attempts",
        "completions",
        "passing_yards",
        "touchdowns_if_available",
        "history_notes",
    ]
    hist_view = player_history[[col for col in history_cols if col in player_history.columns]].sort_values(["season", "week"], ascending=False).head(12)
    st.dataframe(
        build_heatmap_styler(hist_view, ["targets", "receptions", "receiving_yards", "carries", "rushing_yards", "pass_attempts", "completions", "passing_yards", "touchdowns_if_available"]),
        use_container_width=True,
        hide_index=True,
    )

player_challenger = matching_rows(challenger, selected)
render_signal_table(
    player_challenger,
    ["current_overall_signal_score", "challenger_overall_signal_score", "signal_score_delta"],
    [
        "market_family",
        "production_champion_profile",
        "challenger_profile_name",
        "current_overall_signal_score",
        "challenger_overall_signal_score",
        "signal_score_delta",
        "current_signal_tier",
        "challenger_signal_tier",
        "tier_change",
        "current_recommended_user_action",
        "challenger_recommended_user_action",
        "action_change",
        "preview_usage_status",
        "preview_notes",
    ],
    "Champion vs Challenger",
    "Research-only challenger rows are not applied to production signal boards.",
)

section_header("Footer Note")
st.markdown(
    """
    <div class="info-card">
    This page explains signal strength. It does not determine whether a sportsbook price is good.
    </div>
    """,
    unsafe_allow_html=True,
)
