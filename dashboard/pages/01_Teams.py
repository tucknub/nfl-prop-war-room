from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import ROLE_LABELS, available_seasons, available_weeks, primary_rows, situational_team_summary, team_window_summary
from research_ui import (
    methodology_expander,
    note,
    numeric_percent,
    numeric_percent_sort,
    page_intro,
    ratio_text,
    role_noun,
    responsive_table,
    section,
    selection_summary,
    source_footer,
)


page_intro(
    "Team Opportunity Map",
    "See who accounted for a team’s carries, running-back opportunities, and targets.",
)

summary_slot = st.empty()
with st.expander("Change filters"):
    filters = st.columns(5)
    with filters[0]:
        season = st.selectbox("Season", available_seasons(), key="teams_season")
    season_rows = primary_rows()
    season_rows = season_rows[season_rows["season"].eq(season)]
    teams = sorted(season_rows["team"].dropna().astype(str).unique().tolist())
    with filters[1]:
        team = st.selectbox("Team", teams, key="teams_team")
    with filters[2]:
        window_label = st.selectbox("Window", ["Season", "Last 8", "Last 4", "Last 2"], index=2, key="teams_window")
    window = "Season" if window_label == "Season" else int(window_label.split()[-1])
    with filters[3]:
        context = st.selectbox("Context", ["All plays", "Normal game"], index=1, key="teams_context")
    with filters[4]:
        role_family = st.selectbox("Role family", list(ROLE_LABELS), format_func=ROLE_LABELS.get, key="teams_family")

end_week = max(available_weeks(season))
summary = team_window_summary(season, team, role_family, end_week, window, context)
situational = situational_team_summary(season, team, role_family, end_week, window) if season >= 2023 else pd.DataFrame()
if not situational.empty:
    summary = summary.merge(situational, on=["player_id", "player_name", "position"], how="left")

selection_summary(
    f"{team} · {season} · {window_label}",
    f"{context} · {ROLE_LABELS[role_family]}",
    f"Through Week {end_week} · {len(summary)} players",
    target=summary_slot,
)

view_mode = st.segmented_control(
    "Usage view",
    ["Role ownership", "Game script", "Scoring area"],
    default="Role ownership",
    label_visibility="collapsed",
    key="teams_view",
)

if season < 2023 and view_mode != "Role ownership":
    note("Situational views are available for completed 2023–2025 seasons.", amber=True)
    view_mode = "Role ownership"

context_groups = {
    "Game script": [
        ("early_down", "Early down"),
        ("passing_down", "Passing down"),
        ("two_minute", "Two minute"),
        ("short_yardage", "Short yardage"),
    ],
    "Scoring area": [
        ("red_zone", "Red zone"),
        ("inside_10", "Inside 10"),
        ("inside_5", "Inside 5"),
        ("end_zone", "End-zone targets"),
    ],
}

section(view_mode, f"{ROLE_LABELS[role_family]} · numeric sorting uses underlying percentage values.")
if summary.empty:
    st.info("No team rows match the selected filters.")
else:
    cards: list[dict[str, object]] = []
    if view_mode == "Role ownership":
        display = summary[[
            "player_name", "position", "share", "raw_opportunities", "team_denominator", "sample_games", "change"
        ]].rename(
            columns={
                "player_name": "Player", "position": "Position", "raw_opportunities": "Raw",
                "team_denominator": "Denominator", "sample_games": "Games",
            }
        )
        display = numeric_percent(display, "share", "Share")
        display = numeric_percent(display, "change", "Change")
        display = numeric_percent_sort(display, "Share")
        display = display[["Player", "Position", "Share", "Raw", "Denominator", "Games", "Change"]]
        for rank, (_, row) in enumerate(summary.iterrows(), start=1):
            cards.append(
                {
                    "rank": f"#{rank}",
                    "title": row["player_name"],
                    "subtitle": f"{team} · {row['position']}",
                    "metrics": [
                        (ROLE_LABELS[role_family], ratio_text(row["raw_opportunities"], row["team_denominator"], role_noun(role_family)), context),
                        ("Recent comparison", f"{row['change'] * 100:+.1f} pp" if pd.notna(row["change"]) else "—", f"{window_label} versus prior window", True),
                        ("Sample", f"{int(row['sample_games'])} games", "Qualifying games"),
                    ],
                    "href": f"/players?player={row['player_id']}&season={season}&family={role_family}",
                }
            )
        responsive_table(display, cards, key="teams_ownership", height=500, percent_columns=["Share", "Change"])
    else:
        contexts = [item for item in context_groups[view_mode] if item[0] in summary]
        table_columns = ["Player", "Position"]
        display = summary[["player_name", "position"]].rename(columns={"player_name": "Player", "position": "Position"}).copy()
        for source, label in contexts:
            display[f"{label} count"] = summary.apply(
                lambda row: f"{int(row[f'{source}_raw'])} / {int(row[f'{source}_denominator'])}"
                if pd.notna(row.get(f"{source}_raw")) and pd.notna(row.get(f"{source}_denominator")) else "—",
                axis=1,
            )
            display[f"{label} share"] = pd.to_numeric(summary[source], errors="coerce") * 100.0
            table_columns += [f"{label} count", f"{label} share"]
        sort_column = f"{contexts[0][1]} share" if contexts else None
        if sort_column:
            display = numeric_percent_sort(display, sort_column)
        for _, row in summary.iterrows():
            metrics = []
            for source, label in contexts:
                metrics.append(
                    (
                        label,
                        ratio_text(row.get(f"{source}_raw"), row.get(f"{source}_denominator"), role_noun(role_family)),
                        "Same-team, same-window denominator",
                    )
                )
            cards.append(
                {
                    "title": row["player_name"],
                    "subtitle": f"{team} · {row['position']}",
                    "metrics": metrics,
                    "href": f"/players?player={row['player_id']}&season={season}&family={role_family}",
                }
            )
        percent_columns = [column for column in table_columns if column.endswith(" share")]
        responsive_table(display[table_columns], cards, key=f"teams_{view_mode.lower().replace(' ', '_')}", height=520, percent_columns=percent_columns)

methodology_expander(
    [
        "Every percentage is shown with its player count and matching team denominator.",
        "Window shares sum raw opportunities and team opportunities before division.",
        "Normal game excludes defined abnormal game contexts; all plays retains them.",
        "Sorting uses numeric percentage columns, not formatted text.",
    ]
)
source_footer("Shares describe historical opportunity ownership, not future depth-chart status.")
