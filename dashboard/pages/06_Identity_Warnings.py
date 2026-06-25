from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import filter_by_search, inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, show_table_or_missing, sidebar_status


DUPLICATE_PATH = "outputs/identity/duplicate_name_warnings.csv"
UNMATCHED_PATH = "outputs/identity/unmatched_gate_rows.csv"
REPORT_PATH = "outputs/identity/gate_identity_match_report.csv"
CROSSWALK_PATH = "outputs/identity/player_identity_crosswalk.csv"


st.set_page_config(page_title="Identity & Team Matching", layout="wide")
inject_global_styles()
sidebar_status()
page_header("Identity & Team Matching", "Player/team matching guardrails that prevent wrong-player and stale-team errors.", "NEEDS DATA")

duplicates = load_csv_safe(DUPLICATE_PATH)
unmatched = load_csv_safe(UNMATCHED_PATH)
report = load_csv_safe(REPORT_PATH)
crosswalk = load_csv_safe(CROSSWALK_PATH)

team_verify = 0
if not report.empty and "team_verify_rows" in report.columns:
    team_verify = int(report["team_verify_rows"].fillna(0).sum())

cards = st.columns(4)
with cards[0]:
    metric_card("Crosswalk Rows", f"{len(crosswalk):,}")
with cards[1]:
    metric_card("Duplicate Warnings", f"{len(duplicates):,}", "REVIEW" if len(duplicates) else "PASS")
with cards[2]:
    metric_card("Unmatched Rows", f"{len(unmatched):,}", "PASS" if len(unmatched) == 0 else "FAIL")
with cards[3]:
    metric_card("TEAM_VERIFY Rows", team_verify, "PASS" if team_verify == 0 else "TEAM_VERIFY")

st.markdown(
    """
    <div class="info-card">
    Duplicate-name warnings are protective, not a failure. They prevent unsafe name-only matches and force stronger identity checks.
    </div>
    """,
    unsafe_allow_html=True,
)

section_header("Identity Match Report")
show_table_or_missing(presentation_table(report), REPORT_PATH)

section_header("Duplicate Name Warnings")
if not duplicates.empty:
    duplicates = filter_by_search(duplicates, "normalized_player_name", "Search normalized name")
show_table_or_missing(presentation_table(duplicates), DUPLICATE_PATH)

section_header("Unmatched Gate Rows")
show_table_or_missing(presentation_table(unmatched), UNMATCHED_PATH)
