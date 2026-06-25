from __future__ import annotations

import streamlit as st

from utils import (
    get_latest_mtime,
    inject_global_styles,
    load_csv_safe,
    metric_card,
    page_header,
    presentation_table,
    section_header,
    show_table_or_missing,
    sidebar_status,
    value_from_status,
    warning_banner,
)


STATUS_PATH = "outputs/run_reports/latest_receptions_pipeline_status.csv"
BLOCKERS_PATH = "outputs/google_sheets/forward_projection_blockers.csv"
ERRORS_PATH = "outputs/run_reports/latest_receptions_pipeline_errors.csv"


def main() -> None:
    st.set_page_config(page_title="NFL Prop War Room - Receptions V1", layout="wide")
    inject_global_styles()
    sidebar_status()

    mode = value_from_status("projection_mode")
    readiness = value_from_status("final_live_readiness")
    leakage = value_from_status("leakage_status")
    live_output = value_from_status("live_betting_output_created")
    target_season = value_from_status("target_season")
    target_week = value_from_status("target_week")
    latest = get_latest_mtime(
        [
            STATUS_PATH,
            "outputs/google_sheets_receptions_historical_test.csv",
            "outputs/google_sheets/live_readiness_export.csv",
            "outputs/market_edges/receptions_line_ladder.csv",
        ]
    )

    page_header(
        "NFL Prop War Room",
        "Receptions V1 Dashboard. Historical-test control room for NFL player reception projections.",
        readiness,
    )

    cols = st.columns(4)
    with cols[0]:
        metric_card("Current Mode", mode, mode, "Target remains historical test.")
    with cols[1]:
        metric_card("Final Readiness", readiness, readiness, "Live use is blocked until all gates pass.")
    with cols[2]:
        metric_card("Leakage Status", leakage, leakage, "Feature window audit result.")
    with cols[3]:
        metric_card("Live Betting Output", live_output, live_output, "Must remain False while NO-GO.")

    warning_banner(
        "HISTORICAL TEST ONLY - NOT LIVE BETTING READY",
        "This public dashboard reviews committed model outputs. It does not create bets, does not load secrets, and does not switch to forward projection.",
    )

    st.caption(f"Target: {target_season} Week {target_week}")
    st.caption(f"Last pipeline output update: {latest.strftime('%Y-%m-%d %I:%M:%S %p') if latest else 'Unknown'}")

    section_header("What This Dashboard Is", "A polished read-only review layer for the stable Receptions V1 build.")
    st.markdown(
        """
        <div class="info-card">
        This dashboard reviews model output, line-ladder probabilities, gate readiness, identity warnings, and run reports.
        It is not betting-ready until all gates pass and Final Readiness becomes GO.
        </div>
        """,
        unsafe_allow_html=True,
    )

    blockers = load_csv_safe(BLOCKERS_PATH)
    section_header("Current Blockers", "The gates keeping the system in NO-GO mode.")
    if blockers.empty:
        show_table_or_missing(blockers, BLOCKERS_PATH)
    else:
        show_table_or_missing(presentation_table(blockers), BLOCKERS_PATH)

    section_header("Use This Dashboard For")
    good, bad = st.columns(2)
    with good:
        st.markdown(
            """
            <div class="info-card">
            <strong>Safe review tasks</strong><br><br>
            - Inspect historical-test projections<br>
            - Review line-ladder probabilities<br>
            - Check gate and identity blockers<br>
            - Read validation and audit reports
            </div>
            """,
            unsafe_allow_html=True,
        )
    with bad:
        st.markdown(
            """
            <div class="info-card">
            <strong>Do not use it for</strong><br><br>
            - Live betting decisions<br>
            - Forward 2026 projections<br>
            - Treating ladder probabilities as edges<br>
            - Bypassing roster, role, injury, or odds gates
            </div>
            """,
            unsafe_allow_html=True,
        )

    errors = load_csv_safe(ERRORS_PATH)
    section_header("Pipeline Errors", "Expected clean state is a single NONE row.")
    show_table_or_missing(errors, ERRORS_PATH)


if __name__ == "__main__":
    main()
