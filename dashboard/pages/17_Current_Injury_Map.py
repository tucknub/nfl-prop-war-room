from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import (
    inject_global_styles,
    load_csv_safe,
    metric_card,
    page_header,
    presentation_table,
    section_header,
    show_table_or_missing,
    sidebar_status,
    warning_banner,
)


MAP = "outputs/injuries/current_injury_map.csv"
STATUS = "outputs/injuries/current_injury_map_status.csv"
REVIEW = "outputs/injuries/current_injury_needs_review.csv"


st.set_page_config(page_title="Injury / Availability Mapping", layout="wide")
inject_global_styles()
sidebar_status()

page_header(
    "Injury / Availability Mapping",
    "Verified player availability required before any forward projection can become live-ready.",
    "NO-GO",
)
warning_banner(
    "Forward projection blocked until player availability is verified",
    "Template rows do not count as injury data. Questionable, unknown, out, IR, inactive, team-mismatched, and unapproved override rows remain review or blocking conditions.",
)

mapped = load_csv_safe(MAP)
status = load_csv_safe(STATUS)
review = load_csv_safe(REVIEW)


def value(column: str) -> int:
    if status.empty or column not in status.columns:
        return 0
    numeric = pd.to_numeric(status[column], errors="coerce").iloc[0]
    return 0 if pd.isna(numeric) else int(numeric)


overall = str(status.status.iloc[0]) if not status.empty and "status" in status.columns else "NEEDS DATA"
items = [
    ("Injury Rows Loaded", value("injury_rows_loaded"), overall),
    ("READY", value("ready_rows"), "READY"),
    ("NEEDS REVIEW", value("needs_review_rows"), "NEEDS REVIEW"),
    ("NEEDS DATA", value("needs_data_rows"), "NEEDS DATA"),
    ("BLOCKED", value("blocked_rows"), "BLOCKED"),
    ("Questionable / Limited", value("questionable_limited_rows"), "NEEDS REVIEW"),
    ("Out / IR / Inactive", value("out_ir_inactive_rows"), "BLOCKED"),
    ("Manual Overrides", value("manual_overrides"), "REVIEW"),
]

cols = st.columns(4)
for index, (label, metric, state) in enumerate(items):
    with cols[index % 4]:
        metric_card(label, metric, state)

st.markdown(
    '<div class="info-card">Roster tells us where a player is. Role tells us expected workload. Injury mapping tells us whether that workload is available. A player can have a strong projection and still be blocked if availability is unclear.</div>',
    unsafe_allow_html=True,
)

section_header("Current Injury Map", f"Overall mapping status: {overall}")
show_table_or_missing(presentation_table(mapped), MAP)

section_header("Needs Review")
show_table_or_missing(presentation_table(review), REVIEW)

with st.expander("Injury map status details"):
    show_table_or_missing(presentation_table(status), STATUS)
