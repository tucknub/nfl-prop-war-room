from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import (
    filter_minimum,
    filter_multiselect,
    inject_signal_css,
    load_signal_csv,
    render_signal_legend,
    render_signal_table,
    top_signal_cards,
)
from utils import inject_global_styles, metric_card, page_header, sidebar_status, warning_banner


SCORE_COLUMNS = [
    "overall_signal_score",
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "role_availability_score",
    "volatility_score",
    "data_quality_score",
]

BOARD_CONFIG = {
    "Receiving": {
        "path": "outputs/signal_boards/receiving_signal_board.csv",
        "title": "Receiving Signal Board",
        "projection_filters": [
            ("receiving_yards_projection", "Minimum receiving yards projection"),
            ("receptions_projection", "Minimum receptions projection"),
        ],
        "environment": "pass_volume_environment",
        "display_columns": [
            "player_name",
            "team",
            "opponent",
            "position",
            "overall_signal_score",
            "signal_tier",
            "receptions_projection",
            "receiving_yards_projection",
            "l3_targets",
            "l5_targets",
            "l3_receptions",
            "l5_receptions",
            "l3_receiving_yards",
            "l5_receiving_yards",
            "opp_receiving_fit_score",
            "defense_fit_reliability",
            "pass_volume_environment",
            "projection_score",
            "usage_foundation_score",
            "recent_form_score",
            "opponent_fit_score",
            "game_script_score",
            "role_availability_score",
            "volatility_score",
            "data_quality_score",
            "green_signal_count",
            "red_flag_count",
            "recommended_user_action",
            "top_signal_reason",
            "review_reason",
        ],
    },
    "Rushing": {
        "path": "outputs/signal_boards/rushing_signal_board.csv",
        "title": "Rushing Signal Board",
        "projection_filters": [
            ("rushing_yards_projection", "Minimum rushing yards projection"),
            ("carries_projection", "Minimum carries projection"),
        ],
        "environment": "rush_volume_environment",
        "display_columns": [
            "player_name",
            "team",
            "opponent",
            "position",
            "overall_signal_score",
            "signal_tier",
            "rushing_yards_projection",
            "carries_projection",
            "l3_carries",
            "l5_carries",
            "l3_rushing_yards",
            "l5_rushing_yards",
            "opp_rushing_fit_score",
            "defense_fit_reliability",
            "rush_volume_environment",
            "projection_score",
            "usage_foundation_score",
            "recent_form_score",
            "opponent_fit_score",
            "game_script_score",
            "role_availability_score",
            "volatility_score",
            "data_quality_score",
            "green_signal_count",
            "red_flag_count",
            "recommended_user_action",
            "top_signal_reason",
            "review_reason",
        ],
    },
    "Passing": {
        "path": "outputs/signal_boards/passing_signal_board.csv",
        "title": "Passing Signal Board",
        "projection_filters": [
            ("passing_yards_projection", "Minimum passing yards projection"),
            ("pass_attempts_projection", "Minimum pass attempts projection"),
        ],
        "environment": "pass_volume_environment",
        "display_columns": [
            "player_name",
            "team",
            "opponent",
            "position",
            "overall_signal_score",
            "signal_tier",
            "passing_yards_projection",
            "pass_attempts_projection",
            "completions_projection",
            "l3_pass_attempts",
            "l5_pass_attempts",
            "l3_passing_yards",
            "l5_passing_yards",
            "opp_passing_fit_score",
            "defense_fit_reliability",
            "pass_volume_environment",
            "projection_score",
            "usage_foundation_score",
            "recent_form_score",
            "opponent_fit_score",
            "game_script_score",
            "role_availability_score",
            "volatility_score",
            "data_quality_score",
            "green_signal_count",
            "red_flag_count",
            "recommended_user_action",
            "top_signal_reason",
            "review_reason",
        ],
    },
}


def top_name(df: pd.DataFrame, column: str) -> str:
    if df.empty or column not in df.columns:
        return "n/a"
    values = pd.to_numeric(df[column], errors="coerce")
    if not values.notna().any():
        return "n/a"
    row = df.loc[values.idxmax()]
    return f"{row.get('player_name', 'n/a')} ({values.max():.1f})"


def render_board(tab_name: str, config: dict[str, object]) -> None:
    df = load_signal_csv(str(config["path"]))
    if df.empty:
        st.warning(f"Missing or empty file: `{config['path']}`")
        return

    with st.sidebar:
        st.markdown(f"### {tab_name} Filters")
        view = df.copy()
        view = filter_multiselect(view, "team", "Team")
        view = filter_multiselect(view, "opponent", "Opponent")
        view = filter_multiselect(view, "position", "Position")
        view = filter_multiselect(view, "signal_tier", "Signal tier")
        view = filter_multiselect(view, "recent_form_reliability", "Recent form reliability")
        view = filter_multiselect(view, "defense_fit_reliability", "Defense fit reliability")
        view = filter_multiselect(view, str(config["environment"]), "Volume environment")
        view = filter_multiselect(view, "game_total_bucket", "Game total bucket")
        view = filter_multiselect(view, "spread_bucket", "Spread bucket")
        for column, label in config["projection_filters"]:
            view = filter_minimum(view, column, label, 0.0)

    cols = st.columns(4)
    with cols[0]:
        metric_card("Best Overall", top_name(view, "overall_signal_score"), "INFO")
    with cols[1]:
        first_projection = config["projection_filters"][0][0]
        metric_card("Best Projection", top_name(view, first_projection), "INFO")
    with cols[2]:
        metric_card("Rows", len(view), "INFO")
    with cols[3]:
        risk = pd.to_numeric(view.get("red_flag_count", pd.Series(dtype=float)), errors="coerce")
        risk_name = view.loc[risk.idxmax()].get("player_name", "n/a") if risk.notna().any() else "n/a"
        metric_card("Most Review Risk", risk_name, "REVIEW")

    top_signal_cards(view, count=5)
    st.caption("Defense fit is reliability-adjusted and should not be treated as certain. Open Player Signal Drilldown for the why.")
    render_signal_table(
        view.sort_values("overall_signal_score", ascending=False).head(300),
        SCORE_COLUMNS,
        list(config["display_columns"]),
        str(config["title"]),
    )


st.set_page_config(page_title="Position Signal Boards", layout="wide")
inject_global_styles()
inject_signal_css()
sidebar_status()

page_header("Position Signal Boards", "Receiving, rushing, and passing signals in one clean workspace.", "HISTORICAL TEST ONLY")
warning_banner("HISTORICAL TEST ONLY - NOT LIVE BETTING READY", "These are sourced signal boards, not betting recommendations.")
st.caption("Section: Main Signal Workflow")
render_signal_legend()

tabs = st.tabs(["Receiving", "Rushing", "Passing"])
for tab, (name, config) in zip(tabs, BOARD_CONFIG.items()):
    with tab:
        render_board(name, config)
