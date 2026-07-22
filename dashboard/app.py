from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

import streamlit as st


DASHBOARD_DIR = Path(__file__).resolve().parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from research_ui import inject_styles, section  # noqa: E402
from research_data import operational_status_text  # noqa: E402
from home_page import render_home  # noqa: E402


REPORT_CARDS = (
    (
        "Backfield Control",
        "See which running backs own their team's carries and total backfield opportunities.",
    ),
    (
        "Target Hierarchy",
        "See how documented WR and TE targets are distributed within each offense.",
    ),
    (
        "Role Movement",
        "See which player roles gained or lost the most share versus the prior period.",
    ),
)


def render_launch_home() -> None:
    st.markdown(
        """
        <section class="pw-home-hero">
          <span>PROP WAR · NFL ROLE INTELLIGENCE</span>
          <h1>What changed in NFL roles?</h1>
          <p>Start with a clear answer, then inspect the player counts, team totals, and supporting evidence behind it.</p>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="pw-status-line"><strong>Data status</strong><span>{operational_status_text()}</span></div>',
        unsafe_allow_html=True,
    )

    section("Choose a report", "Each report answers one research question without odds, picks, or projections.")
    report_columns = st.columns(3)
    for column, (title, description) in zip(report_columns, REPORT_CARDS):
        with column:
            with st.container(border=True):
                st.markdown(f"### {title}")
                st.write(description)
                st.markdown(
                    f'<a class="pw-primary-link" href="/reports?report={quote(title)}">View {title}</a>',
                    unsafe_allow_html=True,
                )

    st.caption(
        "Historical and current-season role research only. Every percentage remains attached to its player count and team total."
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
