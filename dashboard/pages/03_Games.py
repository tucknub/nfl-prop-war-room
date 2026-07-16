from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from research_data import (
    ROLE_LABELS, available_seasons, available_weeks, game_usage, load_situational_data,
    player_profile, primary_rows,
)
from research_ui import (
    enable_browser_history_sync, initialize_query_control, methodology_expander, note,
    page_intro, parse_int, query_value, ratio_text, responsive_table, role_noun, searchable_selectbox,
    section, selection_summary, source_footer, update_query_from_widget,
)
from supporting_evidence import game_team_totals, home_evidence_message, matchup_from_game_id


def _whole(value: object) -> int:
    return 0 if pd.isna(value) else int(float(value))


def _game_label(game_id: object) -> str:
    # Search labels render the human matchup as "AWAY at HOME" before the technical ID.
    matchup, _, _ = matchup_from_game_id(game_id)
    return f"{matchup} · {game_id}"


enable_browser_history_sync()
page_intro("Game Usage Review", "What happened to each player’s role in this game?")
summary_slot = st.empty()
seasons = available_seasons()
season_state = initialize_query_control("games", "season", "games_season", seasons, parser=parse_int)
season = int(season_state.value)
weeks = available_weeks(season)
week_state = initialize_query_control("games", "week", "games_week", weeks, default=weeks[-1], parser=parse_int)
week = int(week_state.value)
week_rows = primary_rows()
week_rows = week_rows[week_rows["season"].eq(season) & week_rows["week"].eq(week)]
games = sorted(week_rows["game_id"].dropna().astype(str).unique().tolist())
game_state = initialize_query_control("games", "game", "games_game", games)
with st.expander("Change game"):
    controls = st.columns([1, 1, 2.5])
    with controls[0]:
        season = st.selectbox("Season", seasons, key="games_season", on_change=update_query_from_widget, args=("season", "games_season"), kwargs={"clear_query": ("week", "game")})
    with controls[1]:
        week = st.selectbox("Week", weeks, key="games_week", on_change=update_query_from_widget, args=("week", "games_week"), kwargs={"clear_query": ("game",)})
    with controls[2]:
        game_id = searchable_selectbox("Search or select game", games, key="games_game", format_func=_game_label, on_change=update_query_from_widget, args=("game", "games_game"))
if season_state.invalid_query or week_state.invalid_query or game_state.invalid_query:
    st.warning("The requested game, week, or season is unavailable.")
    st.stop()

usage = game_usage(season, week, game_id)
matchup, away, home = matchup_from_game_id(game_id)
teams = [team for team in [away, home] if team in set(usage["team"].astype(str))] if not usage.empty else []
selection_summary(matchup, f"Week {week} · {season} regular season", f"{len(usage)} player rows", target=summary_slot)
if query_value("origin") == "home":
    origin_message = home_evidence_message(
        season,
        week,
        query_value("focus"),
        query_value("focus_family"),
        game_id=game_id,
    )
    if origin_message:
        note(origin_message)
if season < 2023:
    note("Production and situational counts are available for completed 2023–2025 seasons.", amber=True)

situational = load_situational_data()
situational = situational[situational["season"].eq(season) & situational["week"].eq(week) & situational["game_id"].eq(game_id)]

section("Team opportunity totals", "All-play totals with their matching normal-game subsets.")
team_total_rows, team_total_cards = [], []
for team in teams:
    totals = game_team_totals(usage, team)
    outside_rb = max(0, totals["rb_opportunities"] - totals["normal_rb_opportunities"])
    outside_targets = max(0, totals["targets"] - totals["normal_targets"])
    team_total_rows.append({"Team": team, "Carries": totals["carries"], "RB opportunities": totals["rb_opportunities"], "Targets": totals["targets"], "Normal RB": totals["normal_rb_opportunities"], "Normal targets": totals["normal_targets"], "Outside normal": outside_rb + outside_targets})
    team_total_cards.append({"title": team, "subtitle": matchup, "metrics": [("Team carries", str(totals["carries"]), "All plays"), ("RB opportunities", f"{totals['normal_rb_opportunities']} normal / {totals['rb_opportunities']} all", f"{outside_rb} outside normal"), ("Targets", f"{totals['normal_targets']} normal / {totals['targets']} all", f"{outside_targets} outside normal")]})
responsive_table(pd.DataFrame(team_total_rows), team_total_cards, key="game_team_totals", height=220)

