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

decision = engine.knockout_decision_summary(state)
risk = decision["roster_risk"]
faab_posture = decision["faab"]

section(
    "What Should I Do?",
    "Decision-first Knockout guidance from the authoritative league state. Structural signals only; no fake survival probability or optimal bid.",
)
decision_cols = st.columns(4)
decision_cols[0].metric("Next action", decision["next_action"])
decision_cols[1].metric("Roster risk", risk["level"])
decision_cols[2].metric("FAAB posture", faab_posture["posture"])
decision_cols[3].metric("Teams alive", decision["teams_alive"])
st.info(f"**WHY:** {decision['why']}")
st.caption(
    f"FAAB remaining: ${faab_posture['remaining']} / ${faab_posture['start']} "
    f"({faab_posture['pct_remaining']:.0%}) · {faab_posture['reason']}"
)

if current_phase != "PRE_DRAFT" and state.get("roster"):
    depth = engine.roster_depth(state)
    depth_cols = st.columns(4)
    depth_cols[0].metric("QB", depth["counts"]["QB"])
    depth_cols[1].metric("RB", depth["counts"]["RB"])
    depth_cols[2].metric("WR", depth["counts"]["WR"])
    depth_cols[3].metric("TE", depth["counts"]["TE"])
    if depth["starter_gaps"]:
        st.error("Missing starter coverage: " + ", ".join(depth["starter_gaps"]))
    elif depth["thin_positions"]:
        st.warning("Thin structural depth: " + ", ".join(depth["thin_positions"]))
    else:
        st.success("Required starter coverage has bench cushion.")

note(
    "NO TRADES is a hard rule in this engine. Roster improvement after the draft comes from waivers/FAAB and the player pool released by eliminated teams."
)

with st.expander("League rules", expanded=False):
    st.caption("Knockout Fantasy is modeled independently from the Margin Pool.")
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

section("Phase strategy", "The objective is survival first; the optimal risk posture changes as the field shrinks.")
for priority in engine.strategy_priorities(state):
    st.markdown(f"- {priority}")

section("Roster state", "Draft intake and every later add/drop stay private and separate from all Margin data.")
roster = list(state.get("roster") or [])
if roster:
    st.success(f"Current roster loaded. {readiness['roster_count']} players are recorded for Week {state['current_week']}.")
    if readiness["ready"]:
        st.caption("Current roster can fill every required starter slot.")
    else:
        st.warning("Roster is saved, but the current lineup is incomplete: " + "; ".join(readiness["lineup_errors"]))
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
            lineup = engine.lineup_readiness(normalized)
            st.success("Roster structure validates: 14 unique players with recognized positions and NFL teams.")
            if lineup["ready"]:
                st.caption("This roster can also fill every required starter slot.")
            else:
                st.warning("Roster can be saved, but starter coverage is incomplete: " + "; ".join(lineup["errors"]))
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
    section("Waiver / FAAB transaction", "Record completed add/drop results only. This does not submit a waiver claim to ESPN.")
    add_col, pos_col, team_col = st.columns([2, 1, 1])
    with add_col:
        add_player = st.text_input("Player added", key="knockout_add_player")
    with pos_col:
        add_position = st.selectbox("Position", ["QB", "RB", "WR", "TE", "K", "DST"], key="knockout_add_position")
    with team_col:
        add_nfl_team = st.text_input("NFL team", max_chars=3, key="knockout_add_team")

    drop_options = [str(row["player"]) for row in roster]
    spend_col, drop_col = st.columns([1, 2])
    with spend_col:
        spend = st.number_input(
            "FAAB spent",
            min_value=0,
            max_value=int(state.get("faab_remaining", 0)),
            value=0,
            step=1,
            key="knockout_faab_spend",
        )
    with drop_col:
        drop_player = st.selectbox("Player dropped", drop_options, key="knockout_drop_player")
    transaction_note = st.text_input("Transaction note", placeholder="Optional context", key="knockout_transaction_note")
    confirm_transaction = st.checkbox(
        "I confirm this add/drop is final and the FAAB amount is correct.", key="knockout_confirm_transaction"
    )
    can_record_transaction = bool(confirm_transaction and add_player.strip() and add_nfl_team.strip())
    if st.button(
        "Record waiver transaction",
        disabled=not can_record_transaction,
        key="knockout_record_transaction",
    ):
        try:
            updated = engine.record_waiver_transaction(
                state,
                amount=int(spend),
                add_player={"player": add_player, "position": add_position, "nfl_team": add_nfl_team},
                drop_player=drop_player,
                note=transaction_note,
            )
            _persist_transition(config, state, updated, f"Record Knockout Week {state['current_week']} waiver transaction")
            st.success("Roster and FAAB ledger updated.")
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

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

