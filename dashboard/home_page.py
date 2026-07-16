from __future__ import annotations

import pandas as pd
import streamlit as st

from research_data import ROLE_LABELS, available_seasons, available_weeks
from research_ui import (
    enable_browser_history_sync,
    methodology_expander,
    page_intro,
    initialize_query_control,
    parse_int,
    render_weekly_report,
    selection_summary,
    source_footer,
    update_query_from_widget,
)
from supporting_evidence import apply_home_wording
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


def render_home() -> None:
    enable_browser_history_sync()
    page_intro(
        "This Week in NFL Roles",
        "A concise review of changed opportunity, abnormal game context, and opportunity that outpaced production.",
    )

    seasons = available_seasons()
    season_state = initialize_query_control(
        "home", "season", "home_season", seasons, parser=parse_int
    )
    season = season_state.value
    weeks = available_weeks(int(season))
    default_week = default_home_week(int(season), weeks)
    week_state = initialize_query_control(
        "home", "week", "home_week", weeks, default=default_week, parser=parse_int
    )
    week = week_state.value

    controls = st.columns([1, 1, 4])
    with controls[0]:
        season = st.selectbox(
            "Season", seasons, key="home_season",
            on_change=update_query_from_widget,
            args=("season", "home_season"),
            kwargs={"clear_query": ("week",)},
        )
    with controls[1]:
        week = st.selectbox(
            "Week", weeks, key="home_week",
            on_change=update_query_from_widget,
            args=("week", "home_week"),
        )

    if season_state.invalid_query or week_state.invalid_query:
        if season_state.invalid_query:
            st.warning("The requested season was not found. Select a valid season to continue.")
        if week_state.invalid_query:
            st.warning(f"The requested week was not found for {season}. Select a valid week to continue.")
        return

    default_cards, all_matches = build_weekly_role_report(season, week)
    default_cards = apply_home_wording(default_cards)
    all_matches = apply_home_wording(all_matches)
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

    st.caption(
        "Normal-game share removes defined late-game and abnormal contexts that can distort workload."
    )

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
