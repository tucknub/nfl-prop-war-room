from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import apply_global_styles, load_csv_safe, render_status_cards, show_table_or_missing, status_badge


READINESS_PATH = "outputs/google_sheets/live_readiness_export.csv"
STATUS_PATH = "outputs/run_reports/latest_receptions_pipeline_status.csv"
BLOCKERS_PATH = "outputs/google_sheets/forward_projection_blockers.csv"


st.set_page_config(page_title="Live Readiness", layout="wide")
apply_global_styles()
st.title("Live Readiness")

readiness = load_csv_safe(READINESS_PATH)
status = load_csv_safe(STATUS_PATH)
blockers = load_csv_safe(BLOCKERS_PATH)

if not readiness.empty and {"Gate", "Status"}.issubset(readiness.columns):
    final = readiness.loc[readiness["Gate"].eq("Final Betting Use"), "Status"]
    final_status = final.iloc[0] if not final.empty else "UNKNOWN"
    leakage = readiness.loc[readiness["Gate"].eq("History Audit"), "Status"]
    leakage_status = leakage.iloc[0] if not leakage.empty else "UNKNOWN"
else:
    final_row = status[status.get("check_name", "").astype(str).eq("final_live_readiness")] if not status.empty else status
    final_status = final_row["value"].iloc[0] if not final_row.empty and "value" in final_row.columns else "UNKNOWN"
    leakage_row = status[status.get("check_name", "").astype(str).eq("leakage_status")] if not status.empty else status
    leakage_status = leakage_row["value"].iloc[0] if not leakage_row.empty and "value" in leakage_row.columns else "UNKNOWN"

render_status_cards([("Overall status", str(final_status)), ("Leakage", str(leakage_status))])
if str(final_status) != "GO":
    st.markdown(
        "<div class='warning-band'>HISTORICAL TEST ONLY - NOT LIVE BETTING READY</div>",
        unsafe_allow_html=True,
    )

st.subheader("Gate Table")
show_table_or_missing(readiness, READINESS_PATH)

st.subheader("Blocking Gates")
show_table_or_missing(blockers, BLOCKERS_PATH)

if not readiness.empty:
    cols = [col for col in ["Gate", "Action Needed", "Current Value", "Source", "Notes"] if col in readiness.columns]
    if cols:
        st.subheader("Action Needed")
        st.dataframe(readiness[cols], use_container_width=True, hide_index=True)