latest_elimination = None
if state.get("eliminations"):
    latest_elimination = max(
        state["eliminations"],
        key=lambda row: int(row.get("week", 0)),
    )

if latest_elimination is not None:
    release_week = int(latest_elimination.get("week", 0))
    release_team = str(latest_elimination.get("team") or "").strip()
    released_entry = next(
        (
            row
            for row in state.get("released_rosters") or []
            if int(row.get("week", -1)) == release_week
        ),
        None,
    )

    section(
        "Eliminated roster → waivers",
        "Capture the actual released roster once the elimination is official, then evaluate structural fit against your roster.",
    )
    if released_entry is None:
        st.warning(
            f"Week {release_week}: {release_team} was eliminated, but the released "
            "14-player roster has not been loaded yet."
        )
        release_upload = st.file_uploader(
            "Released roster CSV",
            type=["csv"],
            key=f"knockout_release_upload_{release_week}",
        )
        release_paste = st.text_area(
            "Or paste released roster CSV",
            placeholder="player,position,nfl_team\nPlayer One,RB,IND\n...",
            height=150,
            key=f"knockout_release_paste_{release_week}",
        )
        release_text = ""
        if release_upload is not None:
            release_text = release_upload.getvalue().decode("utf-8-sig")
        elif release_paste.strip():
            release_text = release_paste

        if release_text:
            try:
                parsed_release = _parse_roster_csv(release_text)
                normalized_release = engine.validate_roster(
                    parsed_release,
                    roster_size=int(league["roster_size"]),
                )
                st.success(
                    f"Released roster validates: {len(normalized_release)} players from {release_team}."
                )
                st.dataframe(
                    pd.DataFrame(normalized_release),
                    hide_index=True,
                    width="stretch",
                )
                confirm_release = st.checkbox(
                    f"I confirm this is {release_team}'s full released roster.",
                    key=f"knockout_confirm_release_{release_week}",
                )
                if st.button(
                    f"Save Week {release_week} released roster",
                    type="primary",
                    disabled=not confirm_release,
                    key=f"knockout_save_release_{release_week}",
                ):
                    updated = engine.record_released_roster(
                        state,
                        week=release_week,
                        team=release_team,
                        players=normalized_release,
                    )
                    _persist_transition(
                        config,
                        state,
                        updated,
                        f"Record Knockout Week {release_week} released roster",
                    )
                    st.success("Released roster saved to private Knockout state.")
                    st.rerun()
            except Exception as exc:
                st.error(str(exc))
    else:
        st.success(
            f"Week {release_week} released roster loaded: {release_team}."
        )
        fits = engine.released_roster_fit(state, released_entry)
        if fits:
            st.markdown("**Roster-fit screen**")
            st.dataframe(pd.DataFrame(fits), hide_index=True, width="stretch")
            st.caption(
                "Fit is structural only. It identifies positional need; it does not "
                "rank player quality, project weekly points, or recommend a FAAB bid."
            )

section("Season history", "Private ledger of eliminations, weekly scores, released rosters, and waiver/FAAB moves.")
if state.get("weekly_results"):
    results = pd.DataFrame(state["weekly_results"])
    eliminations = pd.DataFrame(state.get("eliminations") or [])
    history = results.merge(eliminations, on="week", how="left", suffixes=("", "_eliminated"))
    st.dataframe(history, hide_index=True, width="stretch")
else:
    st.caption("No weekly results recorded yet.")

if state.get("faab_transactions"):
    st.markdown("**Waiver / FAAB transactions**")
    st.dataframe(pd.DataFrame(state["faab_transactions"]), hide_index=True, width="stretch")

st.caption(
    "Knockout Decision Center uses authoritative league state, roster structure, field size, FAAB state, and recorded released rosters. "
    "It intentionally does not claim a weekly survival probability, player-quality ranking, or optimal FAAB bid until projection and opponent-field evidence are validated."
)
