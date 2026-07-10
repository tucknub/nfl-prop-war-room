from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import (
    build_heatmap_styler,
    inject_signal_css,
    load_signal_csv,
    render_action_badge,
    render_metric_chip,
    render_reliability_badge,
    render_signal_badge,
    render_signal_table,
    summarize_reason,
    player_context_text,
    player_selection_token,
)
from utils import inject_global_styles, metric_card, page_header, section_header, sidebar_status


PROFILES = "outputs/signal_boards/player_signal_profiles.csv"
MARKET = "outputs/signal_boards/player_signal_market_summary.csv"
CONTEXT = "outputs/signal_boards/player_signal_context_summary.csv"
HISTORY = "outputs/signal_boards/player_signal_recent_history.csv"
CHALLENGER = "outputs/signal_boards/signal_challenger_preview_rows.csv"
MATCHUPS = "outputs/signal_boards/by_game_signal_board.csv"


def clean_value(value: object, fallback: str = "—") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text and text.lower() != "nan" else fallback


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


def driver_list(row: pd.Series, columns: list[str]) -> str:
    items = [summarize_reason(row.get(col), 150) for col in columns]
    items = [item for item in items if item]
    if not items:
        items = ["No sourced driver available."]
    return "".join(f"<li>{item}</li>" for item in items)


st.set_page_config(page_title="Player Details | PropWar NFL", layout="wide")
inject_global_styles()
inject_signal_css()
sidebar_status()

page_header("Player Details", "One-player view of strengths, risks, context, and recent history.")

profiles = load_signal_csv(PROFILES)
matchups = load_signal_csv(MATCHUPS)
market = load_signal_csv(MARKET)
context = load_signal_csv(CONTEXT)
history = load_signal_csv(HISTORY)
challenger = load_signal_csv(CHALLENGER)

if profiles.empty:
    st.warning(f"Missing or empty file: `{PROFILES}`")
    st.stop()


def add_matchup_context(profile_frame: pd.DataFrame, matchup_frame: pd.DataFrame) -> pd.DataFrame:
    """Fill profile-only rows from the display-ready by-game board."""
    if profile_frame.empty or matchup_frame.empty or "opponent" not in matchup_frame.columns:
        return profile_frame
    keys = [column for column in ["player_name", "team"] if column in profile_frame.columns and column in matchup_frame.columns]
    if len(keys) < 2:
        return profile_frame
    reference = matchup_frame[keys + ["opponent"]].copy()
    reference["opponent"] = reference["opponent"].fillna("").astype(str).str.strip()
    reference = reference[reference["opponent"].ne("")].drop_duplicates(keys)
    if reference.empty:
        return profile_frame
    enriched = profile_frame.merge(reference, on=keys, how="left", suffixes=("", "_derived"))
    if "opponent_derived" in enriched.columns:
        current = enriched["opponent"].fillna("").astype(str).str.strip() if "opponent" in enriched.columns else pd.Series("", index=enriched.index)
        enriched["opponent"] = current.where(current.ne(""), enriched["opponent_derived"])
        enriched = enriched.drop(columns=["opponent_derived"])
    return enriched


profiles = add_matchup_context(profiles, matchups)

view = profiles.copy()
with st.sidebar:
    st.markdown("### Player Filters")
    query = st.text_input("Search player name", key="drilldown_search").strip().lower()
    if query and "player_name" in view.columns:
        view = view[view["player_name"].astype(str).str.lower().str.contains(query, na=False)]
    for col, label in [("team", "Team"), ("position", "Position"), ("signal_tier", "Strength")]:
        if col in view.columns:
            values = sorted(value for value in view[col].dropna().astype(str).unique() if value)
            selected_values = st.multiselect(label, values, key=f"drilldown_{col}")
            if selected_values:
                view = view[view[col].astype(str).isin(selected_values)]

if view.empty:
    st.info("No players match the current filters.")
    st.stop()

view["_sort_score"] = pd.to_numeric(view.get("best_signal_score", view.get("overall_signal_score")), errors="coerce")
view = view.sort_values("_sort_score", ascending=False)
labels = {
    player_selection_token(row): f"{clean_value(row.get('player_name'))} - {clean_value(row.get('team'), '')} - {clean_value(row.get('position'), '')}"
    for _, row in view.iterrows()
}
requested_key = st.session_state.pop("player_detail_key", None)
default_index = list(labels.keys()).index(requested_key) if requested_key in labels else 0
selected_key = st.selectbox(
    "Player",
    list(labels.keys()),
    index=default_index,
    format_func=lambda key: labels.get(key, key),
    key="drilldown_player",
)
selected = view.loc[view.apply(player_selection_token, axis=1).eq(selected_key)].iloc[0]

