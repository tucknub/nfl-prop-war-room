from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (inject_global_styles, load_csv_safe, metric_card, page_header,
                   presentation_table, section_header, show_table_or_missing,
                   sidebar_status, warning_banner)


MAP_PATH = "outputs/roster/current_roster_map.csv"
STATUS_PATH = "outputs/roster/current_roster_map_status.csv"
REVIEW_PATH = "outputs/roster/current_roster_needs_review.csv"

st.set_page_config(page_title="Current Roster / Team Mapping", layout="wide")
inject_global_styles()
sidebar_status()
page_header("Current Roster / Team Mapping", "Verified team context required for every forward projection.", "NO-GO")
st.caption("Section: Readiness / Data Admin")
warning_banner("Forward projection blocked until current teams are verified", "Template rows do not count as roster data. Every changed team needs source-backed verification or an approved override.")

mapped = load_csv_safe(MAP_PATH)
status = load_csv_safe(STATUS_PATH)
review = load_csv_safe(REVIEW_PATH)

def status_value(column: str, default: int = 0) -> int:
    if status.empty or column not in status.columns:
        return default
    value = pd.to_numeric(status[column], errors="coerce").iloc[0]
    return default if pd.isna(value) else int(value)

overall = str(status["status"].iloc[0]) if not status.empty and "status" in status.columns else "NEEDS DATA"
cards = st.columns(4)
values = [
    ("Roster Rows Loaded", status_value("roster_rows_loaded"), overall),
    ("READY", status_value("ready_rows"), "READY"),
    ("NEEDS REVIEW", status_value("needs_review_rows"), "NEEDS REVIEW"),
    ("NEEDS DATA", status_value("needs_data_rows"), "NEEDS DATA"),
    ("BLOCKED", status_value("blocked_rows"), "BLOCKED"),
    ("Changed Teams", status_value("changed_team_rows"), "REVIEW"),
    ("Manual Overrides", status_value("manual_overrides"), "REVIEW"),
]
for index, (label, value, state) in enumerate(values):
    with cards[index % 4]:
        metric_card(label, value, state)

st.markdown(
    """<div class="info-card">Historical team is where the stats came from. Current/projection team is what forward projections must use. Team changes require source-backed verification before live use.</div>""",
    unsafe_allow_html=True,
)

section_header("Current Roster Map", f"Overall mapping status: {overall}")
show_table_or_missing(presentation_table(mapped), MAP_PATH)
section_header("Needs Review")
show_table_or_missing(presentation_table(review), REVIEW_PATH)

with st.expander("Roster map status details"):
    show_table_or_missing(presentation_table(status), STATUS_PATH)
