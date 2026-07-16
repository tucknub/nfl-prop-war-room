from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from research_data import (
    ROLE_LABELS, available_seasons, load_production_data, load_situational_data,
    opponent_from_game_id, player_profile, player_selector_rows, player_window_table,
    primary_rows, team_window_summary,
)
from research_ui import (
    enable_browser_history_sync, initialize_query_control, kpi_row, methodology_expander,
    nfl_week_axis_values, note, page_intro, parse_int, query_value, ratio_text,
    responsive_table, role_noun, searchable_selectbox, section, selection_summary,
    source_footer, update_query_from_widget,
)
from supporting_evidence import home_evidence_message, player_role_sentence, role_fingerprint_contexts


def _whole(value: object) -> int:
    return 0 if pd.isna(value) else int(float(value))


enable_browser_history_sync()
page_intro("Player Role Profile", "What role does this player currently have, and how has it changed?")
summary_slot = st.empty()
seasons = available_seasons()
season_state = initialize_query_control("players", "season", "players_season", seasons, parser=parse_int)
with st.expander("Change season"):
    season = st.selectbox("Season", seasons, key="players_season", on_change=update_query_from_widget, args=("season", "players_season"), kwargs={"clear_query": ("player", "family", "week")})

data = primary_rows()
season_data = data[data["season"].eq(season)]
week_text = query_value("week")
requested_week = int(week_text) if week_text.isdigit() else None
season_weeks = sorted(season_data["week"].dropna().astype(int).unique().tolist())
if requested_week is not None and requested_week not in season_weeks:
    st.warning(f"Week not found for {season}: {week_text}")
    st.stop()
selector_week = requested_week if requested_week is not None else max(season_weeks)
players = player_selector_rows(season_data, selector_week)
player_options = players["player_id"].astype(str).tolist()
labels = players.set_index(players["player_id"].astype(str)).apply(lambda row: f"{row['player_name']} · {row['team']} · {row['position']}", axis=1).to_dict()
player_state = initialize_query_control("players", "player", "players_player", player_options)
selector_cols = st.columns([2.2, 1.2])
with selector_cols[0]:
    player_id = searchable_selectbox("Search or select player", player_options, format_func=lambda value: labels.get(value, value), key="players_player", on_change=update_query_from_widget, args=("player", "players_player"), kwargs={"clear_query": ("family",)})
family_rows = season_data[season_data["player_id"].astype(str).eq(player_id)]
families = family_rows["role_family"].dropna().astype(str).unique().tolist()
family_state = initialize_query_control("players", "family", "players_family", families)
with selector_cols[1]:
    role_family = st.selectbox("Role family", families, format_func=ROLE_LABELS.get, key="players_family", on_change=update_query_from_widget, args=("family", "players_family"))
if season_state.invalid_query or player_state.invalid_query or family_state.invalid_query:
    if season_state.invalid_query: st.warning("The requested season was not found.")
    if player_state.invalid_query: st.warning("Player not found. Search for and select a valid player.")
    if family_state.invalid_query: st.warning("The requested role family is unavailable for this player.")
    st.stop()

profile = player_profile(player_id, season, role_family)
if requested_week is not None:
    profile = profile[profile["week"].le(requested_week)].copy()
if profile.empty:
    st.info("No player rows match the selected filters.")
    st.stop()
player = profile.iloc[-1]
end_week = requested_week if requested_week is not None else int(profile["week"].max())
selection_summary(f"{player['player_name']} · {player['team']} · {player['position']}", f"{season} · {ROLE_LABELS[role_family]}", f"{profile['week'].nunique()} qualifying games through Week {end_week}", target=summary_slot)

if (
    query_value("origin") == "home"
    and query_value("focus") == player_id
    and query_value("focus_family") == role_family
):
    origin_message = home_evidence_message(
        season, end_week, player_id, role_family, team=str(player["team"])
    )
    if origin_message:
        note(origin_message)

windows = player_window_table(profile, end_week)
window_index = windows.set_index("Window")
team_rank_rows = team_window_summary(season, str(player["team"]), role_family, end_week, "Season", "Normal game")
rank_positions = team_rank_rows.reset_index().loc[team_rank_rows.reset_index()["player_id"].astype(str).eq(player_id), "index"]
role_rank = int(rank_positions.iloc[0]) + 1 if not rank_positions.empty else 0
st.info(player_role_sentence(
    str(player["player_name"]), str(player["team"]), str(player["position"]), ROLE_LABELS[role_family],
    role_rank, len(team_rank_rows), float(window_index.loc["Season", "Normal share"]),
    float(window_index.loc["Last 4", "Normal share"]), int(window_index.loc["Last 4", "Games"]),
))

