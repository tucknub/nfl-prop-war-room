from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import inject_global_styles, load_csv_safe, metric_card, page_header, presentation_table, section_header, show_table_or_missing, sidebar_status


GATE_INPUT_PATH = "outputs/gate_inputs_normalized/gate_input_status.csv"
IDENTITY_PATH = "outputs/identity/gate_identity_match_report.csv"
SAFETY_PATH = "outputs/run_reports/latest_receptions_safety_validation.csv"
DRY_RUN_PATH = "outputs/run_reports/latest_forward_projection_dry_run.csv"


st.set_page_config(page_title="Forward Readiness Gates", layout="wide")
inject_global_styles()
sidebar_status()
page_header("Forward Readiness Gates", "Control-room view of the gates required before forward projection and betting use.", "NO-GO")

gate_inputs = load_csv_safe(GATE_INPUT_PATH)
identity = load_csv_safe(IDENTITY_PATH)
safety = load_csv_safe(SAFETY_PATH)
dry_run = load_csv_safe(DRY_RUN_PATH)


def gate_status(gate: str) -> str:
    if gate_inputs.empty or "gate" not in gate_inputs.columns:
        return "UNKNOWN"
    row = gate_inputs[gate_inputs["gate"].astype(str).eq(gate)]
    return str(row["status"].iloc[0]) if not row.empty and "status" in row.columns else "UNKNOWN"


identity_status = "PASS"
if not identity.empty and "status" in identity.columns:
    values = set(identity["status"].dropna().astype(str))
    identity_status = "NEEDS DATA" if "NEEDS DATA" in values else ("FAIL" if "BLOCKED" in values else "PASS")
safety_status = "PASS" if not safety.empty and not safety["status"].astype(str).eq("FAIL").any() else "FAIL"
dry_status = "PASS" if not dry_run.empty and not dry_run["status"].astype(str).eq("FAIL").any() else "FAIL"

section_header("Gate Cards")
row1 = st.columns(4)
for col, (label, status) in zip(
    row1,
    [
        ("Schedule", gate_status("schedule")),
        ("Roster", gate_status("roster")),
        ("Role", gate_status("role")),
        ("Injury", gate_status("injury")),
    ],
):
    with col:
        metric_card(label, status, status)
row2 = st.columns(4)
for col, (label, status) in zip(
    row2,
    [
        ("Market Odds", gate_status("market_odds")),
        ("Identity", identity_status),
        ("Safety", safety_status),
        ("Forward Dry Run", dry_status),
    ],
):
    with col:
        metric_card(label, status, status)

section_header("What Must Happen Before GO?")
st.markdown(
    """
    <div class="info-card">
    Roster, role, injury, identity, and market odds gates must be loaded with real validated data.
    Historical-test mode must be replaced by a true forward projection only after the required live gates are ready.
    </div>
    """,
    unsafe_allow_html=True,
)

tabs = st.tabs(["Gate Inputs", "Identity", "Safety Validator", "Forward Dry Run"])
with tabs[0]:
    show_table_or_missing(presentation_table(gate_inputs), GATE_INPUT_PATH)
with tabs[1]:
    show_table_or_missing(presentation_table(identity), IDENTITY_PATH)
with tabs[2]:
    show_table_or_missing(presentation_table(safety), SAFETY_PATH)
with tabs[3]:
    show_table_or_missing(presentation_table(dry_run), DRY_RUN_PATH)
