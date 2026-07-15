from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import ROLE_LABELS, available_seasons, available_weeks, league_situational_summary, league_window_summary, load_production_data
from research_ui import methodology_expander, note, numeric_percent_sort, page_intro, ratio_text, responsive_table, role_noun, section, selection_summary, source_footer


REPORTS = [
    "Red Zone Usage",
    "Backfield Usage",
    "Target Share",
    "Recent Usage Risers and Fallers",
    "Opportunity Versus Production",
    "Game-Script Usage",
    "High-Value Opportunities",
]


def _whole(value: object) -> int:
    return 0 if pd.isna(value) else int(float(value))


page_intro(
    "Usage Reports",
    "Focused historical views with player counts, team denominators, and qualifying-game samples.",
)
report = st.selectbox("Report", REPORTS, key="reports_report")
summary_slot = st.empty()
with st.expander("Change filters"):
    controls = st.columns(5)
    with controls[0]:
        season = st.selectbox("Season", available_seasons(), key="reports_season")
    with controls[1]:
        period = st.selectbox("Period", ["Season", "Last 8", "Last 4", "Last 2"], index=2, key="reports_period")
    window = "Season" if period == "Season" else int(period.split()[-1])
    with controls[2]:
        context = st.selectbox("Context", ["All plays", "Normal game"], index=1, key="reports_context")
    with controls[3]:
        minimum_sample = st.number_input("Minimum opportunities", min_value=1, max_value=100, value=8, key="reports_minimum")
    sort_options = ["Share", "Raw opportunities"]
    if report == "Recent Usage Risers and Fallers":
        sort_options.insert(0, "Absolute change")
    with controls[4]:
        sort_by = st.selectbox("Sort by", sort_options, key="reports_sort")

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
    with st.expander("Choose game-script slice"):
        situational_context = st.selectbox("Game-script slice", ["leading", "trailing", "close"], key="reports_game_script")
elif report == "High-Value Opportunities":
    with st.expander("Choose scoring-area slice"):
        situational_context = st.selectbox("Scoring-area slice", ["inside_10", "inside_5", "end_zone"], key="reports_scoring")

if situational_context and season < 2023:
    note("This report is available for completed 2023–2025 seasons.", amber=True)
    result = pd.DataFrame()
elif situational_context:
    result = league_situational_summary(
        season, end_week, window, situational_context, families, overall_context=context
    )
else:
    result = league_window_summary(season, end_week, window, context, families)

if report == "Opportunity Versus Production" and not result.empty:
    production = load_production_data()
    production = production[production["season"].eq(season) & production["week"].le(end_week)]
    if window != "Season":
        selected_weeks = sorted(production["week"].unique().tolist())[-int(window):]
        production = production[production["week"].isin(selected_weeks)]
    produced = production.groupby("player_id", as_index=False).agg(
        Receptions=("receptions", "sum"),
        Rushing_yards=("rushing_yards", "sum"),
        Receiving_yards=("receiving_yards", "sum"),
    )
    result = result.merge(produced, on="player_id", how="left")

if not result.empty:
    result = result[result["raw_opportunities"].ge(minimum_sample)].copy()
    if sort_by == "Absolute change" and "change" in result:
        result["_sort"] = result["change"].abs()
        result = numeric_percent_sort(result, "_sort")
    elif sort_by == "Raw opportunities":
        result = numeric_percent_sort(result, "raw_opportunities")
    else:
        result = numeric_percent_sort(result, "share")

selection_summary(
    f"{report} · {season} · {period}",
    f"{context}{f' · {situational_context.replace('_', ' ')}' if situational_context else ''}",
    f"Minimum {minimum_sample} opportunities · {len(result)} rows",
    target=summary_slot,
)
section("Top results", f"Sorted by {sort_by.lower()}.")
if result.empty:
    st.info("No rows match this report and sample requirement.")
else:
    cards: list[dict[str, object]] = []
    for rank, (_, row) in enumerate(result.head(12).iterrows(), start=1):
        metrics: list[tuple[str, str, str] | tuple[str, str, str, bool]] = [
            ("Opportunity share", ratio_text(row["raw_opportunities"], row["team_denominator"], role_noun(str(row["role_family"]))), context),
            ("Sample", f"{int(row['sample_games'])} games", f"{period} through Week {end_week}"),
        ]
        if "change" in row and pd.notna(row["change"]):
            metrics.append(("Prior comparison", f"{row['change'] * 100:+.1f} pp", "Current window versus prior window", True))
        if report == "Opportunity Versus Production":
            metrics.append(
                (
                    "Production",
                    f"{_whole(row.get('Receptions'))} receptions",
                    f"{_whole(row.get('Rushing_yards'))} rush yds · {_whole(row.get('Receiving_yards'))} rec yds",
                )
            )
        cards.append(
            {
                "rank": f"#{rank}",
                "title": row["player_name"],
                "subtitle": f"{row['team']} · {row['position']} · {row['role_family_label']}",
                "metrics": metrics,
                "href": f"/players?player={row['player_id']}&season={season}&family={row['role_family']}",
            }
        )
    display = result.copy()
    display["Share"] = display["share"] * 100.0
    if "change" in display:
        display["Change"] = display["change"] * 100.0
    display = display.rename(
        columns={
            "player_name": "Player", "team": "Team", "position": "Position", "role_family_label": "Role family",
            "raw_opportunities": "Raw", "team_denominator": "Denominator", "sample_games": "Games",
        }
    )
    columns = ["Player", "Team", "Position", "Role family", "Share", "Raw", "Denominator", "Games"]
    columns += [column for column in ["Change", "Receptions", "Rushing_yards", "Receiving_yards"] if column in display]
    responsive_table(
        display[columns],
        cards,
        key="reports_results",
        height=620,
        percent_columns=[column for column in ["Share", "Change"] if column in display],
    )

methodology_expander(
    [
        "Every share is player opportunities divided by the matching same-team denominator.",
        "Window summaries add raw player and team counts before calculating the percentage.",
        "Minimum opportunities filters the displayed sample after the requested report is constructed.",
        "Report ordering is descriptive historical sorting.",
    ]
)
source_footer("Report ordering is descriptive only.")
