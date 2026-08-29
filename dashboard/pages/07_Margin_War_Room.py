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

from research_ui import note, page_intro, section, source_footer  # noqa: E402
from src.margin import live_engine_v2 as margin_live  # noqa: E402
from src.margin import pool_state, state_store  # noqa: E402


NFL_TEAMS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LA", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
]


@st.cache_data(ttl=300, show_spinner=False)
def _calculate_snapshot(state_text: str) -> dict:
    return margin_live.run(json.loads(state_text), future_posted_mode="live")


def _pct(value: float) -> str:
    return f"{float(value) * 100:.1f}%"


def _signed(value: float, digits: int = 1) -> str:
    return f"{float(value):+.{digits}f}"


def _friendly_source(value: str) -> str:
    return {
        "CURRENT_MARKET": "Current market",
        "POSTED_LOOKAHEAD": "Posted look-ahead",
        "MARKET_POWER_FORECAST": "Market-power forecast",
        "MARKET_RATING_INFERRED": "Early market forecast",
    }.get(str(value), str(value).replace("_", " ").title())


def _render_inventory(used: set[str]) -> None:
    cols = st.columns(4)
    chunks = [NFL_TEAMS[i::4] for i in range(4)]
    for col, chunk in zip(cols, chunks):
        with col:
            for team in chunk:
                status = "USED" if team in used else "available"
                prefix = "✓" if team in used else "·"
                st.markdown(f"**{prefix} {team}**  \n{status}")