def _window_detail(label: str) -> str:
    row = window_index.loc[label]
    games = int(row["Games"])
    nominal = None if label == "Season" else int(label.split()[-1])
    suffix = f" · fewer than {nominal}" if nominal and games < nominal else ""
    return f"{int(row['Normal raw'])} / {int(row['Normal denominator'])} · {games} games{suffix}"

kpi_row([(label, f"{window_index.loc[label, 'Normal share']:.1%}", _window_detail(label)) for label in ["Season", "Last 8", "Last 4", "Last 2"]])
suspected_weeks = profile.loc[profile["suspected_partial_game"], "week"].astype(int).tolist()
kpi_items = [
    ("Normal-game count", f"{int(profile['raw_opportunities_normal'].sum())} / {int(profile['team_opportunities_normal'].sum())}", "Player / team opportunities"),
    ("Team role rank", f"{role_rank} of {len(team_rank_rows)}", ROLE_LABELS[role_family]),
    ("Qualifying games", str(profile["week"].nunique()), f"Through Week {end_week}"),
]
if suspected_weeks:
    kpi_items.append(("Participation", "Suspected", "Weeks " + ", ".join(map(str, suspected_weeks)) + " remain included"))
kpi_row(kpi_items)

section("Weekly opportunity", "Normal game and all plays remain separate; hover for counts.")
chart_mode = st.segmented_control("Chart measure", ["Share", "Raw opportunities", "Team denominator"], default="Share", label_visibility="collapsed", key="players_chart_measure")
if chart_mode == "Share":
    chart_data = profile[["week", "metric_all", "metric_normal", "raw_opportunities_all", "team_opportunities_all", "raw_opportunities_normal", "team_opportunities_normal"]].melt(
        id_vars=["week", "raw_opportunities_all", "team_opportunities_all", "raw_opportunities_normal", "team_opportunities_normal"], value_vars=["metric_all", "metric_normal"], var_name="series", value_name="value"
    )
    chart_data["Series"] = chart_data["series"].map({"metric_all": "All plays", "metric_normal": "Normal game"})
    chart_data["Raw"] = chart_data.apply(lambda row: row["raw_opportunities_all"] if row["series"] == "metric_all" else row["raw_opportunities_normal"], axis=1)
    chart_data["Denominator"] = chart_data.apply(lambda row: row["team_opportunities_all"] if row["series"] == "metric_all" else row["team_opportunities_normal"], axis=1)
    y = alt.Y("value:Q", title="Share", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1]))
else:
    source = "raw_opportunities_all" if chart_mode == "Raw opportunities" else "team_opportunities_all"
    chart_data = profile[["week", "raw_opportunities_all", "team_opportunities_all"]].copy()
    chart_data["value"] = chart_data[source]
    chart_data = chart_data.rename(columns={"raw_opportunities_all": "Raw", "team_opportunities_all": "Denominator"})
    chart_data["Series"] = chart_mode
    y = alt.Y("value:Q", title=chart_mode)
chart_data = chart_data.rename(columns={"week": "Week"}).dropna(subset=["Week", "value"])
if chart_data["Week"].nunique() < 2:
    st.info("Fewer than two qualifying weekly points are available; no trend line is shown.")
else:
    chart = alt.Chart(chart_data).mark_line(point=alt.OverlayMarkDef(size=48), strokeWidth=2.2).encode(
        x=alt.X("Week:Q", scale=alt.Scale(domain=[1, 18]), axis=alt.Axis(values=nfl_week_axis_values(), tickMinStep=1, title="NFL week")),
        y=y, color=alt.Color("Series:N", legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("Week:Q", format=".0f"), "Series:N", alt.Tooltip("value:Q", format=".1%" if chart_mode == "Share" else ".0f"), alt.Tooltip("Raw:Q", format=".0f"), alt.Tooltip("Denominator:Q", format=".0f")],
    ).properties(height=245)
    st.altair_chart(chart, width="stretch")

profile_weeks = set(profile["week"].dropna().astype(int))
bye_weeks, missing_weeks = [], []
assignments = profile[["week", "team"]].drop_duplicates().sort_values("week")
for week in range(1, end_week + 1):
    if week in profile_weeks:
        continue
    prior_assignment = assignments[assignments["week"].le(week)]
    assigned_team = str(prior_assignment.iloc[-1]["team"] if not prior_assignment.empty else assignments.iloc[0]["team"])
    team_played = bool((season_data["team"].eq(assigned_team) & season_data["week"].eq(week)).any())
    (missing_weeks if team_played else bye_weeks).append(week)
status = []
if bye_weeks: status.append("Bye: " + ", ".join(map(str, bye_weeks)))
if missing_weeks: status.append("Team played; no qualifying player row: " + ", ".join(map(str, missing_weeks)))
if status: note(" · ".join(status))

