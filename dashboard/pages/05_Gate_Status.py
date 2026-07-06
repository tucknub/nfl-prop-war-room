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
ROSTER_MAP_STATUS_PATH = "outputs/roster/current_roster_map_status.csv"
ROLE_MAP_STATUS_PATH = "outputs/roles/current_role_map_status.csv"
INJURY_MAP_STATUS_PATH = "outputs/injuries/current_injury_map_status.csv"
ODDS_MAP_STATUS_PATH = "outputs/odds/current_market_odds_status.csv"


st.set_page_config(page_title="Forward Readiness Gates", layout="wide")
inject_global_styles()
sidebar_status()
page_header("Forward Readiness Gates", "Control-room view of the gates required before forward projection and betting use.", "NO-GO")

gate_inputs = load_csv_safe(GATE_INPUT_PATH)
identity = load_csv_safe(IDENTITY_PATH)
safety = load_csv_safe(SAFETY_PATH)
dry_run = load_csv_safe(DRY_RUN_PATH)
roster_map_status = load_csv_safe(ROSTER_MAP_STATUS_PATH)
role_map_status = load_csv_safe(ROLE_MAP_STATUS_PATH)
injury_map_status = load_csv_safe(INJURY_MAP_STATUS_PATH)
odds_map_status = load_csv_safe(ODDS_MAP_STATUS_PATH)


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
current_roster_status = str(roster_map_status["status"].iloc[0]) if not roster_map_status.empty and "status" in roster_map_status.columns else "NEEDS DATA"

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

section_header("Current Team Verification")
metric_card("Current Roster Map", current_roster_status, current_roster_status, "Forward projections remain blocked until all current teams are verified from real non-template roster data.")
current_role_status = str(role_map_status["status"].iloc[0]) if not role_map_status.empty and "status" in role_map_status.columns else "NEEDS DATA"
metric_card("Current Role Map", current_role_status, current_role_status, "Forward projections remain blocked until real non-template role data is verified.")
current_injury_status = str(injury_map_status["status"].iloc[0]) if not injury_map_status.empty and "status" in injury_map_status.columns else "NEEDS DATA"
metric_card("Current Injury Map", current_injury_status, current_injury_status, "Forward projections remain blocked until real non-template injury and practice data is verified.")
current_odds_status = str(odds_map_status["status"].iloc[0]) if not odds_map_status.empty and "status" in odds_map_status.columns else "NEEDS DATA"
metric_card("Market Odds Map", current_odds_status, current_odds_status, "Betting-edge output remains blocked until real non-template odds are verified.")

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
