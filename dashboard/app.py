from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


DASHBOARD_DIR = Path(__file__).resolve().parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from research_ui import inject_styles  # noqa: E402
from research_data import operational_status_text  # noqa: E402
from home_page import render_home  # noqa: E402


def render_launch_home() -> None:
    st.title("Know what changed before researching what happens next.")
    st.write(
        "PropWar turns documented offensive opportunities into three transparent NFL role reports. "
        "Every share remains attached to its raw player count and matching same-team denominator."
    )
    st.info(operational_status_text())
    report_columns = st.columns(3)
    report_copy = (
        (
            "Backfield Control",
            "Carries and total RB opportunities. See who actually controls each backfield.",
        ),
        (
            "Target Hierarchy",
            "WR and TE targets. See how each team's documented passing work is distributed.",
        ),
        (
            "Role Movement",
            "Current window versus the prior matching window. See which roles changed most.",
        ),
    )
    for column, (title, description) in zip(report_columns, report_copy):
        with column:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.write(description)
                st.link_button("Open Reports", "/reports", use_container_width=True)
    st.caption(
        "Descriptive historical research only. No market pricing, picks, projections, or claim that a role will continue."
    )
    st.divider()
    render_home()


def main() -> None:
    st.set_page_config(page_title="PropWar: NFL Role Intelligence", page_icon="PW", layout="wide")
    inject_styles()
    with st.sidebar:
        st.markdown(
            '<div class="pw-brand"><strong>PropWar</strong><span>NFL ROLE INTELLIGENCE</span></div>',
            unsafe_allow_html=True,
        )

    pages = {
        "Role Intelligence": [
            st.Page(render_launch_home, title="Home", icon=":material/home:", url_path="", default=True),
            st.Page("pages/04_Reports.py", title="Reports", icon=":material/bar_chart:", url_path="reports"),
            st.Page("pages/01_Teams.py", title="Teams", icon=":material/groups:", url_path="teams"),
            st.Page("pages/02_Players.py", title="Players", icon=":material/person_search:", url_path="players"),
            st.Page("pages/03_Games.py", title="Games", icon=":material/sports_football:", url_path="games"),
            st.Page("pages/05_Explorer.py", title="Advanced Research", icon=":material/search:", url_path="explorer"),
            st.Page("pages/06_Methodology.py", title="Methodology", icon=":material/menu_book:", url_path="methodology"),
        ]
    }

    st.navigation(pages).run()


if __name__ == "__main__":
    main()