def _field_rows_from_csv_text(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    required = {"id", "name", "cumulative_score", "used_teams"}
    headers = set(reader.fieldnames or [])
    missing = sorted(required - headers)
    if missing:
        raise ValueError(f"field CSV missing columns: {missing}")
    rows = list(reader)
    if not rows:
        raise ValueError("field CSV must include at least one opponent row")
    return rows


def _current_select_index(options: list[str], value: object) -> int:
    text = str(value or "Unknown")
    return options.index(text) if text in options else 0


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
        raise RuntimeError("Authoritative private state changed. Refresh the page before writing again.")
    return state_store.write_remote_state(
        config,
        new_state,
        expected_sha=remote_sha,
        message=message,
    )


page_intro(
    "Margin War Room",
    "One-use NFL team allocation for the 2026 Margin Pool. Only the current week's recommendation is actionable; every future slot is provisional.",
)

state_config = _state_config()
if state_config is None:
    st.error("Private Margin state is not configured. Add the private state repository settings in Streamlit Secrets.")
    st.stop()
if not state_store.owner_write_authorized(state_config):
    st.error("Private Margin state is available only to the authenticated owner.")
    st.stop()
try:
    with st.spinner("Loading private Margin state..."):
        state, _state_sha = state_store.fetch_remote_state(state_config)
except Exception as exc:
    st.error("The private Margin state could not be loaded. No public fallback will be used.")
    st.exception(exc)
    st.stop()

state_text = json.dumps(state, sort_keys=True)

refresh_col, status_col = st.columns([1, 3])
with refresh_col:
    if st.button("Refresh live markets", type="primary", width="stretch"):
        _calculate_snapshot.clear()
        st.rerun()
with status_col:
    st.caption(
        f"State: Week {state['current_week']} · score {float(state.get('cumulative_score', 0.0)):+.0f} · "
        f"{len(state.get('used_teams', []))} teams used · private authoritative state loaded"
    )

try:
    with st.spinner("Rebuilding current board and remaining-season allocation..."):
        audit = _calculate_snapshot(state_text)
except Exception as exc:
    if bool(state.get("season_complete")):
        st.success("The 2026 Margin Pool season is complete.")
        st.stop()
    st.error("The live Margin engine could not produce a valid board.")
    st.exception(exc)
    st.stop()

pick = audit["pick"]
anchor = audit["anchor"]
policy = audit["policy"]
data_quality = audit["data_quality"]
championship_info = audit.get("championship") or {}
used = set(str(x) for x in audit.get("used_teams", []))
raw_board = pd.DataFrame(audit["board"]).copy()

champ_status = str(policy.get("championship_status", ""))
override_applied = bool(policy.get("championship_override_applied", False))
if champ_status != "READY_FOR_SIMULATION":
    if champ_status == "UNAVAILABLE_EARLY_SEASON_RESEARCH_GATE":
        note(
            f"Championship override is promoted but intentionally inactive before Week "
            f"{policy.get('championship_minimum_supported_week', 10)}. The expected-points recommendation is authoritative."
        )
    elif champ_status in {"UNAVAILABLE_POOL_STATE_MISSING", "UNAVAILABLE_POOL_STATE_INCOMPLETE"}:
        note(
            "Championship override is promoted but inactive until the complete pool field is loaded: "
            "pool size/tie rule plus every opponent's score and burned-team inventory. "
            "The expected-points recommendation is authoritative."
        )
    else:
        note(
            "Championship override is blocked because the loaded pool state is invalid. "
            "The expected-points recommendation remains authoritative until the state is corrected.",
            amber=True,
        )
elif override_applied:
    sim = championship_info.get("simulation") or {}
    confirmation = championship_info.get("confirmation") or {}
    note(
        f"Championship override ACTIVE: {policy.get('expected_points_pick')} → {pick['team']}. "
        f"Primary first-place-share lift is {float(sim.get('first_share_lift', 0.0)) * 100:+.1f} pp; "
        f"independent confirmation mean is {float(confirmation.get('mean_first_share_lift', 0.0)) * 100:+.1f} pp "
        f"with a minimum seed lift of {float(confirmation.get('minimum_first_share_lift', 0.0)) * 100:+.1f} pp."
    )
else:
    note(
        "Championship mode evaluated the complete field and retained the expected-points pick. "
        f"Gate result: {str(policy.get('championship_override_status', '')).replace('_', ' ').title()}."
    )

section("Current recommendation", "Refresh near the pool deadline, then record the team you actually submit to the league.")
hero_top = st.columns(3)
hero_top[0].metric("RECOMMENDED", str(pick["team"]))
hero_top[1].metric("Opponent", str(pick["opponent"]))
hero_top[2].metric("Current spread", _signed(pick["current_spread"]))
hero_bottom = st.columns(3)
hero_bottom[0].metric("Expected margin", _signed(pick["calibrated_margin"]))
hero_bottom[1].metric("Loss probability", _pct(pick["p_loss"]))
hero_bottom[2].metric("20+ probability", _pct(pick["p_win20"]))

if override_applied:
    note(
        f"Championship-driven recommendation: {pick['team']} replaces expected-points choice {policy.get('expected_points_pick')}. "
        f"Current spread sacrifice versus the anchor is {pick['current_sacrifice_vs_anchor']:.1f} points."
    )
elif str(pick["team"]) == str(anchor["team"]):
    note(
        f"Anchor retained: {pick['team']} is the largest current favorite and the engine finds no qualifying reason to deviate. "
        f"Future opportunity cost is {pick['future_cost']:.2f} expected points."
    )
else:
    note(
        f"Allocator deviation: {pick['team']} is preferred over anchor {anchor['team']}. "
        f"Current spread sacrifice is {pick['current_sacrifice_vs_anchor']:.1f} points and total-season EV delta is "
        f"{pick['total_season_ev_delta_vs_anchor']:+.2f}."
    )

policy_cols = st.columns(3)
policy_cols[0].metric("Anchor", str(anchor["team"]))
policy_cols[1].metric("Future cost", f"{pick['future_cost']:.2f}")
policy_cols[2].metric("Season EV Δ vs anchor", f"{pick['total_season_ev_delta_vs_anchor']:+.2f}")

section("This week's pick", "Record your actual pool selection here. This does not submit the pick to the external league site.")
authorized = True
decision = state.get("current_decision") or {}
committed_pick = str(decision.get("committed_pick") or "") if str(decision.get("status")) == "COMMITTED" else ""

if committed_pick:
    committed_row = raw_board[raw_board.team.astype(str).eq(committed_pick)]
    if not committed_row.empty:
        r = committed_row.iloc[0]
        commit_cols = st.columns(4)
        commit_cols[0].metric("COMMITTED", committed_pick)
        commit_cols[1].metric("Opponent", str(r.opponent))
        commit_cols[2].metric("Spread at refresh", _signed(r.current_spread))
        commit_cols[3].metric("Expected margin", _signed(r.calibrated_margin, 2))
    else:
        st.success(f"War Room pick committed: {committed_pick}")
    note(
        f"{committed_pick} is recorded in the War Room for Week {state['current_week']}. "
        "Make sure the same team is submitted on the official Margin Pool site."
    )

    with st.form("margin_week_completion_form", clear_on_submit=False):
        final_margin = st.number_input(
            "Final point differential",
            step=1.0,
            value=0.0,
            help="Example: team wins 27-20 = +7; loses 17-24 = -7.",
            key="margin_final_margin",
        )
        confirm_final_margin = st.checkbox(
            f"I confirm this is the official final margin for {committed_pick} in Week {state['current_week']}.",
            key="margin_final_margin_confirm",
        )
        complete_week = st.form_submit_button(
            f"Complete Week {state['current_week']}",
            type="primary",
            disabled=not authorized,
            width="stretch",
        )
    if complete_week and not confirm_final_margin:
        st.warning("Confirm the official final margin before completing the week.")
    elif complete_week:
        try:
            updated_state = state_store.complete_week_state(state, final_margin)
            commit_sha = _persist_transition(
                state_config,
                state,
                updated_state,
                f"Complete Margin Week {state['current_week']}: {committed_pick} {float(final_margin):+g}",
            )
            _calculate_snapshot.clear()
            st.success(f"Week completed and saved to private state ({commit_sha[:8]}). Advancing the War Room.")
            st.rerun()
        except Exception as exc:
            st.error(f"Week completion was not saved: {exc}")

    with st.expander("Change the recorded team before the deadline"):
        available_rows = raw_board[~raw_board.team.astype(str).isin(used)].sort_values(
            ["current_spread", "total_season_ev"], ascending=[False, False]
        )
        change_options = available_rows.team.astype(str).tolist()
        change_index = change_options.index(committed_pick) if committed_pick in change_options else 0
        replacement = st.selectbox(
            "Replacement team",
            change_options,
            index=change_index,
            format_func=lambda t: f"{t} vs {available_rows[available_rows.team.eq(t)].iloc[0].opponent} "
                                  f"({_signed(available_rows[available_rows.team.eq(t)].iloc[0].current_spread)})",
            key="margin_replace_team",
        )
        replace_pick = st.button(
            "Replace recorded pick",
            disabled=not authorized or replacement == committed_pick,
            key="margin_replace_pick",
        )
        if replace_pick:
            try:
                updated_state = state_store.commit_pick_state(state, audit, replacement)
                commit_sha = _persist_transition(
                    state_config,
                    state,
                    updated_state,
                    f"Change Margin Week {state['current_week']} pick: {committed_pick} to {replacement}",
                )
                _calculate_snapshot.clear()
                st.success(f"Recorded pick changed to {replacement} ({commit_sha[:8]}).")
                st.rerun()
            except Exception as exc:
                st.error(f"Pick change was not saved: {exc}")
else:
    available_rows = raw_board[~raw_board.team.astype(str).isin(used)].sort_values(
        ["current_spread", "total_season_ev"], ascending=[False, False]
    )
    team_options = available_rows.team.astype(str).tolist()
    default_team = str(pick["team"])
    default_index = team_options.index(default_team) if default_team in team_options else 0
    selected_team = st.selectbox(
        "Team to record",
        team_options,
        index=default_index,
        format_func=lambda t: (
            f"{t} vs {available_rows[available_rows.team.eq(t)].iloc[0].opponent} · "
            f"spread {_signed(available_rows[available_rows.team.eq(t)].iloc[0].current_spread)} · "
            f"expected {_signed(available_rows[available_rows.team.eq(t)].iloc[0].calibrated_margin, 2)}"
        ),
        key="margin_commit_team",
    )
    selected_row = available_rows[available_rows.team.eq(selected_team)].iloc[0]
    selection_cols = st.columns(4)
    selection_cols[0].metric("Selected", selected_team)
    selection_cols[1].metric("Opponent", str(selected_row.opponent))
    selection_cols[2].metric("Spread", _signed(selected_row.current_spread))
    selection_cols[3].metric("Expected margin", _signed(selected_row.calibrated_margin, 2))

    acknowledge = st.checkbox(
        "I understand this records my War Room state only; I still submit the official pick on the pool site.",
        key="margin_commit_ack",
    )
    commit_pick = st.button(
        f"Commit {selected_team} for Week {state['current_week']}",
        type="primary",
        disabled=not (authorized and acknowledge),
        width="stretch",
        key="margin_commit_pick",
    )
    if commit_pick:
        try:
            updated_state = state_store.commit_pick_state(state, audit, selected_team)
            commit_sha = _persist_transition(
                state_config,
                state,
                updated_state,
                f"Commit Margin Week {state['current_week']} pick: {selected_team}",
            )
            _calculate_snapshot.clear()
            st.success(f"{selected_team} recorded and saved to private state ({commit_sha[:8]}).")
            st.rerun()
        except Exception as exc:
            st.error(f"Pick was not saved: {exc}")

section("Weekly board", "Unused teams ranked from current market value through remaining-season opportunity cost.")
board = raw_board.copy()
status_order = {"PICK": 0, "ANCHOR": 1, "SAVE/PIVOT": 2, "WATCH": 3, "AVOID_CAP": 4}
board["_status_order"] = board["status"].map(status_order).fillna(9)
board = board.sort_values(["_status_order", "total_season_ev", "current_spread"], ascending=[True, False, False])
show_all = st.toggle("Show underdogs and cap-rejected teams", value=False)
if not show_all:
    board = board[(board["current_spread"] > 0) & ~board["status"].eq("AVOID_CAP")].head(12)
else:
    board = board.head(32)

board_display = pd.DataFrame({
    "Status": board["status"],
    "Team": board["team"],
    "Opp": board["opponent"],
    "Spread": board["current_spread"],
    "Exp margin": board["calibrated_margin"],
    "P(loss)": board["p_loss"] * 100.0,
    "P(20+)": board["p_win20"] * 100.0,
    "Future cost": board["future_cost"],
    "Season EV Δ": board["total_season_ev_delta_vs_anchor"],
    "Sacrifice": board["current_sacrifice_vs_anchor"],
})
st.dataframe(
    board_display,
    hide_index=True,
    width="stretch",
    column_config={
        "Spread": st.column_config.NumberColumn(format="%+.1f"),
        "Exp margin": st.column_config.NumberColumn(format="%+.2f"),
        "P(loss)": st.column_config.NumberColumn(format="%.1f%%"),
        "P(20+)": st.column_config.NumberColumn(format="%.1f%%"),
        "Future cost": st.column_config.NumberColumn(format="%.2f"),
        "Season EV Δ": st.column_config.NumberColumn(format="%+.2f"),
        "Sacrifice": st.column_config.NumberColumn(format="%.1f"),
    },
)

top_three = board.sort_values(["total_season_ev", "current_spread"], ascending=[False, False]).head(3)
for rank, (_, row) in enumerate(top_three.iterrows(), start=1):
    st.markdown(
        f"**{rank}. {row['team']} vs {row['opponent']}** — {row['current_spread']:+.1f} spread · "
        f"{row['calibrated_margin']:+.2f} expected · {_pct(row['p_loss'])} loss · {_pct(row['p_win20'])} 20+ · "
        f"{row['status']}"
    )

section("Provisional remaining route", "Reservation map only. Posted look-ahead lines outrank market-power forecasts while they genuinely exist.")
route = pd.DataFrame(audit["route"]).copy()
route_display = pd.DataFrame({
    "Week": route["week"].astype(int),
    "Team": route["team"],
    "Opp": route["opponent"],
    "Projected spread": route["raw_value_spread"],
    "Calibrated EV": route["calibrated_ev"],
    "Source": route["value_source"].map(_friendly_source),
})
st.dataframe(
    route_display,
    hide_index=True,
    width="stretch",
    column_config={
        "Projected spread": st.column_config.NumberColumn(format="%+.2f"),
        "Calibrated EV": st.column_config.NumberColumn(format="%+.2f"),
    },
)
note("Do not follow this route blindly. After every completed week, the remaining route is deleted and rebuilt.", amber=True)

section("My pool state", "Authoritative state is loaded from and written to the private state repository.")
state_cols = st.columns(4)
state_cols[0].metric("Current week", int(state["current_week"]))
state_cols[1].metric("Cumulative score", f"{float(state.get('cumulative_score', 0.0)):+.0f}")
state_cols[2].metric("Teams used", len(used))
state_cols[3].metric("Teams remaining", 32 - len(used))
_render_inventory(used)

history = pd.DataFrame(state.get("weekly_results", []))
if not history.empty:
    st.markdown("#### Completed picks")
    st.dataframe(history, hide_index=True, width="stretch")
else:
    st.caption("No 2026 Margin Pool picks have been completed yet.")

section(
    "Pool field preview",
    "Validate real standings and burned-team inventories, then preview the recommendation without changing authoritative private state.",
)
note(
    "Preview only: this section does not replace the authoritative field until its validated snapshot is persisted. "
    "Pick/result controls above write only to the private owner state.",
    amber=True,
)

pool = state.get("pool") or {}
with st.form("margin_pool_preview_form", clear_on_submit=False):
    meta_a, meta_b, meta_c = st.columns(3)
    with meta_a:
        preview_pool_name = st.text_input("Pool name", value=str(pool.get("name") or ""), key="margin_preview_pool_name")
        preview_pool_size = st.number_input(
            "Entrants (0 = infer from rows)",
            min_value=0,
            step=1,
            value=int(pool.get("size") or 0),
            key="margin_preview_pool_size",
        )
    with meta_b:
        tie_options = ["Unknown", "split", "shared"]
        preview_tie_rule = st.selectbox(
            "First-place tie rule",
            tie_options,
            index=_current_select_index(tie_options, pool.get("first_place_tie_rule")),
            key="margin_preview_tie_rule",
        )
        visibility_options = ["Unknown", "hidden", "visible"]
        current_visibility = pool.get("picks_visible_before_deadline")
        visibility_default = "visible" if current_visibility is True else "hidden" if current_visibility is False else "Unknown"
        preview_visibility = st.selectbox(
            "Picks before deadline",
            visibility_options,
            index=_current_select_index(visibility_options, visibility_default),
            key="margin_preview_visibility",
        )
    with meta_c:
        preview_deadline = st.text_input(
            "Pick deadline",
            value=str(pool.get("pick_deadline") or ""),
            placeholder="e.g. Sunday 12:55 PM ET",
            key="margin_preview_deadline",
        )
        st.text_input(
            "Payout structure",
            value=str(pool.get("payout_structure") or "winner_take_all"),
            disabled=True,
            key="margin_preview_payout",
        )

    uploaded_field = st.file_uploader(
        "Opponent field CSV",
        type=["csv"],
        help="Required columns: id, name, cumulative_score, used_teams",
        key="margin_preview_upload",
    )
    pasted_field = st.text_area(
        "Or paste the same CSV",
        height=120,
        placeholder="id,name,cumulative_score,used_teams\nopp-1,Team A,42,KC|BUF",
        key="margin_preview_paste",
    )
    field_text = uploaded_field.getvalue().decode("utf-8-sig") if uploaded_field is not None else pasted_field
    validate_preview = st.form_submit_button("Validate & preview field")

if validate_preview and not field_text.strip():
    st.warning("Add or paste the opponent field CSV before validating.")
elif validate_preview:
    try:
        raw_rows = _field_rows_from_csv_text(field_text)
        opponents = pool_state.normalize_opponents(raw_rows, int(state.get("completed_week", 0) or 0))
        visibility_value = True if preview_visibility == "visible" else False if preview_visibility == "hidden" else None
        preview_state, readiness = pool_state.apply_pool_snapshot(
            state,
            opponents,
            pool_name=preview_pool_name.strip() or None,
            first_place_tie_rule=None if preview_tie_rule == "Unknown" else preview_tie_rule,
            pick_deadline=preview_deadline.strip() or None,
            picks_visible_before_deadline=visibility_value,
            explicit_pool_size=None if int(preview_pool_size) == 0 else int(preview_pool_size),
            payout_structure="winner_take_all",
        )
        st.session_state["margin_pool_preview_state"] = json.dumps(preview_state, sort_keys=True)
        st.session_state["margin_pool_preview_base_state"] = state_text
        st.success(
            f"Field validated: {len(opponents) + 1} entrants. Championship readiness: {readiness['status']}."
        )
    except Exception as exc:
        st.session_state.pop("margin_pool_preview_state", None)
        st.session_state.pop("margin_pool_preview_base_state", None)
        st.error(f"Field preview rejected: {exc}")

preview_state_text = st.session_state.get("margin_pool_preview_state")
if preview_state_text and st.session_state.get("margin_pool_preview_base_state") != state_text:
    st.session_state.pop("margin_pool_preview_state", None)
    st.session_state.pop("margin_pool_preview_base_state", None)
    preview_state_text = None
    st.warning("The authoritative state changed since this preview was built. Reload the field before using it.")

if preview_state_text:
    try:
        preview_state = json.loads(preview_state_text)
        preview_audit = _calculate_snapshot(preview_state_text)
        preview_policy = preview_audit["policy"]
        preview_pick = preview_audit["pick"]
        preview_opponents = preview_state.get("opponents", [])

        preview_metrics = st.columns(4)
        preview_metrics[0].metric("Preview entrants", int((preview_state.get("pool") or {}).get("size") or 0))
        preview_metrics[1].metric("Preview opponents", len(preview_opponents))
        preview_metrics[2].metric("Championship status", str(preview_policy.get("championship_status", "")))
        preview_metrics[3].metric("Preview PICK", str(preview_pick["team"]))

        if bool(preview_policy.get("championship_override_applied", False)):
            note(
                f"Preview championship override: {preview_policy.get('expected_points_pick')} → {preview_pick['team']}. "
                "This is not authoritative until the validated field snapshot is persisted."
            )
        elif str(preview_policy.get("championship_status", "")) == "READY_FOR_SIMULATION":
            note(
                f"Preview complete field evaluated and retained expected-points pick {preview_pick['team']}. "
                "This is not authoritative until the snapshot is persisted."
            )
        else:
            note(
                f"Preview pick remains {preview_pick['team']}. Championship status: "
                f"{str(preview_policy.get('championship_status', '')).replace('_', ' ').title()}."
            )

        if preview_opponents:
            st.dataframe(pd.DataFrame(preview_opponents), hide_index=True, width="stretch")

        pretty_preview_state = json.dumps(preview_state, indent=2) + "\n"
        st.download_button(
            "Download validated state JSON",
            data=pretty_preview_state,
            file_name="margin_live_state_2026_validated_preview.json",
            mime="application/json",
            key="margin_preview_download",
        )
        with st.form("margin_pool_preview_persist_form", clear_on_submit=False):
            confirm_pool_field = st.checkbox(
                "I confirm the pool standings, scores, and burned-team inventories match the official Margin Pool.",
                key="margin_preview_persist_confirm",
            )
            save_validated_field = st.form_submit_button(
                "Save validated field to Margin state",
                type="primary",
                disabled=not authorized,
                width="stretch",
            )

        if save_validated_field and not confirm_pool_field:
            st.warning("Confirm the validated field matches the official Margin Pool before saving.")
        elif save_validated_field:
            try:
                preview_base_state = json.loads(st.session_state["margin_pool_preview_base_state"])
                commit_sha = _persist_transition(
                    state_config,
                    preview_base_state,
                    preview_state,
                    f"Save validated Margin pool field for Week {state['current_week']}",
                )
                _calculate_snapshot.clear()
                st.session_state.pop("margin_pool_preview_state", None)
                st.session_state.pop("margin_pool_preview_base_state", None)
                st.success(f"Validated field saved to private Margin state ({commit_sha[:8]}).")
                st.rerun()
            except Exception as exc:
                st.error(f"Validated field was not saved: {exc}")

        if st.button("Clear field preview", key="margin_preview_clear"):
            st.session_state.pop("margin_pool_preview_state", None)
            st.session_state.pop("margin_pool_preview_base_state", None)
            st.rerun()
    except Exception as exc:
        st.error(f"Validated field could not produce a preview decision: {exc}")

section("Data quality", "What the engine actually had available for this calculation.")
quality_cols = st.columns(4)
quality_cols[0].metric("Current games", int(data_quality["current_week_games"]))
quality_cols[1].metric("Current spreads", int(data_quality["current_week_posted_spreads"]))
quality_cols[2].metric("Season games", int(data_quality["season_games"]))
quality_cols[3].metric("Market HFA", f"{float(data_quality['fallback_hfa']):.2f}")
with st.expander("Source mix and technical status"):
    st.json({
        "market_snapshot": audit["snapshot_utc"],
        "championship_status": policy.get("championship_status"),
        "championship_override_promoted": policy.get("championship_override_promoted"),
        "championship_override_applied": policy.get("championship_override_applied"),
        "championship_override_status": policy.get("championship_override_status"),
        "championship_primary_lift_threshold": policy.get("championship_primary_lift_threshold"),
        "championship_confirmation_seeds": policy.get("championship_confirmation_seeds"),
        "future_forecast_status": data_quality.get("future_forecast_status"),
        "future_forecast_model": data_quality.get("future_forecast_model"),
        "style_numeric_override": policy.get("style_numeric_override"),
        "value_source_counts": data_quality.get("remaining_value_source_counts", {}),
        "posted_market_games_used_for_fallback": data_quality.get("snapshot_posted_market_games_used_for_fallback"),
        "power_window_periods": data_quality.get("power_window_periods"),
        "power_half_life": data_quality.get("power_half_life"),
        "power_ridge": data_quality.get("power_ridge"),
        "anchor_ev_threshold": policy.get("anchor_ev_threshold"),
        "current_spread_sacrifice_cap": policy.get("current_spread_sacrifice_cap"),
    })

source_footer("NFL schedule/market data: nflverse. Current games use posted market; future unpriced games use the validated V1 market-power allocator.")