family_by_position = {"RB": "rb_opportunity_share", "WR": "wr_target_share", "TE": "te_target_share"}
for team in teams:
    team_usage = usage[usage["team"].eq(team)].copy()
    section(f"{team} leading roles", "Game-level opportunity leaders by role and scoring context.")
    leader_rows, leader_cards = [], []
    role_specs = [("Carry leader", "rb_carry_share", "RB"), ("RB opportunity leader", "rb_opportunity_share", "RB"), ("WR target leader", "wr_target_share", "WR"), ("TE target leader", "te_target_share", "TE")]
    for label, family, position in role_specs:
        eligible = team_usage[team_usage["position"].eq(position)].copy()
        raw_col, den_col = f"{family}_raw", f"{family}_denominator"
        if raw_col not in eligible or eligible.empty:
            continue
        eligible[raw_col] = pd.to_numeric(eligible[raw_col], errors="coerce")
        eligible[den_col] = pd.to_numeric(eligible[den_col], errors="coerce")
        eligible = eligible[eligible[den_col].gt(0)].sort_values([raw_col, "player_name"], ascending=[False, True])
        if eligible.empty:
            continue
        row = eligible.iloc[0]
        leader_rows.append({"Role": label, "Player": row["player_name"], "Count": _whole(row[raw_col]), "Denominator": _whole(row[den_col]), "Share": float(row[raw_col]) / float(row[den_col]) * 100})
        leader_cards.append({"title": label, "subtitle": f"{row['player_name']} · {position}", "metrics": [("Ownership", ratio_text(row[raw_col], row[den_col], role_noun(family)), "All plays")], "href": f"/players?player={row['player_id']}&season={season}&family={family}&week={week}"})
    for context, label in [("red_zone", "Red-zone opportunity leader"), ("inside_5", "Inside-five leader")]:
        context_rows = situational[situational["team"].eq(team) & situational["context"].eq(context) & situational["team_opportunities"].gt(0)].copy()
        if context_rows.empty:
            continue
        context_rows = context_rows.sort_values(["raw_opportunities", "player_name"], ascending=[False, True])
        row = context_rows.iloc[0]
        leader_rows.append({"Role": label, "Player": row["player_name"], "Count": _whole(row["raw_opportunities"]), "Denominator": _whole(row["team_opportunities"]), "Share": float(row["share"]) * 100})
        leader_cards.append({"title": label, "subtitle": f"{row['player_name']} · {row['position']}", "metrics": [("Ownership", ratio_text(row["raw_opportunities"], row["team_opportunities"]), context.replace("_", " ").title())], "href": f"/players?player={row['player_id']}&season={season}&family={row['role_family']}&week={week}"})
    responsive_table(pd.DataFrame(leader_rows), leader_cards, key=f"game_{team}_leaders", height=300, percent_columns=["Share"])

    section(f"{team} player usage", "Current game counts, context, and prior qualifying comparison.")
    cards, desktop_rows = [], []
    for _, row in team_usage.iterrows():
        family = family_by_position.get(str(row["position"]))
        if not family:
            continue
        raw, denominator = row.get(f"{family}_raw"), row.get(f"{family}_denominator")
        normal_raw, normal_denominator = row.get(f"{family}_normal_raw"), row.get(f"{family}_normal_denominator")
        if pd.isna(denominator) or float(denominator) <= 0:
            continue
        player_context = situational[situational["player_id"].astype(str).eq(str(row["player_id"])) & situational["role_family"].eq(family)].set_index("context")
        def context_values(context: str) -> tuple[int, int, float | None]:
            if context not in player_context.index:
                return 0, 0, None
            item = player_context.loc[context]
            if isinstance(item, pd.DataFrame): item = item.iloc[0]
            den = _whole(item["team_opportunities"])
            return _whole(item["raw_opportunities"]), den, float(item["share"]) if den else None
        history = player_profile(str(row["player_id"]), season, family)
        prior = history[history["week"].lt(week)].tail(4)
        prior_den = float(prior["team_opportunities_normal"].sum())
        prior_share = float(prior["raw_opportunities_normal"].sum() / prior_den) if prior_den else math.nan
        outside = max(0, _whole(raw) - _whole(normal_raw))
        red_raw, red_den, _ = context_values("red_zone")
        five_raw, five_den, _ = context_values("inside_5")
        change = float(normal_raw) / float(normal_denominator) - prior_share if pd.notna(normal_denominator) and normal_denominator and pd.notna(prior_share) else math.nan
        change_text = f"{change * 100:+.1f} pp" if pd.notna(change) else "No prior sample"
        cards.append({
            "title": row["player_name"], "subtitle": f"{team} · {row['position']} · {ROLE_LABELS[family]}",
            "metrics": [("All-play ownership", ratio_text(raw, denominator, role_noun(family)), "Game total"), ("Normal-game ownership", ratio_text(normal_raw, normal_denominator, role_noun(family)), f"{outside} outside normal context"), ("Prior comparison", change_text, f"Versus {len(prior)} earlier qualifying games"), ("Scoring area", f"{red_raw} / {red_den} red zone", f"{five_raw} / {five_den} inside five"), ("Production", f"{_whole(row.get('carries'))} carries · {_whole(row.get('targets'))} targets", f"{_whole(row.get('receptions'))} receptions")],
            "note": str(row["partial_game_note"]) if "Suspected" in str(row["partial_game_note"]) else "",
            "href": f"/players?player={row['player_id']}&season={season}&family={family}&week={week}",
        })
        desktop_rows.append({"Player": row["player_name"], "Pos": row["position"], "Family": ROLE_LABELS[family], "All count": f"{_whole(raw)} / {_whole(denominator)}", "All share": float(raw) / float(denominator) * 100, "Normal count": f"{_whole(normal_raw)} / {_whole(normal_denominator)}", "Normal share": float(normal_raw) / float(normal_denominator) * 100 if normal_denominator else pd.NA, "Change vs prior": change * 100 if pd.notna(change) else pd.NA, "Red zone": f"{red_raw} / {red_den}", "Inside five": f"{five_raw} / {five_den}", "Carries": _whole(row.get("carries")), "Targets": _whole(row.get("targets")), "Receptions": _whole(row.get("receptions"))})
    responsive_table(pd.DataFrame(desktop_rows), cards, key=f"game_{team}_players", height=520, percent_columns=["All share", "Normal share", "Change vs prior"])

with st.expander("Technical game details"):
    st.code(str(game_id))
    st.caption("Final score is omitted because it is not present in the committed validated public extract.")
    st.caption("Longest-play and one-play production concentration are omitted because the committed event extract has no yards-gained field.")

methodology_expander([
    "All-play and normal-game shares use player counts divided by matching team counts.",
    "Prior comparison uses up to four earlier qualifying games in the same season.",
    "Inside-five counts come from the committed play-level opportunity extract.",
])
source_footer("Unavailable score and longest-play fields are not inferred or fabricated.")
