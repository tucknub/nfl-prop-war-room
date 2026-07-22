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
from research_data import ROLE_LABELS, available_seasons, available_weeks, league_window_summary
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


def _safe_int(value: object) -> int:
    return 0 if pd.isna(value) else int(float(value))


def _load_report(
    report: str,
    season: int,
    end_week: int,
    window: int | str,
    minimum_sample: int,
) -> pd.DataFrame:
    families = list(REPORT_FAMILIES[report])
    all_play = league_window_summary(season, end_week, window, "All plays", families)
    if all_play.empty:
        return all_play

    result = all_play.copy()
    result = result[pd.to_numeric(result["raw_opportunities"], errors="coerce").ge(minimum_sample)]

    normal = league_window_summary(season, end_week, window, "Normal game", families)
    if not normal.empty:
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
        result = result.merge(normal, on=["player_id", "team", "role_family"], how="left")
    else:
        result["normal_raw"] = pd.NA
        result["normal_denominator"] = pd.NA
        result["normal_share"] = pd.NA

    if report == "Role Movement":
        result = result[result["change"].notna()].copy()
        result["absolute_change"] = pd.to_numeric(result["change"], errors="coerce").abs()
        result = result.sort_values(
            ["absolute_change", "raw_opportunities", "player_name"],
            ascending=[False, False, True],
        )
    else:
        result = result.sort_values(
            ["share", "raw_opportunities", "player_name"],
            ascending=[False, False, True],
        )

    return result.reset_index(drop=True)


def _answer_text(report: str, row: pd.Series) -> str:
    player = str(row["player_name"])
    team = str(row["team"])
    family = str(row["role_family"])
    raw = _safe_int(row["raw_opportunities"])
    denominator = _safe_int(row["team_denominator"])
    share = float(row["share"])

    if report == "Role Movement":
        change = float(row["change"])
        direction = "gained" if change >= 0 else "lost"
        return (
            f"{player} {direction} {abs(change) * 100:.1f} percentage points of "
            f"{role_noun(family)} for {team}. Current all-play ownership: "
            f"{raw}/{denominator} ({share:.1%})."
        )

    return (
        f"{player} controls {raw}/{denominator} {role_noun(family)} for {team} "
        f"({share:.1%} all-play share)."
    )


def _render_report(report: str, result: pd.DataFrame, season: int, end_week: int, period: str) -> None:
    st.markdown(f"### {report}")
    st.caption(REPORT_DEFINITIONS[report])

    if result.empty:
        st.info("No rows match the selected period and sample requirement.")
        return

    section("Answer first", "The highest-priority descriptive findings, with raw evidence attached.")
    for rank, (_, row) in enumerate(result.head(3).iterrows(), 1):
        with st.container(border=True):
            st.markdown(f"**{rank}. {_answer_text(report, row)}**")
            evidence = ratio_text(
                row["raw_opportunities"],
                row["team_denominator"],
                role_noun(str(row["role_family"])),
            )
            supporting = "Normal-game context unavailable"
            if pd.notna(row.get("normal_share")):
                supporting = (
                    f"Normal game: {_safe_int(row.get('normal_raw'))}/"
                    f"{_safe_int(row.get('normal_denominator'))} "
                    f"({float(row['normal_share']):.1%})"
                )
            st.caption(f"All-play evidence: {evidence} · {supporting}")
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

    section("Complete report", "Every displayed percentage remains tied to its raw player count and same-team denominator.")
    display = result.copy()
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
    for rank, (_, row) in enumerate(result.head(12).iterrows(), 1):
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
                    "Current window versus prior matching window",
                    True,
                )
            )
        if pd.notna(row.get("normal_share")):
            metrics.append(
                (
                    "Supporting context",
                    f"{float(row['normal_share']):.1%}",
                    "Normal-game share",
                )
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

    methodology_expander(list(REPORT_METHODS[report]))


page_intro(
    "NFL Role Intelligence",
    "Three evidence-backed reports generated from documented offensive opportunities.",
)
st.info(ALL_PLAY_AUTHORITY_NOTICE)

with st.expander("Report controls", expanded=True):
    controls = st.columns(3)
    with controls[0]:
        season = int(st.selectbox("Season", available_seasons(), key="launch_reports_season"))
    with controls[1]:
        period = st.selectbox(
            "Comparison window",
            ["Season", "Last 8", "Last 4", "Last 2"],
            index=2,
            key="launch_reports_period",
        )
    with controls[2]:
        minimum_sample = int(
            st.number_input(
                "Minimum all-play opportunities",
                min_value=1,
                max_value=100,
                value=8,
                key="launch_reports_minimum",
            )
        )

window: int | str = "Season" if period == "Season" else int(period.split()[-1])
end_week = max(available_weeks(season))
selection_summary(
    f"Three-report launch · {season} · {period}",
    "All-play authority · Normal-game supporting context",
    f"Minimum {minimum_sample} all-play opportunities · Through Week {end_week}",
)

selected_report = st.segmented_control(
    "Report",
    list(REPORT_ORDER),
    default=REPORT_ORDER[0],
    key="launch_report_selection",
)
if selected_report is None:
    selected_report = REPORT_ORDER[0]

report_result = _load_report(selected_report, season, end_week, window, minimum_sample)
_render_report(selected_report, report_result, season, end_week, period)

source_footer(
    "Descriptive historical research only. No odds, picks, projections, or claims that a documented role will persist."
)
