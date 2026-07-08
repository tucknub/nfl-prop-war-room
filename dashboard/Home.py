from __future__ import annotations

import streamlit as st

from utils import inject_global_styles, metric_card, page_header, section_header, sidebar_status, value_from_status, warning_banner


def main() -> None:
    st.set_page_config(page_title="NFL Prop War Room", layout="wide")
    inject_global_styles()
    sidebar_status()

    readiness = value_from_status("final_live_readiness")
    leakage = value_from_status("leakage_status")
    live_output = value_from_status("live_betting_output_created")

    page_header(
        "NFL Prop War Room",
        "Signal-first control room for historical-test NFL player prop research.",
        readiness,
    )
    warning_banner(
        "HISTORICAL TEST ONLY - NOT LIVE BETTING READY",
        "The main product is the signal board workflow. Model/debug pages are secondary.",
    )

    cols = st.columns(3)
    with cols[0]:
        metric_card("Final Readiness", readiness, readiness)
    with cols[1]:
        metric_card("Leakage", leakage, leakage)
    with cols[2]:
        metric_card("Live Output", live_output, live_output)

    section_header("Start Here")
    choice_cols = st.columns(3)
    with choice_cols[0]:
        st.markdown(
            """
            <div class="info-card">
            <div class="player-name">Start Here: Signal Command Center</div>
            <div class="metric-help">Open <strong>02 Signal Command Center</strong> first. It summarizes the slate, top signals, game mini-board, and drilldown workflow.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with choice_cols[1]:
        st.markdown(
            """
            <div class="info-card">
            <div class="player-name">Research Lab: Audits / Backtests / Tuning</div>
            <div class="metric-help">Use score audit, historical backtest, weight tuning, and champion/challenger preview to validate signal behavior.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with choice_cols[2]:
        st.markdown(
            """
            <div class="info-card">
            <div class="player-name">Admin: Readiness / Data Intake / Gates</div>
            <div class="metric-help">Use readiness, intake, roster, role, injury, identity, and market-data pages to understand why live readiness remains blocked.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    section_header("Recommended Workflow")
    st.markdown(
        """
        <div class="info-card">
        1. Signal Command Center<br>
        2. Slate Signal Board<br>
        3. By-Game Matchup Board<br>
        4. Receiving / Rushing / Passing Signal Boards<br>
        5. Player Signal Drilldown<br>
        6. Blocked / Review Board
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
