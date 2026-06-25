from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import apply_global_styles, filter_by_search, load_csv_safe, show_table_or_missing


DUPLICATE_PATH = "outputs/identity/duplicate_name_warnings.csv"
UNMATCHED_PATH = "outputs/identity/unmatched_gate_rows.csv"
REPORT_PATH = "outputs/identity/gate_identity_match_report.csv"


st.set_page_config(page_title="Identity Warnings", layout="wide")
apply_global_styles()
st.title("Identity Warnings")
st.info("Duplicate-name warnings do not mean the system is broken. They prevent unsafe name-only matching.")

duplicates = load_csv_safe(DUPLICATE_PATH)
unmatched = load_csv_safe(UNMATCHED_PATH)
report = load_csv_safe(REPORT_PATH)

st.subheader("Identity Match Report")
show_table_or_missing(report, REPORT_PATH)

st.subheader("Duplicate Name Warnings")
if not duplicates.empty:
    duplicates = filter_by_search(duplicates, "normalized_player_name", "Search normalized name")
show_table_or_missing(duplicates, DUPLICATE_PATH)

st.subheader("Unmatched Gate Rows")
show_table_or_missing(unmatched, UNMATCHED_PATH)
