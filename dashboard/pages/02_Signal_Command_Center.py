from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import (
    build_signal_heatmap,
    command_center_card,
    inject_signal_css,
    load_signal_csv,
    quick_link_card,
    render_player_signal_card,
    render_signal_legend,
    section_label,
)
from utils import inject_global_styles, page_header, section_header, sidebar_status, warning_banner


SLATE = "outputs/signal_boards/slate_signal_board.csv"
BY_GAME = "outputs/signal_boards/by_game_signal_board.csv"
RECEIVING = "outputs/signal_boards/receiving_signal_board.csv"
RUSHING = "outputs/signal_boards/rushing_signal_board.csv"
PASSING = "outputs/signal_boards/passing_signal_board.csv"
BLOCKED = "outputs/signal_boards/blocked_review_board.csv"
PROFILES = "outputs/signal_boards/player_signal_profiles.csv"
CONTEXT = "outputs/signal_boards/player_signal_context_summary.csv"


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame.get(column, pd.Series(dtype=float)), errors="coerce")


def top_player(frame: pd.DataFrame, column: str, label: str) -> tuple[str, object]:
    if frame.empty or column not in frame.columns:
        return "NOT_AVAILABLE", "NEEDS SOURCE"
    values = numeric(frame, column)
    if not values.notna().any():
        return "NOT_AVAILABLE", "NEEDS SOURCE"
    row = frame.loc[values.idxmax()]
    return f"{row.get('player_name', 'n/a')} ({values.max():.1f})", label


def top_row(frame: pd.DataFrame, column: str = "overall_signal_score") -> pd.Series | None:
    if frame.empty or column not in frame.columns:
        return None
    values = numeric(frame, column)
    if not values.notna().any():
        return None
    return frame.loc[values.idxmax()]


def game_key(row: pd.Series) -> str:
    if pd.notna(row.get("game_id")):
        return str(row.get("game_id"))
    team = str(row.get("team", "") or "")
    opponent = str(row.get("opponent", "") or "")
    if opponent:
        return f"{team} / {opponent}"
    return team or "UNKNOWN"


