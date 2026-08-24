from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PAGE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = PAGE_DIR.parent
REPO_ROOT = DASHBOARD_DIR.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_ui import note, page_intro, section  # noqa: E402
from src.knockout import engine, state_store  # noqa: E402


def _state_config() -> dict[str, str] | None:
    try:
        return state_store.config_from_secrets(st.secrets)
    except Exception:
        return None


def _same_state(a: dict, b: dict) -> bool:
    return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _persist_transition(config: dict[str, str], expected_state: dict, new_state: dict, message: str) -> str:
    remote_state, remote_sha = state_store.fetch_remote_state(config)
    if not _same_state(remote_state, expected_state):
        raise RuntimeError("Authoritative Knockout state changed. Refresh before writing again.")
    return state_store.write_remote_state(config, new_state, expected_sha=remote_sha, message=message)


def _parse_roster_csv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    required = {"player", "position", "nfl_team"}
    headers = set(reader.fieldnames or [])
    missing = sorted(required - headers)
    if missing:
        raise ValueError(f"roster CSV missing columns: {missing}")
    return [dict(row) for row in reader]


page_intro(
    "Knockout Fantasy War Room",
    "Separate 18-team fantasy elimination league. Lowest weekly score is eliminated; eliminated rosters return to waivers. Trades are not allowed.",
)

config = _state_config()
if config is None:
    st.error("Private Knockout state is not configured. The owner private-state repository must be configured first.")
    st.stop()
if not state_store.owner_write_authorized(config):
    st.error("Knockout Fantasy is available only to the authenticated owner.")
    st.stop()

try:
    with st.spinner("Loading private Knockout state..."):
        state, _state_sha = state_store.fetch_remote_state(config)
        engine.validate_state(state)
except Exception as exc:
    st.error("The private Knockout state could not be loaded. No public fallback will be used.")
    st.exception(exc)
    st.stop()

league = state["league"]
readiness = engine.draft_readiness(state)
current_phase = engine.phase(state)
active_teams = engine.active_team_count(state)

st.caption(
    f"State: {current_phase.replace('_', ' ').title()} · Week {int(state.get('current_week', 0))} · "
    f"{active_teams} teams alive · ${int(state.get('faab_remaining', 0))} FAAB · private authoritative state loaded"
)

cols = st.columns(4)
cols[0].metric("Phase", current_phase.replace("_", " ").title())
cols[1].metric("Teams alive", active_teams)
cols[2].metric("FAAB", f"${int(state.get('faab_remaining', 0))}")
cols[3].metric("Roster", f"{len(state.get('roster') or [])}/{int(league['roster_size'])}")

note(
    "NO TRADES is a hard rule in this engine. Roster improvement after the draft comes from waivers/FAAB and the player pool released by eliminated teams."
)

section("League rules", "Knockout Fantasy is modeled independently from the Margin Pool.")
rules = pd.DataFrame(
    [
        ("Teams", league["teams"]),
        ("Scoring", "Full PPR"),
        ("Roster", f"{league['roster_size']} players"),
        ("Starters", "QB · 2 RB · 2 WR · TE · FLEX · K · D/ST"),
        ("FAAB", f"${league['faab_start']} continuous budget"),
        ("Trades", "Not allowed"),
        ("Elimination", "Lowest weekly fantasy score"),
        ("Eliminated roster", "Entire roster released to waivers"),
        ("Elimination weeks", "Weeks 1-17"),
    ],
    columns=["Rule", "Setting"],
)
st.dataframe(rules, hide_index=True, width="stretch")

section("Current strategy", "The objective is survival first; the optimal risk posture changes as the field shrinks.")
for priority in engine.strategy_priorities(state):
    st.markdown(f"- {priority}")

section("Roster state", "Draft intake is private and separate from all Margin data.")
roster = list(state.get("roster") or [])
if roster:
    st.success(f"Draft roster loaded. {readiness['roster_count']} players are recorded for Week {state['current_week']}.")
    st.dataframe(pd.DataFrame(roster), hide_index=True, width="stretch")
