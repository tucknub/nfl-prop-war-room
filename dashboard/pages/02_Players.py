from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from research_data import (
    ROLE_LABELS,
    available_seasons,
    load_production_data,
    load_situational_data,
    opponent_from_game_id,
    player_profile,
    player_selector_rows,
    player_window_table,
    primary_rows,
    team_window_summary,
)
from research_ui import (
    enable_browser_history_sync,
    kpi_row,
    initialize_query_control,
    methodology_expander,
    nfl_week_axis_values,
    note,
    page_intro,
    parse_int,
    query_value,
    ratio_text,
    responsive_table,
    role_noun,
    searchable_selectbox,
    section,
    selection_summary,
    source_footer,
    table,
    update_query_from_widget,
)


def _whole(value: object) -> int:
    return 0 if pd.isna(value) else int(float(value))


enable_browser_history_sync()
page_intro(
    "Player Role Profile",
    "Compare season and recent opportunity windows, then inspect weekly counts and context.",
)

seasons = available_seasons()
season_state = initialize_query_control(
    "players", "season", "players_season", seasons, parser=parse_int
)
summary_slot = st.empty()
with st.expander("Change season"):
    season = st.selectbox(
        "Season",
        seasons,
        key="players_season",
        on_change=update_query_from_widget,
        args=("season", "players_season"),
        kwargs={"clear_query": ("player", "family", "week")},
    )

data = primary_rows()
season_data = data[data["season"].eq(season)]
requested_week_text = query_value("week")
requested_week = int(requested_week_text) if requested_week_text.isdigit() else None
season_weeks = sorted(season_data["week"].dropna().astype(int).unique().tolist())
if requested_week is not None and requested_week not in season_weeks:
    st.warning(f"Week not found for {season}: {requested_week_text}")
    st.link_button("Return to Players", "/players")
    st.stop()
selector_week = requested_week if requested_week is not None else (max(season_weeks) if season_weeks else None)
players = player_selector_rows(season_data, selector_week)
player_options = players["player_id"].astype(str).tolist()
labels = players.set_index(players["player_id"].astype(str)).apply(
    lambda row: f"{row['player_name']} · {row['team']} · {row['position']}", axis=1
).to_dict()
player_state = initialize_query_control(
    "players", "player", "players_player", player_options
)
selector_cols = st.columns([2.2, 1.2])
with selector_cols[0]:
    player_id = searchable_selectbox(
        "Search or select player",
        player_options,
        format_func=lambda value: labels.get(value, value),
        key="players_player",
        on_change=update_query_from_widget,
        args=("player", "players_player"),
        kwargs={"clear_query": ("family",)},
    )
family_rows = season_data[season_data["player_id"].astype(str).eq(player_id)]
families = family_rows["role_family"].dropna().astype(str).unique().tolist()
family_state = initialize_query_control(
    "players", "family", "players_family", families
)
with selector_cols[1]:
    role_family = st.selectbox(
        "Role family",
        families,
        format_func=ROLE_LABELS.get,
        key="players_family",
        on_change=update_query_from_widget,
        args=("family", "players_family"),
    )

if season_state.invalid_query or player_state.invalid_query or family_state.invalid_query:
    if season_state.invalid_query:
        st.warning("The requested season was not found. Select a valid season to continue.")
    if player_state.invalid_query:
        st.warning("Player not found. Search for and select a valid player to continue.")
    if family_state.invalid_query:
        st.warning("The requested role family is unavailable for this player. Select a valid role family.")
    st.stop()

profile = player_profile(player_id, season, role_family)
if requested_week is not None:
    profile = profile[profile["week"].le(requested_week)].copy()
if profile.empty:
    st.info("No player rows match the selected filters.")
    st.stop()
player = profile.iloc[-1]
end_week = requested_week if requested_week is not None else int(profile["week"].max())
selection_summary(
    f"{player['player_name']} · {player['team']} · {player['position']}",
    f"{season} · {ROLE_LABELS[role_family]}",
    f"{profile['week'].nunique()} qualifying games through Week {end_week}",
    target=summary_slot,
)

