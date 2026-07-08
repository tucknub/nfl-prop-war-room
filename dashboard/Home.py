from __future__ import annotations

import streamlit as st

from utils import inject_global_styles, page_header, sidebar_status, warning_banner


def main() -> None:
    st.set_page_config(page_title="NFL Prop War Room", layout="wide")
    inject_global_styles()
    sidebar_status()

    page_header(
        "NFL Prop War Room",
        "Signal-first NFL prop research board.",
        "HISTORICAL TEST ONLY",
    )
    warning_banner(
        "HISTORICAL TEST ONLY - NOT LIVE BETTING READY",
        "Final readiness remains NO-GO. This app does not create live betting output.",
    )

    st.markdown(
        """
        <div class="info-card">
        <strong>Start here:</strong><br>
        1. Signal Command Center<br>
        2. By-Game Matchup Board<br>
        3. Position Signal Boards<br>
        4. Player Signal Drilldown<br>
        5. Blocked / Review
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(2)
    with cols[0]:
        st.markdown(
            """
            <div class="info-card">
            <strong>Research Lab</strong><br><br>
            Model validation, backtests, tuning, challenger previews, and run reports.
            </div>
            """,
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            """
            <div class="info-card">
            <strong>Admin / Readiness</strong><br><br>
            Data quality, gates, identity checks, current maps, and safety status.
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
