from __future__ import annotations

import pandas as pd
import streamlit as st

from launch_contract import (
    ALL_PLAY_AUTHORITY_NOTICE,
    REPORT_DEFINITIONS,
    REPORT_FAMILIES,
    REPORT_METHODS,
    REPORT_ORDER,
)
from research_data import (
    available_seasons,
    available_weeks,
    league_window_summary,
    operational_status_text,
)
from research_ui import (
    methodology_expander,
    page_intro,
    ratio_text,
    responsive_table,
    role_noun,
    section,
    selection_summary,
    source_footer,
)

# Legacy audit note: High-Value Opportunities was merged into Scoring-Area Usage before launch scope was narrowed.


def _whole(value: object) -> int:
    return 0 if pd.isna(value) else int(float(value))


def _report_rows(
    report: str,
    season: int,
    end_week: int,
    window: int | str,
    minimum_sample: int,
    sort_by: str,
) -> pd.DataFrame:
    families = list(REPORT_FAMILIES[report])
    all_play = league_window_summary(season, end_week, window, "All plays", families)
    if all_play.empty:
        return all_play

    rows = all_play[
        pd.to_numeric(all_play["raw_opportunities"], errors="coerce").ge(minimum_sample)
    ].copy()
    normal = league_window_summary(season, end_week, window, "Normal game", families)
    if normal.empty:
        rows["normal_raw"] = pd.NA
        rows["normal_denominator"] = pd.NA
        rows["normal_share"] = pd.NA
    else:
        normal = normal[
            [
                "player_id",
                "team",
                "role_family",
                "raw_opportunities",
                "team_denominator",
                "share",
            ]
        ].rename(
            columns={
                "raw_opportunities": "normal_raw",
                "team_denominator": "normal_denominator",
                "share": "normal_share",
            }
        )
        rows = rows.merge(normal, on=["player_id", "team", "role_family"], how="left")

    if report == "Role Movement":
        rows = rows[rows["change"].notna()].copy()
        rows["absolute_change"] = pd.to_numeric(rows["change"], errors="coerce").abs()

    sort_columns = {
        "Share": ["share", "raw_opportunities", "player_name"],
        "Raw opportunities": ["raw_opportunities", "share", "player_name"],
        "Absolute change": ["absolute_change", "raw_opportunities", "player_name"],
    }
    columns = sort_columns[sort_by]
    ascending = [False, False, True]
    return rows.sort_values(columns, ascending=ascending).reset_index(drop=True)


def _answer(report: str, row: pd.Series) -> str:
    player = str(row["player_name"])
    team = str(row["team"])
    family = str(row["role_family"])
    raw = _whole(row["raw_opportunities"])
    denominator = _whole(row["team_denominator"])
    share = float(row["share"])
    if report == "Role Movement":
        change = float(row["change"])
        direction = "gained" if change >= 0 else "lost"
        return (
            f"{player} {direction} {abs(change) * 100:.1f} percentage points of "
            f"{role_noun(family)} for {team}. Current all-play ownership is "
            f"{raw}/{denominator} ({share:.1%})."
        )
    return (
        f"{player} controls {raw}/{denominator} {role_noun(family)} for {team} "
        f"({share:.1%} all-play share)."
    )


def _render_answers(report: str, rows: pd.DataFrame, season: int, end_week: int) -> None:
    section("Answer first", "The leading descriptive findings with their raw evidence.")
    for rank, (_, row) in enumerate(rows.head(3).iterrows(), 1):
        with st.container(border=True):
            st.markdown(f"**{rank}. {_answer(report, row)}**")
            all_play = ratio_text(
                row["raw_opportunities"],
                row["team_denominator"],
                role_noun(str(row["role_family"])),
            )
            normal = "Normal-game context unavailable"
            if pd.notna(row.get("normal_share")):
                normal = (
                    f"Normal game: {_whole(row.get('normal_raw'))}/"
                    f"{_whole(row.get('normal_denominator'))} "
                    f"({float(row['normal_share']):.1%})"
                )
            st.caption(f"All-play evidence: {all_play} · {normal}")
            links = st.columns(2)
            with links[0]:
                st.link_button(
                    "Player evidence",
                    f"/players?player={row['player_id']}&season={season}&family={row['role_family']}&week={end_week}",
                    use_container_width=True,
                )
            with links[1]:
                st.link_button(
                    "Team evidence",
                    f"/teams?team={row['team']}&season={season}&family={row['role_family']}&week={end_week}",
                    use_container_width=True,
                )


