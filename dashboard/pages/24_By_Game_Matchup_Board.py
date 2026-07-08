from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import filter_multiselect, inject_signal_css, load_signal_csv, render_metric_chip, render_signal_legend, render_signal_table
from utils import inject_global_styles, metric_card, page_header, section_header, sidebar_status, warning_banner


PATH = "outputs/signal_boards/by_game_signal_board.csv"
SCORE_COLUMNS = [
    "overall_signal_score",
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "role_availability_score",
    "data_quality_score",
]
DISPLAY_COLUMNS = [
    "player_name",
    "position",
    "overall_signal_score",
    "signal_tier",
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "data_quality_score",
    "top_signal_reason",
    "review_reason",
]


def game_label(row: pd.Series) -> str:
    if "game_id" in row and pd.notna(row["game_id"]):
        return str(row["game_id"])
    if "game_key" in row and pd.notna(row["game_key"]):
        return str(row["game_key"])
    teams = sorted([str(row.get("team", "")), str(row.get("opponent", ""))])
    return " at ".join(teams)


def top_name(df: pd.DataFrame, mask_column: str | None = None) -> str:
    view = df.copy()
    if mask_column and mask_column in view.columns:
        view = view[view[mask_column].astype(str).str.lower().isin(["true", "1", "yes"])]
    if view.empty or "overall_signal_score" not in view.columns:
        return "n/a"
    row = view.sort_values("overall_signal_score", ascending=False).iloc[0]
    return f"{row.get('player_name', 'n/a')} ({row.get('overall_signal_score', 'n/a')})"


st.set_page_config(page_title="By-Game Matchup Board", layout="wide")
inject_global_styles()
inject_signal_css()
sidebar_status()

page_header("By-Game Matchup Board", "Game-level player signal splits from the existing by-game signal board.", "HISTORICAL TEST ONLY")
st.caption("Section: Main Signal Workflow")
warning_banner(
    "HISTORICAL TEST ONLY - NOT LIVE BETTING READY",
    "Game tables are research views only and do not create live output.",
)
st.caption("Use Player Signal Drilldown to inspect drivers and recent history for any player.")
render_signal_legend()

df = load_signal_csv(PATH)
if df.empty:
    st.warning(f"Missing or empty file: `{PATH}`")
    st.stop()

df = df.copy()
df["game_selector"] = df.apply(game_label, axis=1)
games = sorted(df["game_selector"].dropna().astype(str).unique())
selected_game = st.selectbox("Game", games)
game = df[df["game_selector"].astype(str).eq(selected_game)].copy()
chip_columns = [
    ("Total", "total_line"),
    ("Spread", "spread_line"),
    ("Favorite", "favorite_status"),
    ("Pass Env", "pass_volume_environment"),
    ("Rush Env", "rush_volume_environment"),
]
chip_row = st.columns(len(chip_columns))
for idx, (label, column) in enumerate(chip_columns):
    if column in game.columns and not game[column].dropna().empty:
        with chip_row[idx]:
            render_metric_chip(label, game[column].dropna().iloc[0], "INFO")
with st.sidebar:
    st.markdown("### Game Context Filters")
    game = filter_multiselect(game, "game_total_bucket", "Game total bucket")
    game = filter_multiselect(game, "spread_bucket", "Spread bucket")
    game = filter_multiselect(game, "pass_volume_environment", "Pass volume environment")
    game = filter_multiselect(game, "rush_volume_environment", "Rush volume environment")

review_count = 0
if "signal_tier" in game.columns:
    review_count = int(game["signal_tier"].astype(str).isin(["REVIEW", "BLOCKED", "INSUFFICIENT_DATA"]).sum())
missing_total = int(pd.to_numeric(game.get("missing_signal_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum())
completeness = "NEEDS SOURCE" if missing_total else "COMPLETE"

cols = st.columns(6)
with cols[0]:
    metric_card("Top Overall", top_name(game), "INFO")
with cols[1]:
    metric_card("Top Receiving", top_name(game, "receiving_market_available"), "INFO")
with cols[2]:
    metric_card("Top Rushing", top_name(game, "rushing_market_available"), "INFO")
with cols[3]:
    metric_card("Top Passing", top_name(game, "passing_market_available"), "INFO")
with cols[4]:
    metric_card("Review/Block Rows", review_count, "REVIEW" if review_count else "PASS")
with cols[5]:
    metric_card("Data Completeness", completeness, completeness)

teams = sorted(game["team"].dropna().astype(str).unique()) if "team" in game.columns else []
left, right = st.columns(2)
for idx, team in enumerate(teams[:2]):
    target_column = left if idx == 0 else right
    with target_column:
        render_signal_table(
            game[game["team"].astype(str).eq(team)].sort_values("overall_signal_score", ascending=False),
            SCORE_COLUMNS,
            DISPLAY_COLUMNS,
            f"{team} Players",
        )

section_header("Top Signals In This Game")
st.caption("Defense and game-context signals are reliability-adjusted and should not be treated as certain.")
render_signal_table(
    game.sort_values("overall_signal_score", ascending=False).head(25),
    SCORE_COLUMNS,
    ["team", *DISPLAY_COLUMNS],
    "Top Game Signals",
)
