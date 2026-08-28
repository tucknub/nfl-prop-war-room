from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PAGE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = PAGE_DIR.parent
REPO_ROOT = DASHBOARD_DIR.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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


def _sync_report_query() -> None:
    selected = st.session_state.get("reports_report")
    if selected in REPORT_ORDER:
        st.query_params["report"] = selected
        st.session_state["reports_last_query"] = selected


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
            f"{role_noun(family)} for {team}. The current share is "
            f"{raw} of {denominator} ({share:.1%})."
        )
    return (
        f"{player} controls {raw} of {denominator} {role_noun(family)} for {team} "
        f"({share:.1%} of the team total)."
    )


def _render_answers(report: str, rows: pd.DataFrame, season: int, end_week: int) -> None:
    section("Top findings", "The clearest answers first, with the counts behind each percentage.")
    for rank, (_, row) in enumerate(rows.head(3).iterrows(), 1):
        with st.container(border=True):
            st.markdown(
                f"### {rank}. {row['player_name']}"
            )
            st.caption(
                f"{row['team']} · {row['position']} · {row['role_family_label']}"
            )
            metrics = st.columns(3)
            metrics[0].metric("Team share", f"{float(row['share']):.1%}")
            metrics[1].metric(
                "Opportunities",
                f"{_whole(row['raw_opportunities'])} of {_whole(row['team_denominator'])}",
            )
            if report == "Role Movement":
                metrics[2].metric(
                    "Change",
                    f"{float(row['change']) * 100:+.1f} pp",
                )
            elif pd.notna(row.get("normal_share")):
                metrics[2].metric("Typical-game share", f"{float(row['normal_share']):.1%}")
            else:
                metrics[2].metric("Games", _whole(row.get("sample_games")))

            st.write(_answer(report, row))
            all_play = ratio_text(
                row["raw_opportunities"],
                row["team_denominator"],
                role_noun(str(row["role_family"])),
            )
            normal = "Typical-game context unavailable"
            if pd.notna(row.get("normal_share")):
                normal = (
                    f"Typical game: {_whole(row.get('normal_raw'))} of "
                    f"{_whole(row.get('normal_denominator'))} "
                    f"({float(row['normal_share']):.1%})"
                )
            st.caption(f"All-play evidence: {all_play} · {normal}")
            links = st.columns(2)
            with links[0]:
                st.link_button(
                    "View player evidence",
                    f"/players?player={row['player_id']}&season={season}&family={row['role_family']}&week={end_week}",
                    use_container_width=True,
                )
            with links[1]:
                st.link_button(
                    "View team evidence",
                    f"/teams?team={row['team']}&season={season}&family={row['role_family']}&week={end_week}",
                    use_container_width=True,
                )