else:
    st.info("No roster is loaded yet. This is expected before the draft.")
    st.caption("When the draft is complete, upload or paste exactly 14 rows with columns: player, position, nfl_team.")
    upload = st.file_uploader("Draft roster CSV", type=["csv"], key="knockout_roster_upload")
    pasted = st.text_area(
        "Or paste roster CSV",
        placeholder="player,position,nfl_team\nPlayer One,RB,IND\n...",
        height=150,
        key="knockout_roster_paste",
    )
    raw_text = ""
    if upload is not None:
        raw_text = upload.getvalue().decode("utf-8-sig")
    elif pasted.strip():
        raw_text = pasted

    if raw_text:
        try:
            parsed = _parse_roster_csv(raw_text)
            normalized = engine.validate_roster(parsed, roster_size=int(league["roster_size"]))
            st.success("Roster validates for the league's 14-player lineup requirements.")
            st.dataframe(pd.DataFrame(normalized), hide_index=True, width="stretch")
            confirm = st.checkbox("I confirm this is my final drafted roster.", key="knockout_confirm_draft")
            if st.button("Save draft roster", type="primary", disabled=not confirm, key="knockout_save_draft"):
                updated = engine.record_draft_state(state, normalized)
                _persist_transition(config, state, updated, "Record 2026 Knockout Fantasy draft roster")
                st.success("Draft roster saved to private Knockout state.")
                st.rerun()
        except Exception as exc:
            st.error(str(exc))

if roster and current_phase not in {"ELIMINATED", "CHAMPION"}:
    section("FAAB ledger", "Record only completed waiver spending; this does not place waiver claims.")
    faab_col, note_col = st.columns([1, 3])
    with faab_col:
        spend = st.number_input(
            "FAAB spent",
            min_value=0,
            max_value=int(state.get("faab_remaining", 0)),
            value=0,
            step=1,
            key="knockout_faab_spend",
        )
    with note_col:
        faab_note = st.text_input("Transaction note", placeholder="Player added / waiver result", key="knockout_faab_note")
    confirm_faab = st.checkbox("I confirm this FAAB amount was actually spent.", key="knockout_confirm_faab")
    if st.button("Record FAAB spend", disabled=not confirm_faab or int(spend) <= 0, key="knockout_record_faab"):
        updated = engine.record_faab_spend(state, int(spend), note=faab_note)
        _persist_transition(config, state, updated, f"Record Knockout Week {state['current_week']} FAAB spend")
        st.success("FAAB ledger updated.")
        st.rerun()

    section("Weekly survival result", "Advance the league only after the week's elimination is official.")
    result_col, eliminated_col = st.columns(2)
    with result_col:
        user_score = st.number_input("My fantasy score", min_value=0.0, value=0.0, step=0.1, key="knockout_user_score")
    with eliminated_col:
        eliminated_team = st.text_input("Eliminated fantasy team", key="knockout_eliminated_team")
    user_eliminated = st.checkbox("My team was eliminated this week", key="knockout_user_eliminated")
    confirm_week = st.checkbox("I confirm this week's elimination is final.", key="knockout_confirm_week")
    can_record = bool(confirm_week and eliminated_team.strip())
    if st.button(
        f"Complete Week {int(state['current_week'])}",
        type="primary",
        disabled=not can_record,
        key="knockout_complete_week",
    ):
        updated = engine.record_week_state(
            state,
            user_score=float(user_score),
            eliminated_team=eliminated_team,
            user_eliminated=user_eliminated,
        )
        _persist_transition(config, state, updated, f"Complete Knockout Fantasy Week {state['current_week']}")
        st.success("Weekly Knockout state updated.")
        st.rerun()

section("Season history", "Private ledger of eliminations, weekly scores, and FAAB spending.")
if state.get("weekly_results"):
    results = pd.DataFrame(state["weekly_results"])
    eliminations = pd.DataFrame(state.get("eliminations") or [])
    history = results.merge(eliminations, on="week", how="left", suffixes=("", "_eliminated"))
    st.dataframe(history, hide_index=True, width="stretch")
else:
    st.caption("No weekly results recorded yet.")

if state.get("faab_transactions"):
    st.markdown("**FAAB transactions**")
    st.dataframe(pd.DataFrame(state["faab_transactions"]), hide_index=True, width="stretch")

st.caption(
    "V1 is the league-state foundation. It intentionally does not claim a weekly survival probability or optimal FAAB bid until projection, opponent-field, and waiver-candidate evidence are loaded and validated."
)
