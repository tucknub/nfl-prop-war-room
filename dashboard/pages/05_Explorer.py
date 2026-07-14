from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import ROLE_LABELS, explorer_usage, load_opportunity_events, percent
from research_ui import condition_box, inject_styles, note, page_intro, section, source_footer, table


inject_styles()
page_intro(
    "Usage Explorer",
    "Guided play-level filters for 2023–2024 with the applied conditions, denominator definition, and sample shown every time.",
)
events = load_opportunity_events()
row1 = st.columns([1, 1, 1, 1, 1])
with row1[0]:
    season = st.selectbox("Season", [2024, 2023])
season_events = events[events["season"].eq(season)]
teams = ["All"] + sorted(season_events["team"].dropna().astype(str).unique().tolist())
with row1[1]:
    team_choice = st.selectbox("Team", teams)
players = season_events if team_choice == "All" else season_events[season_events["team"].eq(team_choice)]
player_rows = players[["player_id", "player_name", "team", "position"]].drop_duplicates("player_id").sort_values("player_name")
player_ids = ["All"] + player_rows["player_id"].astype(str).tolist()
player_labels = player_rows.set_index(player_rows["player_id"].astype(str)).apply(
    lambda row: f"{row['player_name']} · {row['team']} · {row['position']}", axis=1
).to_dict()
with row1[2]:
    player_choice = st.selectbox("Player", player_ids, format_func=lambda value: "All players" if value == "All" else player_labels.get(value, value))
with row1[3]:
    role_family = st.selectbox("Role family", list(ROLE_LABELS), format_func=ROLE_LABELS.get)
weeks = sorted(season_events["week"].dropna().astype(int).unique().tolist())
with row1[4]:
    week_range = st.select_slider("Week range", options=weeks, value=(weeks[0], weeks[-1]))

row2 = st.columns(6)
with row2[0]:
    game_state = st.selectbox("Game state", ["All", "Leading", "Trailing", "Close"])
with row2[1]:
    quarter = st.selectbox("Quarter", ["All", "Q1", "Q2", "Q3", "Q4"])
with row2[2]:
    down_distance = st.selectbox("Down & distance", ["All", "Early down", "Passing down", "Short yardage"])
with row2[3]:
    field_zone = st.selectbox("Field zone", ["All", "Red zone", "Inside 10", "Inside 5"])
with row2[4]:
    two_minute = st.checkbox("Two-minute only")
with row2[5]:
    normal_game = st.checkbox("Normal-game only", value=True)
minimum_sample = st.slider("Minimum player opportunities", 1, 50, 5)

summary, weekly = explorer_usage(
    season, week_range[0], week_range[1], role_family,
    player_id=None if player_choice == "All" else player_choice,
    team=None if team_choice == "All" else team_choice,
    game_state=game_state, quarter=quarter, down_distance=down_distance,
    field_zone=field_zone, two_minute=two_minute, normal_game=normal_game,
)
summary = summary[summary["raw_opportunities"].ge(minimum_sample)]
conditions = [f"{season} Weeks {week_range[0]}–{week_range[1]}", ROLE_LABELS[role_family]]
conditions += [value for value in [team_choice, game_state, quarter, down_distance, field_zone] if value != "All"]
if player_choice != "All":
    conditions.append(player_labels.get(player_choice, player_choice))
if two_minute:
    conditions.append("two-minute")
if normal_game:
    conditions.append("normal-game")
condition_box(
    "; ".join(conditions) + ".",
    "The denominator is the matching team opportunity universe after the same play filters; player filters affect only the numerator.",
    f"{int(summary['raw_opportunities'].sum()) if not summary.empty else 0} player opportunities across {int(summary['sample_games'].sum()) if not summary.empty else 0} player-games.",
)

if summary.empty:
    st.info("No rows match the current conditions and minimum sample.")
else:
    selected_ids = summary["player_id"].astype(str).tolist()
    chart_rows = weekly[weekly["player_id"].astype(str).isin(selected_ids[:8])].copy()
    chart = chart_rows.pivot_table(index="week", columns="player_name", values="share", aggfunc="mean")
    section("Share over time", "Up to eight visible players.")
    st.line_chart(chart, height=340, y_label="Share")
    section("Filtered usage table")
    view = summary.copy()
    view["Share"] = view["share"].map(percent)
    view = view.rename(columns={
        "player_name": "Player", "team": "Team", "position": "Position",
        "raw_opportunities": "Raw opportunities", "team_denominator": "Team denominator", "sample_games": "Sample games",
    })
    table(view[["Player", "Team", "Position", "Share", "Raw opportunities", "Team denominator", "Sample games"]], height=520)
source_footer("The Explorer never reads 2025 rows; its committed event extract contains 2023–2024 only.")