def _render_table(report: str, rows: pd.DataFrame, season: int, end_week: int) -> None:
    section(
        "Complete report",
        "Every percentage remains attached to its player count and same-team denominator.",
    )
    display = rows.copy()
    display["All-play share"] = pd.to_numeric(display["share"], errors="coerce") * 100
    display["Normal-game share"] = pd.to_numeric(display["normal_share"], errors="coerce") * 100
    if report == "Role Movement":
        display["Change"] = pd.to_numeric(display["change"], errors="coerce") * 100
    display = display.rename(
        columns={
            "player_name": "Player",
            "team": "Team",
            "position": "Position",
            "role_family_label": "Role family",
            "raw_opportunities": "All-play raw",
            "team_denominator": "All-play denominator",
            "normal_raw": "Normal-game raw",
            "normal_denominator": "Normal-game denominator",
            "sample_games": "Games",
        }
    )
    columns = [
        "Player",
        "Team",
        "Position",
        "Role family",
        "All-play raw",
        "All-play denominator",
        "All-play share",
        "Normal-game raw",
        "Normal-game denominator",
        "Normal-game share",
        "Games",
    ]
    if report == "Role Movement":
        columns.insert(7, "Change")

    cards: list[dict[str, object]] = []
    for rank, (_, row) in enumerate(rows.head(12).iterrows(), 1):
        metrics: list[tuple[object, ...]] = [
            (
                "All-play authority",
                ratio_text(
                    row["raw_opportunities"],
                    row["team_denominator"],
                    role_noun(str(row["role_family"])),
                ),
                f"{float(row['share']):.1%} share",
            )
        ]
        if report == "Role Movement":
            metrics.append(
                (
                    "Prior comparison",
                    f"{float(row['change']) * 100:+.1f} pp",
                    "Current versus prior matching window",
                    True,
                )
            )
        if pd.notna(row.get("normal_share")):
            metrics.append(
                ("Supporting context", f"{float(row['normal_share']):.1%}", "Normal-game share")
            )
        cards.append(
            {
                "rank": f"#{rank}",
                "title": row["player_name"],
                "subtitle": f"{row['team']} · {row['position']} · {row['role_family_label']}",
                "metrics": metrics,
                "links": [
                    (
                        "Player Profile",
                        f"/players?player={row['player_id']}&season={season}&family={row['role_family']}&week={end_week}",
                    ),
                    (
                        "Team Breakdown",
                        f"/teams?team={row['team']}&season={season}&family={row['role_family']}&week={end_week}",
                    ),
                ],
            }
        )

    percent_columns = ["All-play share", "Normal-game share"]
    if report == "Role Movement":
        percent_columns.append("Change")
    responsive_table(
        display[columns],
        cards,
        key=f"launch_report_{report.lower().replace(' ', '_')}",
        height=650,
        percent_columns=percent_columns,
        label="Open complete report table",
    )


page_intro(
    "NFL Role Intelligence",
    "Three evidence-backed reports generated from documented offensive opportunities.",
)
st.info(ALL_PLAY_AUTHORITY_NOTICE)
st.caption(operational_status_text())

selected_report = st.segmented_control(
    "Report",
    list(REPORT_ORDER),
    default=REPORT_ORDER[0],
    key="reports_report",
)
if selected_report is None:
    selected_report = REPORT_ORDER[0]
st.markdown(f"## {selected_report}")
st.caption(REPORT_DEFINITIONS[selected_report])

sort_options = ["Share", "Raw opportunities"]
if selected_report == "Role Movement":
    sort_options.append("Absolute change")
if st.session_state.get("reports_sort") not in sort_options:
    st.session_state["reports_sort"] = sort_options[0]

with st.expander("Report controls", expanded=True):
    controls = st.columns(5)
    with controls[0]:
        season = int(st.selectbox("Season", available_seasons(), key="reports_season"))
    with controls[1]:
        period = st.selectbox(
            "Comparison window",
            ["Season", "Last 8", "Last 4", "Last 2"],
            index=2,
            key="reports_period",
        )
    with controls[2]:
        context = st.selectbox("Supporting context", ["Normal game"], key="reports_context")
    with controls[3]:
        minimum_sample = int(
            st.number_input(
                "Minimum all-play opportunities",
                min_value=1,
                max_value=100,
                value=8,
                key="reports_minimum",
            )
        )
    with controls[4]:
        sort_by = st.selectbox("Sort by", sort_options, key="reports_sort")

window: int | str = "Season" if period == "Season" else int(period.split()[-1])
end_week = max(available_weeks(season))
selection_summary(
    f"{selected_report} · {season} · {period}",
    f"All-play authority · {context} supporting context",
    f"Minimum {minimum_sample} all-play opportunities · Through Week {end_week}",
)

rows = _report_rows(selected_report, season, end_week, window, minimum_sample, sort_by)
if rows.empty:
    st.info("No rows match the selected period and sample requirement.")
else:
    _render_answers(selected_report, rows, season, end_week)
    _render_table(selected_report, rows, season, end_week)

methodology_expander(list(REPORT_METHODS[selected_report]))
source_footer(operational_status_text())
