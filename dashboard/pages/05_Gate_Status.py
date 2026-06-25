from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import apply_global_styles, load_csv_safe, render_status_cards, show_table_or_missing


GATE_INPUT_PATH = "outputs/gate_inputs_normalized/gate_input_status.csv"
IDENTITY_PATH = "outputs/identity/gate_identity_match_report.csv"
SAFETY_PATH = "outputs/run_reports/latest_receptions_safety_validation.csv"
DRY_RUN_PATH = "outputs/run_reports/latest_forward_projection_dry_run.csv"


st.set_page_config(page_title="Gate Status", layout="wide")
apply_global_styles()
st.title("Gate Status")

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

render_status_cards(
    [
        ("Schedule Gate", gate_status("schedule")),
        ("Roster Gate", gate_status("roster")),
        ("Role Gate", gate_status("role")),
        ("Injury Gate", gate_status("injury")),
    ]
)
render_status_cards(
    [
        ("Market Odds Gate", gate_status("market_odds")),
        ("Identity Gate", identity_status),
        ("Safety Validator", safety_status),
        ("Forward Dry Run", dry_status),
    ]
)

st.subheader("Gate Input Status")
show_table_or_missing(gate_inputs, GATE_INPUT_PATH)

st.subheader("Identity Match Report")
show_table_or_missing(identity, IDENTITY_PATH)

st.subheader("Safety Validator")
show_table_or_missing(safety, SAFETY_PATH)

st.subheader("Forward Dry Run")
show_table_or_missing(dry_run, DRY_RUN_PATH)