def by_game_mini(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    data = frame.copy()
    data["_game"] = data.apply(game_key, axis=1)
    rows = []
    for game, group in data.groupby("_game"):
        scores = numeric(group, "overall_signal_score")
        if scores.notna().any():
            top = group.loc[scores.idxmax()]
            top_score = scores.max()
        else:
            top = group.iloc[0]
            top_score = pd.NA
        tiers = group.get("signal_tier", pd.Series(dtype=str)).astype(str)
        rows.append(
            {
                "game/team/opponent": game,
                "top_player": top.get("player_name", "n/a"),
                "top_signal_score": top_score,
                "top_signal_tier": top.get("signal_tier", "n/a"),
                "review_count": int(tiers.isin(["REVIEW", "INSUFFICIENT_DATA", "WATCH"]).sum()),
                "blocked_count": int(tiers.eq("BLOCKED").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values("top_signal_score", ascending=False, na_position="last")


st.set_page_config(page_title="NFL Signal Command Center", layout="wide")
inject_global_styles()
inject_signal_css()
sidebar_status()

st.markdown(
    """
    <div class="signal-header">
      <h2>NFL Signal Command Center</h2>
      <p>Color-coded player and matchup signals. No odds. No CLV. No betting output.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
section_label("Main Signal Workflow")
warning_banner("Research-only signal board", "Final readiness remains NO-GO.")
render_signal_legend()

slate = load_signal_csv(SLATE)
by_game = load_signal_csv(BY_GAME)
receiving = load_signal_csv(RECEIVING)
rushing = load_signal_csv(RUSHING)
passing = load_signal_csv(PASSING)
blocked = load_signal_csv(BLOCKED)
profiles = load_signal_csv(PROFILES)
context = load_signal_csv(CONTEXT)

if slate.empty:
    st.warning(f"Missing or empty file: `{SLATE}`")
    st.stop()

tiers = slate.get("signal_tier", pd.Series(dtype=str)).astype(str)
kpi_cols = st.columns(7)
with kpi_cols[0]:
    command_center_card("Total Signal Rows", len(slate), "INFO")
with kpi_cols[1]:
    command_center_card("Elite / Strong", int(tiers.isin(["ELITE_SIGNAL", "STRONG_SIGNAL"]).sum()), "PASS")
with kpi_cols[2]:
    command_center_card("Good / Watch", int(tiers.isin(["GOOD_SIGNAL", "WATCH"]).sum()), "WATCH")
with kpi_cols[3]:
    command_center_card("Review / Blocked", len(blocked) if not blocked.empty else int(tiers.isin(["REVIEW", "BLOCKED", "INSUFFICIENT_DATA"]).sum()), "REVIEW")
with kpi_cols[4]:
    command_center_card("Receiving Rows", len(receiving), "PASS")
with kpi_cols[5]:
    command_center_card("Rushing Rows", len(rushing), "PASS")
with kpi_cols[6]:
    command_center_card("Passing Rows", len(passing), "PASS")

section_header("Top Player Cards", "The fastest scan of the slate.")
card_specs = [
    ("Best Overall Signal", slate, "overall_signal_score"),
    ("Best Receiving Signal", receiving, "overall_signal_score"),
    ("Best Rushing Signal", rushing, "overall_signal_score"),
    ("Best Passing Signal", passing, "overall_signal_score"),
    ("Most Review Risk", blocked if not blocked.empty else slate, "missing_signal_count"),
]
card_cols = st.columns(5)
for idx, (_, frame, column) in enumerate(card_specs):
    row = top_row(frame, column)
    if row is not None:
        with card_cols[idx % len(card_cols)]:
            render_player_signal_card(row)

section_header("Top 10 Overall Signals", "Sorted from the existing slate signal board.")
top_cols = [
    "player_name",
    "team",
    "opponent",
    "position",
    "overall_signal_score",
    "signal_tier",
    "recommended_user_action",
    "top_signal_reason",
    "review_reason",
]
top = slate.sort_values("overall_signal_score", ascending=False).head(10)
st.dataframe(
    build_signal_heatmap(top[[col for col in top_cols if col in top.columns]], ["overall_signal_score"], ["signal_tier", "recommended_user_action"]),
    use_container_width=True,
    hide_index=True,
    height=420,
)

section_header("Best By Category")
best_specs = [
    ("Best Receiving Signal", receiving, "overall_signal_score", "PASS"),
    ("Best Rushing Signal", rushing, "overall_signal_score", "PASS"),
    ("Best Passing Signal", passing, "overall_signal_score", "PASS"),
    ("Highest Recent Form", slate, "recent_form_score", "PASS"),
    ("Best Game Environment", slate, "game_script_score", "PASS"),
    ("Best Defense Fit", slate, "opponent_fit_score", "PASS"),
    ("Most Review Risk", blocked if not blocked.empty else slate, "missing_signal_count", "REVIEW"),
]
best_cols = st.columns(4)
for idx, (title, frame, column, status) in enumerate(best_specs):
    if frame.empty or column not in frame.columns:
        continue
    value, card_status = top_player(frame, column, status)
    with best_cols[idx % len(best_cols)]:
        command_center_card(title, value, card_status, column)

section_header("By-Game Mini Board", "Top players and review counts by game/team/opponent.")
mini = by_game_mini(by_game if not by_game.empty else slate)
if mini.empty:
    st.info("By-game signal rows are not available.")
else:
    st.dataframe(
        build_signal_heatmap(mini.head(40), ["top_signal_score"], ["top_signal_tier"]),
        use_container_width=True,
        hide_index=True,
        height=420,
    )

section_header("Quick Start")
st.markdown(
    """
    <div class="info-card">
    1. Start with Top Overall Signals.<br>
    2. Use By-Game Matchup Board to compare both teams.<br>
    3. Open Receiving/Rushing/Passing boards for full tables.<br>
    4. Use Player Signal Drilldown for the why.<br>
    5. Check Blocked/Review before trusting any signal.
    </div>
    """,
    unsafe_allow_html=True,
)

section_header("Quick Links", "Use these pages in order for the main workflow.")
links = [
    ("Slate Signal Board", "Start with the full player signal heatmap.", "23_Slate_Signal_Board"),
    ("By-Game Matchup Board", "Review players grouped by matchup context.", "24_By_Game_Matchup_Board"),
    ("Receiving Signal Board", "Inspect receiving-only signal rows.", "25_Receiving_Signal_Board"),
    ("Rushing Signal Board", "Inspect rushing-only signal rows.", "26_Rushing_Signal_Board"),
    ("Passing Signal Board", "Inspect quarterback passing signal rows.", "27_Passing_Signal_Board"),
    ("Player Signal Drilldown", "Open one player and inspect drivers, context, and history.", "33_Player_Signal_Drilldown"),
    ("Blocked / Review Board", "Finish by checking missing context and risk rows.", "28_Blocked_Review_Board"),
]
link_cols = st.columns(3)
for idx, (title, description, page) in enumerate(links):
    with link_cols[idx % len(link_cols)]:
        quick_link_card(title, description, page)

section_header("Workflow Note")
st.markdown(
    """
    <div class="info-card">
    The main product is the signal board workflow: players, games, recent form, defense fit,
    game environment, role/injury/readiness, and drilldown context. Model/debug pages are secondary.
    </div>
    """,
    unsafe_allow_html=True,
)