windows = player_window_table(profile, end_week)
window_index = windows.set_index("Window")
kpi_row(
    [
        (label, f"{window_index.loc[label, 'Normal share'] * 100:.1f}%", f"{int(window_index.loc[label, 'Normal raw'])} / {int(window_index.loc[label, 'Normal denominator'])} · {int(window_index.loc[label, 'Games'])} games")
        for label in ["Season", "Last 8", "Last 4", "Last 2"]
    ]
)

team_rank_rows = team_window_summary(season, str(player["team"]), role_family, end_week, "Season", "Normal game")
rank_matches = team_rank_rows.reset_index().loc[team_rank_rows.reset_index()["player_id"].astype(str).eq(player_id), "index"]
role_rank = int(rank_matches.iloc[0]) + 1 if not rank_matches.empty else 0
suspected_weeks = profile.loc[profile["suspected_partial_game"], "week"].astype(int).tolist()
participation = f"Suspected Week {', '.join(map(str, suspected_weeks))}" if suspected_weeks else "No flagged rows"
kpi_row(
    [
        ("Normal-game count", f"{int(profile['raw_opportunities_normal'].sum())} / {int(profile['team_opportunities_normal'].sum())}", "Player / team opportunities"),
        ("Team role rank", f"{role_rank} of {len(team_rank_rows)}", ROLE_LABELS[role_family]),
        ("Qualifying games", str(profile["week"].nunique()), f"Through Week {end_week}"),
        ("Participation", participation, "Suspected rows remain included"),
    ]
)

section("Weekly opportunity", "Weeks 1–18; hover for player and team counts.")
chart_mode = st.segmented_control(
    "Chart measure",
    ["Share", "Raw opportunities", "Team denominator"],
    default="Share",
    label_visibility="collapsed",
    key="players_chart_measure",
)
if chart_mode == "Share":
    chart_data = profile[["week", "metric_all", "metric_normal", "raw_opportunities_all", "team_opportunities_all", "raw_opportunities_normal", "team_opportunities_normal"]].copy()
    chart_data = chart_data.melt(
        id_vars=["week", "raw_opportunities_all", "team_opportunities_all", "raw_opportunities_normal", "team_opportunities_normal"],
        value_vars=["metric_all", "metric_normal"],
        var_name="series",
        value_name="value",
    )
    chart_data["Series"] = chart_data["series"].map({"metric_all": "All play", "metric_normal": "Normal game"})
    chart_data["Raw"] = chart_data.apply(
        lambda row: row["raw_opportunities_all"] if row["series"] == "metric_all" else row["raw_opportunities_normal"], axis=1
    )
    chart_data["Denominator"] = chart_data.apply(
        lambda row: row["team_opportunities_all"] if row["series"] == "metric_all" else row["team_opportunities_normal"], axis=1
    )
    y = alt.Y("value:Q", title="Share", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1]))
else:
    source = "raw_opportunities_all" if chart_mode == "Raw opportunities" else "team_opportunities_all"
    chart_data = profile[["week", "raw_opportunities_all", "team_opportunities_all"]].copy()
    chart_data["value"] = chart_data[source]
    chart_data = chart_data.rename(columns={"raw_opportunities_all": "Raw", "team_opportunities_all": "Denominator"})
    chart_data["Series"] = chart_mode
    y = alt.Y("value:Q", title=chart_mode)
chart_data = chart_data.rename(columns={"week": "Week"})
base_chart = (
    alt.Chart(chart_data)
    .mark_line(point=alt.OverlayMarkDef(size=48), strokeWidth=2.2)
    .encode(
        x=alt.X("Week:Q", scale=alt.Scale(domain=[1, 18]), axis=alt.Axis(values=nfl_week_axis_values(), tickMinStep=1, title="NFL week")),
        y=y,
        tooltip=[alt.Tooltip("Week:Q", format=".0f"), "Series:N", alt.Tooltip("value:Q", format=".1%" if chart_mode == "Share" else ".0f"), alt.Tooltip("Raw:Q", format=".0f"), alt.Tooltip("Denominator:Q", format=".0f")],
    )
    .properties(height=255)
)
if chart_mode == "Share":
    chart = base_chart.encode(
        color=alt.Color(
            "Series:N",
            scale=alt.Scale(domain=["All play", "Normal game"], range=["#0b5cff", "#8a9aae"]),
            legend=alt.Legend(orient="top", title=None),
        )
    )