st.markdown(
    f"""
    <div class="signal-header">
      <h2>{clean_value(selected.get('player_name'))}</h2>
      <p>{player_context_text(selected)}</p>
      <div class="signal-chip-row">
        {render_signal_badge(selected.get('overall_signal_score'))}
        {render_signal_badge(selected.get('signal_tier'))}
        {render_action_badge(selected.get('recommended_user_action'))}
        {render_reliability_badge(selected.get('readiness_status'))}
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

cols = st.columns(4)
with cols[0]:
    metric_card("Board Score", clean_value(selected.get("overall_signal_score")), clean_value(selected.get("signal_tier")))
with cols[1]:
    metric_card("Strength", clean_value(selected.get("signal_tier")), clean_value(selected.get("signal_tier")))
with cols[2]:
    metric_card("Action", clean_value(selected.get("recommended_user_action")), clean_value(selected.get("readiness_status")))
if clean_value(selected.get("opponent"), ""):
    with cols[3]:
        metric_card("Opponent", clean_value(selected.get("opponent")), "INFO")

section_header("Why This Player?")
driver_cols = st.columns(2)
with driver_cols[0]:
    st.markdown(
        f"""
        <div class="plain-signal-list">
        <h4>Strengths</h4>
        <ul>{driver_list(selected, ['top_positive_driver_1', 'top_positive_driver_2', 'top_positive_driver_3'])}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
with driver_cols[1]:
    st.markdown(
        f"""
        <div class="plain-signal-list">
        <h4>Risks</h4>
        <ul>{driver_list(selected, ['top_negative_driver_1', 'top_negative_driver_2', 'top_negative_driver_3', 'review_reason', 'blocked_reason'])}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

player_context = matching_rows(context, selected)
section_header("Context Summary")
if player_context.empty:
    st.info("Context chips are not available for this player.")
else:
    first_context = player_context.iloc[0]
    chip_columns = [
        ("Total", "total_line"),
        ("Spread", "spread_line"),
        ("Favorite", "favorite_status"),
        ("Pass Env", "pass_volume_environment"),
        ("Rush Env", "rush_volume_environment"),
        ("Defense Fit", "defense_fit_reliability"),
        ("Recent Form", "recent_form_reliability"),
    ]
    chip_wrap = st.columns(4)
    for idx, (label, column) in enumerate(chip_columns):
        if column in player_context.columns:
            with chip_wrap[idx % len(chip_wrap)]:
                render_metric_chip(label, clean_value(first_context.get(column)), first_context.get(column))

player_history = matching_rows(history, selected)
section_header("Recent History", "Prior games only. Target week and future rows are excluded.")
if player_history.empty:
    st.info("Recent history is not available for this player.")
else:
    history_cols = [
        "season",
        "week",
        "team",
        "opponent",
        "targets",
        "receptions",
        "receiving_yards",
        "carries",
        "rushing_yards",
        "pass_attempts",
        "completions",
        "passing_yards",
    ]
    hist_view = player_history[[col for col in history_cols if col in player_history.columns]].sort_values(["season", "week"], ascending=False).head(8)
    st.dataframe(
        build_heatmap_styler(hist_view, ["targets", "receptions", "receiving_yards", "carries", "rushing_yards", "pass_attempts", "completions", "passing_yards"]),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Market Family Detail"):
    player_market = matching_rows(market, selected)
    render_signal_table(
        player_market,
        ["overall_signal_score", "projection_score", "recent_form_score", "opponent_fit_score"],
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
        ],
        "Market Family Summary",
    )

with st.expander("Comparison"):
    player_challenger = matching_rows(challenger, selected)
    render_signal_table(
        player_challenger,
        ["current_overall_signal_score", "challenger_overall_signal_score", "signal_score_delta"],
        [
            "market_family",
            "current_overall_signal_score",
            "challenger_overall_signal_score",
            "signal_score_delta",
            "current_signal_tier",
            "challenger_signal_tier",
            "tier_change",
            "preview_usage_status",
            "preview_notes",
        ],
        "Comparison",
        "Comparison rows are shown for context only.",
    )
