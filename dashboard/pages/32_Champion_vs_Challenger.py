from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from signal_ui import build_heatmap_styler, load_signal_csv, render_signal_table
from utils import inject_global_styles, metric_card, page_header, section_header, sidebar_status, warning_banner


PREVIEW_ROWS = "outputs/signal_boards/signal_challenger_preview_rows.csv"
SUMMARY = "outputs/signal_boards/signal_challenger_preview_summary.csv"
FAMILY = "outputs/signal_boards/signal_challenger_family_comparison.csv"
MOVERS = "outputs/signal_boards/signal_challenger_top_movers.csv"
CHANGES = "outputs/signal_boards/signal_challenger_tier_changes.csv"


def metric_value(summary: pd.DataFrame, name: str, fallback: object = "n/a") -> object:
    if summary.empty or not {"metric", "value"}.issubset(summary.columns):
        return fallback
    row = summary[summary["metric"].astype(str).eq(name)]
    return fallback if row.empty else row["value"].iloc[0]


def board_view(preview: pd.DataFrame, family: str, mode: str) -> pd.DataFrame:
    data = preview[preview["market_family"].astype(str).eq(family)].copy() if family != "all" else preview.copy()
    if data.empty:
        return data
    if mode == "Champion":
        data["display_score"] = pd.to_numeric(data["current_overall_signal_score"], errors="coerce")
        data["display_tier"] = data["current_signal_tier"]
        data["display_action"] = data["current_recommended_user_action"]
    elif mode == "Challenger":
        data["display_score"] = pd.to_numeric(data["challenger_overall_signal_score"], errors="coerce")
        data["display_tier"] = data["challenger_signal_tier"]
        data["display_action"] = data["challenger_recommended_user_action"]
    else:
        data["display_score"] = pd.to_numeric(data["signal_score_delta"], errors="coerce")
        data["display_tier"] = data["tier_change"]
        data["display_action"] = data["action_change"]
    return data.sort_values("display_score", ascending=False).head(250)


st.set_page_config(page_title="Champion vs Challenger Signal Preview", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "Champion vs Challenger Signal Preview",
    "Visual comparison of production current_v1 scoring versus research-only challenger scoring.",
    "HISTORICAL TEST ONLY",
)
st.caption("Section: Research / Audit Lab")
warning_banner(
    "Research-only",
    "Challenger weights are not applied to production signal boards.",
)

preview = load_signal_csv(PREVIEW_ROWS)
summary = load_signal_csv(SUMMARY)
family = load_signal_csv(FAMILY)
movers = load_signal_csv(MOVERS)
changes = load_signal_csv(CHANGES)

cols = st.columns(6)
with cols[0]:
    metric_card("Rows Previewed", metric_value(summary, "rows_previewed", len(preview)), "INFO")
with cols[1]:
    metric_card("Families Testing", metric_value(summary, "families_with_challenger_test", 0), "CHECK")
with cols[2]:
    metric_card("Tier Upgrades", metric_value(summary, "tier_upgrades", 0), "PASS")
with cols[3]:
    metric_card("Tier Downgrades", metric_value(summary, "tier_downgrades", 0), "REVIEW")
with cols[4]:
    metric_card("Action Changes", metric_value(summary, "action_changes", 0), "CHECK")
with cols[5]:
    metric_card("Production Champion", "current_v1", "PASS")

render_signal_table(
    family,
    ["avg_current_score", "avg_challenger_score", "avg_score_delta"],
    [
        "market_family",
        "champion_profile",
        "challenger_profile",
        "row_count",
        "avg_current_score",
        "avg_challenger_score",
        "avg_score_delta",
        "current_elite_strong_count",
        "challenger_elite_strong_count",
        "tier_upgrade_count",
        "tier_downgrade_count",
        "action_change_count",
        "preview_recommendation",
        "notes",
    ],
    "Family Comparison",
)

render_signal_table(
    movers.head(100) if not movers.empty else movers,
    ["current_overall_signal_score", "challenger_overall_signal_score", "signal_score_delta"],
    [
        "player_name",
        "team",
        "opponent",
        "position",
        "market_family",
        "current_overall_signal_score",
        "challenger_overall_signal_score",
        "signal_score_delta",
        "current_signal_tier",
        "challenger_signal_tier",
        "tier_change",
        "current_recommended_user_action",
        "challenger_recommended_user_action",
        "preview_flag",
        "preview_notes",
    ],
    "Top Movers",
)

render_signal_table(
    changes,
    ["current_overall_signal_score", "challenger_overall_signal_score", "signal_score_delta"],
    [
        "player_name",
        "team",
        "opponent",
        "position",
        "market_family",
        "challenger_profile_name",
        "current_signal_tier",
        "challenger_signal_tier",
        "tier_change",
        "current_recommended_user_action",
        "challenger_recommended_user_action",
        "action_change",
        "preview_usage_status",
    ],
    "Tier And Action Changes",
)

section_header("Side-by-Side Board Preview", "Existing production boards remain on current_v1.")
if preview.empty:
    st.info("No challenger preview rows available.")
else:
    control_cols = st.columns(2)
    with control_cols[0]:
        selected_family = st.selectbox("Market family", ["all", "receiving", "rushing", "passing"])
    with control_cols[1]:
        selected_view = st.selectbox("View", ["Champion", "Challenger", "Delta"])
    board = board_view(preview, selected_family, selected_view)
    columns = [
        "player_name",
        "team",
        "opponent",
        "position",
        "market_family",
        "production_champion_profile",
        "challenger_profile_name",
        "display_score",
        "display_tier",
        "display_action",
        "current_overall_signal_score",
        "challenger_overall_signal_score",
        "signal_score_delta",
        "preview_usage_status",
        "preview_notes",
    ]
    view = board[[col for col in columns if col in board.columns]]
    st.dataframe(
        build_heatmap_styler(view, ["display_score", "current_overall_signal_score", "challenger_overall_signal_score", "signal_score_delta"], ["display_tier", "preview_usage_status"]),
        use_container_width=True,
        hide_index=True,
    )

section_header("Promotion Note")
st.markdown(
    """
    <div class="info-card">
    No challenger profile is promoted automatically. Promotion requires explicit user approval after reviewing historical results and board behavior.
    </div>
    """,
    unsafe_allow_html=True,
)