else:
    chart = base_chart.mark_line(
        point=alt.OverlayMarkDef(size=48), strokeWidth=2.2, color="#0b5cff"
    )
st.altair_chart(chart, width="stretch")

team_weeks = set(
    season_data.loc[season_data["team"].eq(player["team"]), "week"].dropna().astype(int).tolist()
)
profile_weeks = set(profile["week"].dropna().astype(int).tolist())
bye_weeks = [week for week in range(1, end_week + 1) if week not in team_weeks]
missing_weeks = [week for week in range(1, end_week + 1) if week in team_weeks and week not in profile_weeks]
status_parts = []
if bye_weeks:
    status_parts.append("Bye: " + ", ".join(map(str, bye_weeks)))
if missing_weeks:
    status_parts.append("No qualifying row: " + ", ".join(map(str, missing_weeks)))
if status_parts:
    note(" · ".join(status_parts))

section("Weekly counts", "All-play and normal-game counts remain visible with participation notes.")
game_log = profile.copy()
game_log["Opponent"] = game_log.apply(lambda row: opponent_from_game_id(row["game_id"], row["team"]), axis=1)
production = load_production_data()
production = production[production["season"].eq(season) & production["player_id"].astype(str).eq(player_id)]
if not production.empty:
    game_log = game_log.merge(
        production[["game_id", "carries", "targets", "receptions", "rushing_yards", "receiving_yards"]],
        on="game_id", how="left",
    )
cards = []
for _, row in game_log.sort_values("week", ascending=False).iterrows():
    participation_note = str(row["partial_game_note"])
    participation_label = participation_note if participation_note != "Included" else "No participation flag"
    cards.append(
        {
            "rank": f"Week {int(row['week'])}",
            "title": f"{row['team']} vs {row['Opponent']}",
            "subtitle": participation_label,
            "metrics": [
                ("All play", ratio_text(row["raw_opportunities_all"], row["team_opportunities_all"], role_noun(role_family)), "Player / team opportunities"),
                ("Normal game", ratio_text(row["raw_opportunities_normal"], row["team_opportunities_normal"], role_noun(role_family)), "Player / team opportunities"),
                ("Production", f"{_whole(row.get('carries'))} carries · {_whole(row.get('targets'))} targets", f"{_whole(row.get('receptions'))} receptions"),
            ],
        }
    )
display = game_log[[
    "week", "Opponent", "raw_opportunities_all", "team_opportunities_all", "metric_all",
    "raw_opportunities_normal", "team_opportunities_normal", "metric_normal", "partial_game_note",
]].rename(
    columns={
        "week": "Week", "raw_opportunities_all": "All raw", "team_opportunities_all": "All denominator",
        "metric_all": "All share", "raw_opportunities_normal": "Normal raw",
        "team_opportunities_normal": "Normal denominator", "metric_normal": "Normal share",
        "partial_game_note": "Participation note",
    }
)
display["All share"] = display["All share"] * 100.0
display["Normal share"] = display["Normal share"] * 100.0
display["Participation note"] = display["Participation note"].replace("Included", "No flag")
responsive_table(display, cards, key="player_weekly", height=520, percent_columns=["All share", "Normal share"])

if season >= 2023:
    with st.expander("Situational counts"):
        situation = load_situational_data()
        situation = situation[
            situation["season"].eq(season) & situation["player_id"].astype(str).eq(player_id)
            & situation["role_family"].eq(role_family)
        ]
        if situation.empty:
            st.info("No situational opportunities are available for this player and role family.")
        else:
            situ_summary = situation.groupby("context", as_index=False).agg(
                Raw=("raw_opportunities", "sum"), Denominator=("team_opportunities", "sum")
            )
            situ_summary["Share"] = situ_summary["Raw"] / situ_summary["Denominator"].replace(0, pd.NA) * 100.0
            situ_summary["Context"] = situ_summary["context"].str.replace("_", " ").str.title()
            table(situ_summary[["Context", "Raw", "Denominator", "Share"]], height=360, percent_columns=["Share"])

methodology_expander(
    [
        "Window shares sum player and team opportunities before calculating the percentage.",
        "A team bye is separated from a week in which the team played but the player had no qualifying row.",
        "All-play and normal-game values use the same player identity and team-week join.",
    ]
)
source_footer("Player identity uses the canonical GSIS player ID and team-week join.")
