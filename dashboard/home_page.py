from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import ROLE_LABELS, available_seasons, available_weeks, observable_changes, pp
from research_ui import methodology_expander, overview, page_intro, render_change_rows, section, selection_summary, source_footer


def _largest_change(frame: pd.DataFrame, families: set[str]) -> str:
    rows = frame[frame["role_family"].isin(families) & frame["change"].gt(0)]
    if rows.empty:
        return "—"
    row = rows.sort_values("change", ascending=False).iloc[0]
    return f"{row['player_name']} {pp(row['change'])}"


def render_home() -> None:
    page_intro(
        "Weekly Observable Changes",
        "Recent player opportunity shares compared with each player’s prior qualifying games.",
    )

    summary_slot = st.empty()
    with st.expander("Change filters"):
        controls = st.columns(5)
        with controls[0]:
            season = st.selectbox("Season", available_seasons(), key="home_season")
        weeks = available_weeks(season)
        with controls[1]:
            week = st.selectbox("Week", weeks, index=len(weeks) - 1, key="home_week")
        all_changes = observable_changes(season, week)
        positions = ["All"] + sorted(all_changes["position"].dropna().astype(str).unique().tolist())
        with controls[2]:
            position = st.selectbox("Position", positions, key="home_position")
        family_options = ["All"] + list(ROLE_LABELS)
        with controls[3]:
            family = st.selectbox(
                "Role family",
                family_options,
                format_func=lambda value: "All role families" if value == "All" else ROLE_LABELS[value],
                key="home_family",
            )
        with controls[4]:
            direction = st.selectbox("Direction", ["All", "Increase", "Decrease"], key="home_direction")

    changes = all_changes.copy()
    if position != "All":
        changes = changes[changes["position"].eq(position)]
    if family != "All":
        changes = changes[changes["role_family"].eq(family)]
    if direction == "Increase":
        changes = changes[changes["change"].gt(0)]
    elif direction == "Decrease":
        changes = changes[changes["change"].lt(0)]

    family_text = "All role families" if family == "All" else ROLE_LABELS[family]
    selection_summary(
        f"{season} · Week {week}",
        f"{position if position != 'All' else 'All positions'} · {family_text} · {direction}",
        f"{len(changes)} matching rows",
        target=summary_slot,
    )
    overview(
        [
            ("What changed", f"{len(changes)} rows"),
            ("RB carry increase", _largest_change(changes, {"rb_carry_share"})),
            ("Target-share increase", _largest_change(changes, {"wr_target_share", "te_target_share"})),
            (
                "Abnormal context",
                f"{int(changes['partial_game_note'].astype(str).str.contains('Suspected', case=False).sum())} suspected"
                if not changes.empty else "0 suspected",
            ),
        ]
    )

    section("Largest changes", "Descriptive ranking by absolute percentage-point change.")
    show_more = st.toggle("Show up to 20 rows", value=False, key="home_show_more")
    render_change_rows(changes, limit=20 if show_more else 10)

    methodology_expander(
        [
            "The recent game is compared with up to four prior qualifying games in the same season.",
            "Shares use player opportunities divided by the matching team opportunity count.",
            "Confirmed partial games are excluded; suspected partial games remain visible.",
            "Rankings describe historical usage only and do not claim that a change will continue.",
        ]
    )
    source_footer("Completed historical data through 2025; the 2026 NFL season has not started.")