def _render_table(report: str, rows: pd.DataFrame, season: int, end_week: int) -> None:
    section(
        "Complete report",
        "Scan the essential columns first. Open the evidence table only when you need the full detail.",
    )
    display = rows.copy()
    display["Team share"] = pd.to_numeric(display["share"], errors="coerce") * 100
    display["Typical-game share"] = pd.to_numeric(display["normal_share"], errors="coerce") * 100
    if report == "Role Movement":
        display["Change"] = pd.to_numeric(display["change"], errors="coerce") * 100
    display = display.rename(
        columns={
            "player_name": "Player",
            "team": "Team",
            "position": "Position",
            "role_family_label": "Role",
            "raw_opportunities": "Opportunities",
            "team_denominator": "Team total",
            "normal_raw": "Typical-game opportunities",
            "normal_denominator": "Typical-game team total",
            "sample_games": "Games",
        }
    )
    compact_columns = [
        "Player",
        "Team",
        "Position",
        "Role",
        "Opportunities",
        "Team total",
        "Team share",
        "Games",
    ]
    if report == "Role Movement":
        compact_columns.insert(7, "Change")

    full_columns = [
        "Player",
        "Team",
        "Position",
        "Role",
        "Opportunities",
        "Team total",
        "Team share",
        "Typical-game opportunities",
        "Typical-game team total",
        "Typical-game share",
        "Games",
    ]
    if report == "Role Movement":
        full_columns.insert(7, "Change")

    cards: list[dict[str, object]] = []
    for rank, (_, row) in enumerate(rows.head(12).iterrows(), 1):
        metrics: list[tuple[object, ...]] = [
            (
                "Team share",
                f"{float(row['share']):.1%}",
                ratio_text(
                    row["raw_opportunities"],
                    row["team_denominator"],
                    role_noun(str(row["role_family"])),
                ),
            )
        ]
        if report == "Role Movement":
            metrics.append(
                (
                    "Change",
                    f"{float(row['change']) * 100:+.1f} pp",
                    "Current versus prior matching period",
                    True,
                )
            )
        if pd.notna(row.get("normal_share")):
            metrics.append(
                ("Typical-game share", f"{float(row['normal_share']):.1%}", "Supporting context")
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

    percent_columns = ["Team share"]
    if report == "Role Movement":
        percent_columns.append("Change")
    responsive_table(
        display[compact_columns],
        cards,
        key=f"launch_report_{report.lower().replace(' ', '_')}",
        height=650,
        percent_columns=percent_columns,
        label="Open complete report table",
    )

    with st.expander("Show all evidence columns"):
        st.caption(
            "Typical-game values help review unusual late-game or extreme situations. The full-period player count and team total remain the authority."
        )
        evidence_percent_columns = {
            "Team share": st.column_config.NumberColumn(format="%.1f%%"),
            "Typical-game share": st.column_config.NumberColumn(format="%.1f%%"),
        }
        if report == "Role Movement":
            evidence_percent_columns["Change"] = st.column_config.NumberColumn(format="%+.1f pp")
        st.dataframe(
            display[full_columns],
            width="stretch",
            hide_index=True,
            column_config=evidence_percent_columns,
        )


page_intro(
    "NFL Role Intelligence",
    "Choose one question, see the clearest answers, then inspect the evidence only when you need it.",
)
st.caption(operational_status_text())
st.caption(ALL_PLAY_AUTHORITY_NOTICE)

requested_report = str(st.query_params.get("report", ""))
last_query = st.session_state.get("reports_last_query")
if requested_report in REPORT_ORDER and requested_report != last_query:
    st.session_state["reports_report"] = requested_report
    st.session_state["reports_last_query"] = requested_report
elif st.session_state.get("reports_report") not in REPORT_ORDER:
    st.session_state["reports_report"] = REPORT_ORDER[0]
    st.session_state["reports_last_query"] = REPORT_ORDER[0]

selected_report = st.segmented_control(
    "Choose report",
    list(REPORT_ORDER),
    key="reports_report",
    on_change=_sync_report_query,
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

with st.expander("Customize report"):
    controls = st.columns(5)
    with controls[0]:
        season = int(st.selectbox("Season", available_seasons(), key="reports_season"))
    with controls[1]:
        period = st.selectbox(
            "Time period",
            ["Season", "Last 8", "Last 4", "Last 2"],
            index=2,
            key="reports_period",
        )
    with controls[2]:
        context = st.selectbox(
            "Typical-game context",
            ["Normal game"],
            key="reports_context",
            format_func=lambda _: "Included",
        )
    with controls[3]:
        minimum_sample = int(
            st.number_input(
                "Minimum opportunities to appear",
                min_value=1,
                max_value=100,
                value=8,
                key="reports_minimum",
            )
        )
    with controls[4]:
        sort_by = st.selectbox("Sort results", sort_options, key="reports_sort")

window: int | str = "Season" if period == "Season" else int(period.split()[-1])
end_week = max(available_weeks(season))
selection_summary(
    f"{selected_report} · {season} · {period} · Through Week {end_week}",
    "Share of team opportunities from all documented plays",
    f"Typical-game context included · Minimum {minimum_sample} opportunities",
)

rows = _report_rows(selected_report, season, end_week, window, minimum_sample, sort_by)
if rows.empty:
    st.info("No players meet the selected time period and minimum opportunity requirement.")
else:
    _render_answers(selected_report, rows, season, end_week)
    _render_table(selected_report, rows, season, end_week)

methodology_expander(list(REPORT_METHODS[selected_report]))
source_footer(operational_status_text())
