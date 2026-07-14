from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import (
    ROLE_LABELS,
    available_seasons,
    available_weeks,
    percent,
    pp,
    primary_rows,
    situational_team_summary,
    team_window_summary,
)
from research_ui import inject_styles, note, page_intro, section, source_footer, table, yard_rule


inject_styles()
page_intro(
    "Team Opportunity Map",
    "A depth-chart view of who accounted for each team’s carries, running-back opportunities, and targets.",
)

seasons = available_seasons()
top = st.columns([1, 1.2, 1, 1.2, 1.5])
with top[0]:
    season = st.selectbox("Season", seasons)
season_rows = primary_rows()
season_rows = season_rows[season_rows["season"].eq(season)]
teams = sorted(season_rows["team"].dropna().astype(str).unique().tolist())
with top[1]:
    team = st.selectbox("Team", teams)
with top[2]:
    window_label = st.selectbox("Window", ["Season", "Last 8", "Last 4", "Last 2"], index=2)
window = "Season" if window_label == "Season" else int(window_label.split()[-1])
with top[3]:
    context = st.selectbox("Context", ["All plays", "Normal game"], index=1)
family_options = list(ROLE_LABELS)
with top[4]:
    role_family = st.selectbox("Role family", family_options, format_func=ROLE_LABELS.get)

end_week = max(available_weeks(season))
summary = team_window_summary(season, team, role_family, end_week, window, context)
section(ROLE_LABELS[role_family], f"Through Week {end_week} · {window_label} · {context}")
if season >= 2023:
    note("Situational splits are available for 2023–2024 and use same-game team opportunity denominators.")
    situational = situational_team_summary(season, team, role_family, end_week, window)
    if not situational.empty:
        summary = summary.merge(situational, on=["player_id", "player_name", "position"], how="left")
else:
    note("This season supports audited overall and normal-game shares. Down, clock, and field-zone splits begin in 2023.", amber=True)

if summary.empty:
    st.info("No team rows match the selected filters.")
else:
    view = summary.rename(columns={"player_name": "Player", "position": "Position"}).copy()
    view["Overall share"] = view["share"].map(percent)
    view["Change vs prior"] = view["change"].map(pp)
    context_columns = [
        ("all_play", "All-play split"), ("normal_game", "Normal-game split"),
        ("early_down", "Early down"), ("passing_down", "Passing down"),
        ("two_minute", "Two minute"), ("short_yardage", "Short yardage"),
        ("red_zone", "Red zone"), ("inside_10", "Inside 10"), ("inside_5", "Inside 5"),
    ]
    if role_family in {"wr_target_share", "te_target_share"}:
        context_columns.append(("end_zone", "End-zone targets"))
    selected = ["Player", "Position", "Overall share"]
    for source, label in context_columns:
        if source in view:
            view[label] = view[source].map(percent)
            selected.append(label)
    view["Raw opportunities"] = view["raw_opportunities"].astype(int)
    view["Team denominator"] = view["team_denominator"].astype(int)
    view["Sample games"] = view["sample_games"].astype(int)
    core = selected[:3] + ["Raw opportunities", "Team denominator", "Sample games", "Change vs prior"]
    game_script = ["Player", "Position"] + [
        column for column in ["Early down", "Passing down", "Two minute", "Short yardage"] if column in view
    ]
    scoring = ["Player", "Position"] + [
        column for column in ["Red zone", "Inside 10", "Inside 5", "End-zone targets"] if column in view
    ]
    ownership_tab, script_tab, scoring_tab = st.tabs(["Role ownership", "Game script", "Scoring area"])
    with ownership_tab:
        table(view[core], height=500)
    with script_tab:
        table(view[game_script], height=500)
    with scoring_tab:
        table(view[scoring], height=500)

yard_rule()
source_footer("Shares are ratios, not depth-chart labels or forecasts.")
