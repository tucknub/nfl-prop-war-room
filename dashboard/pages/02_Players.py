from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import (
    ROLE_LABELS,
    available_seasons,
    load_production_data,
    load_situational_data,
    opponent_from_game_id,
    percent,
    player_profile,
    player_window_table,
    pp,
    primary_rows,
)
from research_ui import condition_box, inject_styles, note, page_intro, section, source_footer, table


inject_styles()
page_intro(
    "Player Role Profile",
    "Weekly opportunity shares, transparent windows, game logs, and participation-quality notes for one player.",
)

seasons = available_seasons()
filters = st.columns([1, 2.2, 1.5])
with filters[0]:
    season = st.selectbox("Season", seasons)
data = primary_rows()
season_data = data[data["season"].eq(season)]
players = season_data[["player_id", "player_name", "team", "position"]].drop_duplicates("player_id").sort_values("player_name")
player_options = players["player_id"].astype(str).tolist()
labels = players.set_index(players["player_id"].astype(str)).apply(
    lambda row: f"{row['player_name']} · {row['team']} · {row['position']}", axis=1
).to_dict()
with filters[1]:
    player_id = st.selectbox("Search player", player_options, format_func=lambda value: labels.get(value, value))
family_rows = season_data[season_data["player_id"].astype(str).eq(player_id)]
families = family_rows["role_family"].dropna().unique().tolist()
with filters[2]:
    role_family = st.selectbox("Role family", families, format_func=ROLE_LABELS.get)

profile = player_profile(player_id, season, role_family)
if profile.empty:
    st.info("No player rows match the selected filters.")
    st.stop()
player = profile.iloc[-1]
end_week = int(profile["week"].max())
condition_box(
    f"{player['player_name']} ({player['team']}), {ROLE_LABELS[role_family]}, {season} regular season.",
    "All windows remain inside the selected season and end at the latest played week.",
    f"{profile['week'].nunique()} qualifying games through Week {end_week}.",
)

section("Weekly opportunity share", "All-play and normal-game shares are shown together.")
chart = profile[["week", "metric_all", "metric_normal"]].rename(
    columns={"week": "Week", "metric_all": "All-play share", "metric_normal": "Normal-game share"}
).set_index("Week")
st.line_chart(chart, color=["#0b5cff", "#8a9aae"], height=360, y_label="Share")
suspected = profile[profile["suspected_partial_game"]]
if not suspected.empty:
    note(
        "Suspected partial-game rows remain included and visible at Week "
        + ", ".join(suspected["week"].astype(int).astype(str).tolist())
        + ". Statistical usage alone is not treated as injury evidence.",
        amber=True,
    )

section("Window summary", "Raw opportunities and same-game team denominators are summed before shares are calculated.")
windows = player_window_table(profile, end_week)
for column in ["All share", "Normal share"]:
    windows[column] = windows[column].map(percent)
windows["Change vs prior"] = windows["Change vs prior"].map(pp)
table(windows, height=220)

if season >= 2023:
    section("Situational usage", "Play-level splits are available for 2023–2024.")
    situation = load_situational_data()
    situation = situation[
        situation["season"].eq(season) & situation["player_id"].astype(str).eq(player_id)
        & situation["role_family"].eq(role_family)
    ]
    if situation.empty:
        st.info("No situational opportunities are available for this player and family.")
    else:
        situ_summary = situation.groupby("context", as_index=False).agg(
            Raw=("raw_opportunities", "sum"), Denominator=("team_opportunities", "sum")
        )
        situ_summary["Share"] = (situ_summary["Raw"] / situ_summary["Denominator"].replace(0, pd.NA)).map(percent)
        situ_summary["Context"] = situ_summary["context"].str.replace("_", " ").str.title()
        table(situ_summary[["Context", "Raw", "Denominator", "Share"]], height=360)

section("Game log", "Opportunity facts with participation notes; production fields are available for 2023–2024.")
game_log = profile.copy()
game_log["Opponent"] = game_log.apply(lambda row: opponent_from_game_id(row["game_id"], row["team"]), axis=1)
game_log["All-play share"] = game_log["metric_all"].map(percent)
game_log["Normal-game share"] = game_log["metric_normal"].map(percent)
game_log = game_log.rename(columns={
    "week": "Week", "raw_opportunities_all": "All raw", "team_opportunities_all": "All denominator",
    "raw_opportunities_normal": "Normal raw", "team_opportunities_normal": "Normal denominator",
    "partial_game_note": "Participation note", "game_id": "Game ID",
})
production = load_production_data()
production = production[production["season"].eq(season) & production["player_id"].astype(str).eq(player_id)]
if not production.empty:
    game_log = game_log.merge(
        production[["game_id", "carries", "targets", "receptions", "rushing_yards", "receiving_yards"]].rename(columns={"game_id": "Game ID"}),
        on="Game ID", how="left",
    )
columns = ["Week", "Opponent", "All raw", "All denominator", "All-play share", "Normal raw", "Normal denominator", "Normal-game share"]
columns += [column for column in ["carries", "targets", "receptions", "rushing_yards", "receiving_yards"] if column in game_log]
columns += ["Participation note"]
table(game_log[columns], height=520)
source_footer("Player identity uses the canonical GSIS player ID and team-week join.")
