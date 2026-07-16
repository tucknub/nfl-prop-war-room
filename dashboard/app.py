from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


DASHBOARD_DIR = Path(__file__).resolve().parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from research_ui import inject_styles  # noqa: E402
from home_page import render_home  # noqa: E402


def main() -> None:
    st.set_page_config(page_title="PropWar: NFL Role & Usage Research", page_icon="PW", layout="wide")
    inject_styles()
    with st.sidebar:
        st.markdown(
            '<div class="pw-brand"><strong>PropWar</strong><span>NFL ROLE &amp; USAGE RESEARCH</span></div>',
            unsafe_allow_html=True,
        )

    pages = {
        "Role & Usage": [
            st.Page(render_home, title="Home", icon=":material/home:", url_path="", default=True),
            st.Page("pages/01_Teams.py", title="Teams", icon=":material/groups:", url_path="teams"),
            st.Page("pages/02_Players.py", title="Players", icon=":material/person_search:", url_path="players"),
            st.Page("pages/03_Games.py", title="Games", icon=":material/sports_football:", url_path="games"),
            st.Page("pages/04_Reports.py", title="Reports", icon=":material/bar_chart:", url_path="reports"),
            st.Page("pages/05_Explorer.py", title="Advanced Research", icon=":material/search:", url_path="explorer"),
        ]
    }

    st.navigation(pages).run()


if __name__ == "__main__":
    main()
