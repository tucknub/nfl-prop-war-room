from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import (
    ROLE_LABELS,
    available_seasons,
    available_weeks,
    league_situational_summary,
    league_window_summary,
    load_production_data,
    percent,
    pp,
)
from research_ui import condition_box, inject_styles, note, page_intro, section, source_footer, table


REPORTS = [
    "Red Zone Usage", "Backfield Usage", "Target Share", "Recent Risers / Fallers",
    "Opportunity vs Production", "Game-Script Usage", "High-Value Opportunities",
]


inject_styles()
page_intro(
    "Usage Reports",
    "Focused, sortable views of opportunity ownership with explicit periods, denominators, and sample sizes.",
)
report = st.radio("Report", REPORTS, horizontal=True, label_visibility="collapsed")
controls = st.columns([1, 1, 1.1, 1])
with controls[0]:
    season = st.selectbox("Season", available_seasons())
with controls[1]:
    period = st.selectbox("Period", ["Season", "Last 8", "Last 4", "Last 2"], index=2)
window = "Season" if period == "Season" else int(period.split()[-1])
with controls[2]:
    context = st.selectbox("Context", ["All plays", "Normal game"], index=1)
with controls[3]:
    minimum_sample = st.number_input("Minimum opportunities", min_value=1, max_value=100, value=8)
end_week = max(available_weeks(season))

families = list(ROLE_LABELS)
situational_context = None
if report == "Backfield Usage":
    families = ["rb_carry_share", "rb_opportunity_share"]
elif report == "Target Share":
    families = ["wr_target_share", "te_target_share"]
elif report == "Red Zone Usage":
    situational_context = "red_zone"
elif report == "Game-Script Usage":
    situational_context = st.selectbox("Game-state slice", ["leading", "trailing", "close"])
elif report == "High-Value Opportunities":
    situational_context = st.selectbox("Field-position slice", ["inside_10", "inside_5", "end_zone"])

if situational_context and season < 2023:
    note("This focused report requires the 2023–2024 situational extract. Choose 2023 or 2024.", amber=True)
    result = pd.DataFrame()
elif situational_context:
    result = league_situational_summary(season, end_week, window, situational_context, families)
else:
    result = league_window_summary(season, end_week, window, context, families)

if report == "Recent Risers / Fallers" and not result.empty:
    result = result.assign(_magnitude=result["change"].abs()).sort_values("_magnitude", ascending=False)
if report == "Opportunity vs Production" and not result.empty:
    production = load_production_data()
    production = production[production["season"].eq(season) & production["week"].le(end_week)]
    if window != "Season":
        weeks = sorted(production["week"].unique().tolist())[-int(window):]
        production = production[production["week"].isin(weeks)]
    produced = production.groupby("player_id", as_index=False).agg(
        Receptions=("receptions", "sum"), Rushing_yards=("rushing_yards", "sum"), Receiving_yards=("receiving_yards", "sum")
    )
    result = result.merge(produced, on="player_id", how="left")

result = result[result["raw_opportunities"].ge(minimum_sample)] if not result.empty else result
condition_box(
    f"{report}; {season} through Week {end_week}; {period}; {context}.",
    "Share equals player opportunities divided by the matching same-team, same-game opportunity denominator.",
    f"Minimum {minimum_sample} player opportunities; {len(result)} rows shown.",
)
section(report)
if result.empty:
    st.info("No rows match this report and sample requirement.")
else:
    view = result.copy()
    view["Share"] = view["share"].map(percent)
    if "change" in view:
        view["Change"] = view["change"].map(pp)
    view = view.rename(columns={
        "player_name": "Player", "team": "Team", "position": "Position", "role_family_label": "Role family",
        "raw_opportunities": "Raw opportunities", "team_denominator": "Team denominator", "sample_games": "Sample games",
    })
    columns = ["Player", "Team", "Position", "Role family", "Share", "Raw opportunities", "Team denominator", "Sample games"]
    columns += [column for column in ["Change", "Receptions", "Rushing_yards", "Receiving_yards"] if column in view]
    table(view[columns], height=620)
source_footer("Report sorting is descriptive only.")
