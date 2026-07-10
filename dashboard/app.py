from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Streamlit's multipage runner does not guarantee that the dashboard directory
# is on sys.path when a page is executed.  Register it once at the entrypoint
# so every page resolves the shared presentation modules consistently locally
# and on Streamlit Cloud.
dashboard_dir = str(Path(__file__).resolve().parent)
if dashboard_dir not in sys.path:
    sys.path.insert(0, dashboard_dir)


pages = [
    st.Page("Home.py", title="Today’s Board", url_path="", default=True),
    st.Page("pages/02_By_Game_Matchup_Board.py", title="Matchups", url_path="By_Game_Matchup_Board"),
    st.Page("pages/03_Position_Signal_Boards.py", title="By Position", url_path="Position_Signal_Boards"),
    st.Page("pages/04_Player_Signal_Drilldown.py", title="Player Details", url_path="Player_Signal_Drilldown"),
    st.Page("pages/05_Blocked_Review.py", title="Needs Review", url_path="Blocked_Review"),
]

navigation = st.navigation(pages)
navigation.run()
