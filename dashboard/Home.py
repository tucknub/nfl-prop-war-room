from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import available_seasons, available_weeks, observable_changes, pp
from research_ui import inject_styles, page_intro, render_change_rows, section, source_footer, table, team_rail, yard_rule


inject_styles()
page_intro(
    "Weekly Observable Changes",
    "Factual changes in player opportunity share, with the numerator, team denominator, and baseline shown.",
)

seasons = available_seasons()
filters = st.columns([1, 1, 2.8])
with filters[0]:
    season = st.selectbox("Season", seasons, index=0)
weeks = available_weeks(season)
with filters[1]:
    week = st.selectbox("Week", weeks, index=len(weeks) - 1)
with filters[2]:
    st.caption("Recent game compared with the prior four qualifying games in the same season. No future game is used.")

changes = observable_changes(season, week)
section("Observable change detail", "Largest absolute share changes; ranking is descriptive only.")
render_change_rows(changes, limit=5)
yard_rule()

section("Quick Team Access", "Teams represented in the selected week.")
teams = sorted(changes["team"].dropna().astype(str).unique().tolist()) if not changes.empty else []
team_rail(teams)

section("Players to Inspect", "Ordered only by absolute percentage-point change.")
if changes.empty:
    st.info("No players meet the baseline requirement for this week.")
else:
    inspect = changes.head(30).copy()
    inspect.insert(0, "Rank", range(1, len(inspect) + 1))
    inspect["Change"] = inspect["change"].map(pp)
    inspect = inspect.rename(columns={
        "player_name": "Player", "team": "Team", "role_family_label": "Role family",
        "raw_opportunities": "Opportunities", "team_denominator": "Denominator",
        "baseline_games": "Games in baseline", "partial_game_note": "Participation note",
    })
    table(
        inspect[["Rank", "Player", "Team", "Role family", "Change", "Opportunities", "Denominator", "Games in baseline", "Participation note"]],
        height=520,
    )

source_footer("Latest completed season is 2024; no 2026 data is shown.")
