from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import (
    ROLE_LABELS,
    available_seasons,
    available_weeks,
    game_usage,
    percent,
    player_profile,
    primary_rows,
)
from research_ui import inject_styles, note, page_intro, section, source_footer, table


inject_styles()
page_intro(
    "Game Usage Box Scores",
    "One-game workload facts: carries, targets, receptions, role shares, context exclusions, and prior-game baselines.",
)

seasons = available_seasons()
controls = st.columns([1, 1, 2.5])
with controls[0]:
    season = st.selectbox("Season", seasons)
weeks = available_weeks(season)
with controls[1]:
    week = st.selectbox("Week", weeks, index=len(weeks) - 1)
rows = primary_rows()
week_rows = rows[rows["season"].eq(season) & rows["week"].eq(week)]
games = sorted(week_rows["game_id"].dropna().astype(str).unique().tolist())
with controls[2]:
    game_id = st.selectbox("Game", games)

usage = game_usage(season, week, game_id)
teams = sorted(usage["team"].dropna().astype(str).unique().tolist()) if not usage.empty else []
section("Usage detail", " vs ".join(teams) if len(teams) == 2 else game_id)
if season < 2023:
    note("Carry and target shares are available. Receptions and yardage fields begin in the committed 2023–2025 play-level extract.", amber=True)

for team in teams:
    st.markdown(f"### {team}")
    team_view = usage[usage["team"].eq(team)].copy()
    role_family = team_view["position"].map({"RB": "rb_opportunity_share", "WR": "wr_target_share", "TE": "te_target_share"})
    team_view["Role family"] = role_family.map(ROLE_LABELS)
    team_view["All-play share"] = team_view.apply(
        lambda row: percent(row.get(role_family.loc[row.name], pd.NA)), axis=1
    )
    team_view["Normal-game share"] = team_view.apply(
        lambda row: percent(row.get(f"{role_family.loc[row.name]}_normal", pd.NA)), axis=1
    )
    team_view["Context-excluded opportunities"] = "—"
    factual = []
    for _, row in team_view.iterrows():
        family = {"RB": "rb_opportunity_share", "WR": "wr_target_share", "TE": "te_target_share"}.get(row["position"])
        if not family:
            factual.append("—")
            continue
        history = player_profile(str(row["player_id"]), season, family)
        prior = history[history["week"].lt(week)].tail(4)
        denom = prior["team_opportunities_normal"].sum()
        baseline = prior["raw_opportunities_normal"].sum() / denom if denom else pd.NA
        factual.append(f"Prior {len(prior)}-game normal share: {percent(baseline)}")
    team_view["Prior baseline"] = factual
    base_columns = ["player_name", "position", "Role family"]
    production_columns = [column for column in ["carries", "targets", "receptions", "rushing_yards", "receiving_yards"] if column in team_view]
    display = team_view[base_columns + production_columns + ["All-play share", "Normal-game share", "Prior baseline", "partial_game_note"]].rename(
        columns={"player_name": "Player", "position": "Position", "partial_game_note": "Participation note"}
    )
    table(display, height=max(220, min(500, 42 * (len(display) + 1))))

source_footer("A high one-play share can reflect a small denominator; raw counts remain visible.")
