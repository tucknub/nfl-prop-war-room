from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import ROLE_LABELS, available_seasons, available_weeks
from research_ui import (
    methodology_expander,
    page_intro,
    render_weekly_report,
    resolve_query_choice,
    selection_summary,
    source_footer,
)
from weekly_report import (
    DISPLAY_CATEGORIES,
    build_weekly_role_report,
    default_home_week,
    report_period_notice,
)


def _apply_filters(frame: pd.DataFrame, position: str, family: str, category: str) -> pd.DataFrame:
    result = frame.copy()
    if position != "All":
        result = result[result["position"].eq(position)]
    if family != "All":
        result = result[result["role_family"].eq(family)]
    if category != "All":
        result = result[result["category"].eq(category)]
    return result.reset_index(drop=True)


def _query_value(name: str) -> str:
    value = st.query_params.get(name, "")
    return value[0] if isinstance(value, list) and value else str(value)


def render_home() -> None:
    page_intro(
        "This Week in NFL Roles",
        "A concise review of changed opportunity, abnormal game context, and opportunity that outpaced production.",
    )

    seasons = available_seasons()
    requested_season_text = _query_value("season")
    requested_season = int(requested_season_text) if requested_season_text.isdigit() else None
    season, invalid_season = resolve_query_choice(
        seasons, requested_season, st.session_state.get("home_season")
    )
    if invalid_season:
        st.warning(f"Season not found: {requested_season_text}")
        st.link_button("Return to Home", "/")
        return
    st.session_state["home_season"] = season
    weeks = available_weeks(int(season))
    requested_week_text = _query_value("week")
    requested_week = int(requested_week_text) if requested_week_text.isdigit() else None
    default_week = default_home_week(int(season), weeks)
    week, invalid_week = resolve_query_choice(
        weeks, requested_week, st.session_state.get("home_week", default_week)
    )
    if invalid_week:
        st.warning(f"Week not found for {season}: {requested_week_text}")
        st.link_button("Return to Home", "/")
        return
    st.session_state["home_week"] = week

    controls = st.columns([1, 1, 4])
    with controls[0]:
        season = st.selectbox("Season", seasons, key="home_season")
    with controls[1]:
        week = st.selectbox("Week", weeks, key="home_week")

    default_cards, all_matches = build_weekly_role_report(season, week)
    positions = ["All"] + sorted(all_matches["position"].dropna().astype(str).unique().tolist()) if not all_matches.empty else ["All"]
    families = ["All"] + list(ROLE_LABELS)
    categories = ["All"] + DISPLAY_CATEGORIES
    selected_position = st.session_state.get("home_position", "All")
    selected_family = st.session_state.get("home_family", "All")
    selected_category = st.session_state.get("home_category", "All")
    if selected_position not in positions:
        selected_position = "All"
    if selected_family not in families:
        selected_family = "All"
    if selected_category not in categories:
        selected_category = "All"

    visible_cards = _apply_filters(default_cards, selected_position, selected_family, selected_category)
    active_filters = [
        selected_position if selected_position != "All" else "All positions",
        ROLE_LABELS[selected_family] if selected_family != "All" else "All role families",
        selected_category if selected_category != "All" else "All categories",
    ]
    selection_summary(
        f"{season} · Week {week}",
        " · ".join(active_filters),
        f"{len(visible_cards)} situations · {visible_cards['category'].nunique() if not visible_cards.empty else 0} categories",
    )

    period_notice = report_period_notice(int(week))
    if period_notice:
        notice_type, notice_text = period_notice
        getattr(st, notice_type)(notice_text)

    render_weekly_report(visible_cards, DISPLAY_CATEGORIES)

    with st.expander("Change filters"):
        filter_columns = st.columns(3)
        with filter_columns[0]:
            st.selectbox("Position", positions, index=positions.index(selected_position), key="home_position")
        with filter_columns[1]:
            st.selectbox(
                "Role family",
                families,
                index=families.index(selected_family),
                format_func=lambda value: "All role families" if value == "All" else ROLE_LABELS[value],
                key="home_family",
            )
        with filter_columns[2]:
            st.selectbox("Category", categories, index=categories.index(selected_category), key="home_category")

    with st.expander("View all qualifying results"):
        all_visible = _apply_filters(all_matches, selected_position, selected_family, selected_category)
        st.caption(
            "Technical category matches are shown here before the one-player, one-primary-category presentation rule."
        )
        if all_visible.empty:
            st.info("No situations meet the documented screening rules for these filters.")
        else:
            display = all_visible[
                [
                    "category",
                    "player_name",
                    "team",
                    "position",
                    "role_family_label",
                    "current_raw",
                    "current_denominator",
                    "current_share",
                    "baseline_share",
                    "share_change",
                    "baseline_games",
                    "secondary_categories",
                ]
            ].copy()
            display.columns = [
                "Category",
                "Player",
                "Team",
                "Position",
                "Role family",
                "Raw",
                "Denominator",
                "Current share",
                "Baseline share",
                "Change",
                "Baseline games",
                "All qualifying categories",
            ]
            st.dataframe(
                display,
                width="stretch",
                hide_index=True,
                column_config={
                    "Current share": st.column_config.NumberColumn(format="%.1%%"),
                    "Baseline share": st.column_config.NumberColumn(format="%.1%%"),
                    "Change": st.column_config.NumberColumn(format="%+.1%%"),
                },
            )

    methodology_expander(
        [
            "Selected-week shares use player opportunities divided by the matching same-team opportunity count.",
            "The baseline sums counts from up to four earlier qualifying games in the same season before division.",
            "Confirmed partial games are excluded; suspected partial games remain included and labeled.",
            "Category assignment is deterministic and descriptive. It does not claim that usage will continue.",
        ]
    )
    source_footer("Completed historical data through 2025; the 2026 NFL season has not started.")