if season >= 2023:
    section("Role fingerprint", "Up to six useful contexts that describe the player's assignment.")
    situation = load_situational_data()
    situation = situation[(situation["season"].eq(season)) & (situation["week"].le(end_week)) & situation["player_id"].astype(str).eq(player_id) & situation["role_family"].eq(role_family)]
    situation = situation[situation["context"].isin(role_fingerprint_contexts(role_family))]
    situ = situation.groupby("context", as_index=False).agg(Raw=("raw_opportunities", "sum"), Denominator=("team_opportunities", "sum"), Games=("game_id", "nunique")) if not situation.empty else pd.DataFrame()
    if not situ.empty:
        situ = situ[situ["Denominator"].gt(0)].copy()
        situ["Share"] = situ["Raw"] / situ["Denominator"] * 100
        situ["Context"] = situ["context"].str.replace("_", " ").str.title()
        cards = [{"title": row["Context"], "subtitle": f"{int(row['Games'])} qualifying games", "metrics": [("Ownership", ratio_text(row["Raw"], row["Denominator"], role_noun(role_family)), "Player / same-team opportunities")]} for _, row in situ.iterrows()]
        responsive_table(situ[["Context", "Raw", "Denominator", "Share", "Games"]], cards, key="player_situational", height=360, percent_columns=["Share"])
    else:
        st.info("No valid situational denominators are available for this player.")

section("Team comparison", "Who shares this same team opportunity?")
peer_cards = [{"rank": f"#{rank}", "title": row["player_name"], "subtitle": f"{player['team']} · {row['position']}", "metrics": [("Season ownership", ratio_text(row["raw_opportunities"], row["team_denominator"], role_noun(role_family)), "Normal game")], "href": f"/players?player={row['player_id']}&season={season}&family={role_family}&week={end_week}"} for rank, (_, row) in enumerate(team_rank_rows.head(6).iterrows(), 1)]
peer_table = team_rank_rows.head(10).copy()
peer_table["Share"] = peer_table["share"] * 100
peer_table = peer_table.rename(columns={"player_name": "Player", "position": "Position", "raw_opportunities": "Raw", "team_denominator": "Denominator", "sample_games": "Games"})
responsive_table(peer_table[["Player", "Position", "Raw", "Denominator", "Share", "Games"]], peer_cards, key="player_peers", height=360, percent_columns=["Share"])

section("Weekly counts", "Each row retains its game-week team assignment.")
game_log = profile.copy()
game_log["Opponent"] = game_log.apply(lambda row: opponent_from_game_id(row["game_id"], row["team"]), axis=1)
production = load_production_data()
production = production[production["season"].eq(season) & production["player_id"].astype(str).eq(player_id)]
if not production.empty:
    game_log = game_log.merge(production[["game_id", "carries", "targets", "receptions", "rushing_yards", "receiving_yards"]], on="game_id", how="left")
cards = []
for _, row in game_log.sort_values("week", ascending=False).iterrows():
    participation = str(row["partial_game_note"])
    cards.append({"rank": f"Week {int(row['week'])}", "title": f"{row['team']} vs {row['Opponent']}", "subtitle": participation if "Suspected" in participation else f"{row['team']} segment", "metrics": [("All plays", ratio_text(row["raw_opportunities_all"], row["team_opportunities_all"], role_noun(role_family)), "Player / team"), ("Normal game", ratio_text(row["raw_opportunities_normal"], row["team_opportunities_normal"], role_noun(role_family)), "Player / team"), ("Production", f"{_whole(row.get('carries'))} carries · {_whole(row.get('targets'))} targets", f"{_whole(row.get('receptions'))} receptions")]})
display = game_log[["week", "team", "Opponent", "raw_opportunities_all", "team_opportunities_all", "metric_all", "raw_opportunities_normal", "team_opportunities_normal", "metric_normal", "partial_game_note"]].rename(columns={"week": "Week", "team": "Team", "raw_opportunities_all": "All raw", "team_opportunities_all": "All denominator", "metric_all": "All share", "raw_opportunities_normal": "Normal raw", "team_opportunities_normal": "Normal denominator", "metric_normal": "Normal share", "partial_game_note": "Participation"})
display["All share"] *= 100
display["Normal share"] *= 100
responsive_table(display, cards, key="player_weekly", height=520, percent_columns=["All share", "Normal share"])

team_history = profile[["week", "team"]].drop_duplicates().sort_values("week")
if team_history["team"].nunique() > 1:
    segments = ", ".join(f"{team_name} Weeks {group['week'].min()}–{group['week'].max()}" for team_name, group in team_history.groupby("team", sort=False))
    note(f"Team history: {segments}. The heading reflects the selected boundary; weekly rows retain game-week teams.")

methodology_expander([
    "Window shares sum player and matching team opportunities before division.",
    "Bye weeks are distinguished from weeks when the team played without a qualifying player row.",
    "Confirmed partial games remain excluded; suspected rows remain visible and included.",
])
source_footer("Canonical player identity and team-week attribution are preserved.")
