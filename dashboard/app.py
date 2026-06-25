from __future__ import annotations

import streamlit as st

from utils import (
    apply_global_styles,
    get_latest_mtime,
    load_csv_safe,
    render_status_cards,
    show_table_or_missing,
    status_badge,
    value_from_status,
)


STATUS_PATH = "outputs/run_reports/latest_receptions_pipeline_status.csv"
BLOCKERS_PATH = "outputs/google_sheets/forward_projection_blockers.csv"
ERRORS_PATH = "outputs/run_reports/latest_receptions_pipeline_errors.csv"


def main() -> None:
    st.set_page_config(
        page_title="NFL Prop War Room - Receptions V1",
        layout="wide",
    )
    apply_global_styles()
    st.markdown(
        """
        <div class="war-header">
          <h1>NFL Prop War Room - Receptions V1</h1>
          <p>Local research and model-review dashboard. No live betting output is created here.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

    render_status_cards(
        [
            ("Current mode", mode),
            ("Final readiness", readiness),
            ("Leakage status", leakage),
            ("Live betting output", live_output),
        ]
    )

    if readiness != "GO":
        st.markdown(
            "<div class='warning-band'>HISTORICAL TEST ONLY - NOT LIVE BETTING READY</div>",
            unsafe_allow_html=True,
        )

    st.caption(f"Target: {target_season} Week {target_week}")
    st.caption(f"Last pipeline output update: {latest.strftime('%Y-%m-%d %I:%M:%S %p') if latest else 'Unknown'}")

    blockers = load_csv_safe(BLOCKERS_PATH)
    st.subheader("Current Blockers")
    show_table_or_missing(blockers, BLOCKERS_PATH)

    errors = load_csv_safe(ERRORS_PATH)
    st.subheader("Pipeline Errors")
    show_table_or_missing(errors, ERRORS_PATH)

    st.subheader("Quick Status")
    st.markdown(f"Final readiness: {status_badge(readiness)}", unsafe_allow_html=True)
    st.markdown(f"Leakage: {status_badge(leakage)}", unsafe_allow_html=True)
    st.markdown(f"Live betting output created: {status_badge(live_output)}", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
