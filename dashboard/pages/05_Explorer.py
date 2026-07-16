from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import ROLE_LABELS, explorer_usage, load_opportunity_events
from research_ui import (
    condition_box,
    methodology_expander,
    page_intro,
    ratio_text,
    responsive_table,
    role_noun,
    searchable_selectbox,
    section,
    selection_summary,
    source_footer,
)


def _reset_explorer() -> None:
    defaults = {
        "explorer_season": 2025,
        "explorer_team": "All",
        "explorer_player": "All",
        "explorer_family": "rb_carry_share",
        "explorer_weeks": (1, 18),
        "explorer_game_state": "All",
        "explorer_quarter": "All",
        "explorer_down": "All",
        "explorer_zone": "All",
        "explorer_two_minute": False,
        "explorer_normal": True,
        "explorer_minimum": 5,
    }
    for key, value in defaults.items():
        st.session_state[key] = value


page_intro(
    "Usage Explorer",
    "Build a historical opportunity view, then inspect its selected conditions and sample.",
)
events = load_opportunity_events()
summary_slot = st.empty()
with st.expander("Change filters"):
    row1 = st.columns(5)
    with row1[0]:
        season = st.selectbox("Season", [2025, 2024, 2023], key="explorer_season")
    season_events = events[events["season"].eq(season)]
    teams = ["All"] + sorted(season_events["team"].dropna().astype(str).unique().tolist())
    if st.session_state.get("explorer_team") not in teams:
        st.session_state["explorer_team"] = "All"
    with row1[1]:
        team_choice = searchable_selectbox(
            "Search or select team", teams, key="explorer_team",
            format_func=lambda value: "All teams" if value == "All" else value,
        )
    players = season_events if team_choice == "All" else season_events[season_events["team"].eq(team_choice)]
    player_rows = players[["player_id", "player_name", "team", "position"]].drop_duplicates("player_id").sort_values("player_name")
    player_ids = ["All"] + player_rows["player_id"].astype(str).tolist()
    player_labels = player_rows.set_index(player_rows["player_id"].astype(str)).apply(
        lambda row: f"{row['player_name']} · {row['team']} · {row['position']}", axis=1
    ).to_dict()
    if st.session_state.get("explorer_player") not in player_ids:
        st.session_state["explorer_player"] = "All"
    with row1[2]:
        player_choice = searchable_selectbox(
            "Search or select player", player_ids,
            format_func=lambda value: "All players" if value == "All" else player_labels.get(value, value),
            key="explorer_player",
        )
    with row1[3]:
        role_family = st.selectbox("Role family", list(ROLE_LABELS), format_func=ROLE_LABELS.get, key="explorer_family")
    weeks = sorted(season_events["week"].dropna().astype(int).unique().tolist())
    with row1[4]:
        week_range = st.select_slider("Week range", options=weeks, value=(weeks[0], weeks[-1]), key="explorer_weeks")

    row2 = st.columns(6)
    with row2[0]:
        game_state = st.selectbox("Game state", ["All", "Leading", "Trailing", "Close"], key="explorer_game_state")
    with row2[1]:
        quarter = st.selectbox("Quarter", ["All", "Q1", "Q2", "Q3", "Q4"], key="explorer_quarter")
    with row2[2]:
        down_distance = st.selectbox("Down & distance", ["All", "Early down", "Passing down", "Short yardage"], key="explorer_down")
    with row2[3]:
        field_zone = st.selectbox("Field zone", ["All", "Red zone", "Inside 10", "Inside 5"], key="explorer_zone")
    with row2[4]:
        two_minute = st.checkbox("Two-minute only", key="explorer_two_minute")
    with row2[5]:
        normal_game = st.checkbox("Normal-game only", value=True, key="explorer_normal")
    minimum_sample = st.slider("Minimum player opportunities", 1, 50, 5, key="explorer_minimum")
    st.button("Reset filters", on_click=_reset_explorer, key="explorer_reset")

summary, weekly = explorer_usage(
    season,
    week_range[0],
    week_range[1],
    role_family,
    player_id=None if player_choice == "All" else player_choice,
    team=None if team_choice == "All" else team_choice,
    game_state=game_state,
    quarter=quarter,
    down_distance=down_distance,
    field_zone=field_zone,
    two_minute=two_minute,
    normal_game=normal_game,
)
summary = summary[summary["raw_opportunities"].ge(minimum_sample)].copy()
condition_items = [f"{season} Weeks {week_range[0]}–{week_range[1]}", ROLE_LABELS[role_family]]
condition_items += [value for value in [team_choice, game_state, quarter, down_distance, field_zone] if value != "All"]
if player_choice != "All":
    condition_items.append(player_labels.get(player_choice, player_choice))
if two_minute:
    condition_items.append("Two minute")
if normal_game:
    condition_items.append("Normal game")
total_raw = int(summary["raw_opportunities"].sum()) if not summary.empty else 0
total_games = int(summary["sample_games"].sum()) if not summary.empty else 0
selection_summary(
    " · ".join(condition_items[:3]),
    " · ".join(condition_items[3:]) if len(condition_items) > 3 else "All remaining conditions",
    f"{total_raw} player opportunities · {total_games} player-games",
    target=summary_slot,
)
condition_box(
    "; ".join(condition_items) + ".",
    "Player opportunities divided by the matching team opportunity universe after the same filters.",
    f"Minimum {minimum_sample}; {len(summary)} players; {total_raw} opportunities across {total_games} player-games.",
)

section("Filtered results", "Top rows by opportunity share.")
if summary.empty:
    st.info("No rows match the current conditions and minimum sample.")
else:
    cards: list[dict[str, object]] = []
    for rank, (_, row) in enumerate(summary.head(12).iterrows(), start=1):
        cards.append(
            {
                "rank": f"#{rank}",
                "title": row["player_name"],
                "subtitle": f"{row['team']} · {row['position']} · {ROLE_LABELS[role_family]}",
                "metrics": [
                    ("Selected share", ratio_text(row["raw_opportunities"], row["team_denominator"], role_noun(role_family)), "Selected play conditions"),
                    ("Sample", f"{int(row['sample_games'])} games", f"Weeks {week_range[0]}–{week_range[1]}"),
                    ("Context", "Normal game" if normal_game else "All play", game_state if game_state != "All" else "All game states"),
                ],
                "href": f"/players?player={row['player_id']}&season={season}&family={role_family}",
            }
        )
    display = summary.copy()
    display["Share"] = display["share"] * 100.0
    display = display.rename(
        columns={
            "player_name": "Player", "team": "Team", "position": "Position",
            "raw_opportunities": "Raw", "team_denominator": "Denominator", "sample_games": "Games",
        }
    )
    responsive_table(
        display[["Player", "Team", "Position", "Share", "Raw", "Denominator", "Games"]],
        cards,
        key="explorer_results",
        height=520,
        percent_columns=["Share"],
        label="Open advanced table",
    )
    with st.expander("Show share-over-time chart"):
        selected_ids = summary["player_id"].astype(str).tolist()
        chart_rows = weekly[weekly["player_id"].astype(str).isin(selected_ids[:6])].copy()
        chart = chart_rows.pivot_table(index="week", columns="player_name", values="share", aggfunc="mean")
        st.line_chart(chart, height=260, y_label="Share")

methodology_expander(
    [
        "The team denominator is filtered by the same week, game state, quarter, down, field zone, and clock conditions.",
        "Choosing one player changes the numerator rows but does not change the team denominator universe.",
        "The displayed sample is calculated after the selected conditions and minimum opportunity threshold.",
    ]
)
source_footer("Completed historical play-level data through 2025; no 2026 usage is shown.")
