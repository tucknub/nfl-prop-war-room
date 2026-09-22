from __future__ import annotations

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
from src.margin import pdl_sync, state_store  # noqa: E402


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


def _favorite_line(team: object, value: object, digits: int = 1) -> str:
    return f"{str(team)} -{abs(float(value)):.{digits}f}"


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
    "PDL War Room",
    "One-use NFL team allocation for the 2026 Point Differential League. Only the current week's recommendation is actionable; every future slot is provisional.",
    show_data_status=False,
)

state_config = _state_config()
if state_config is None:
    st.error("Private PDL state is not configured. Add the private state repository settings in Streamlit Secrets.")
    st.stop()
if not state_store.owner_write_authorized(state_config):
    st.error("Private PDL state is available only to the authenticated owner.")
    st.stop()
try:
    with st.spinner("Loading private PDL state..."):
        stored_state, _state_sha = state_store.fetch_remote_state(state_config)
except Exception as exc:
    st.error("The private PDL state could not be loaded. No public fallback will be used.")
    st.exception(exc)
    st.stop()

try:
    with st.spinner("Synchronizing the official PDL ledger..."):
        state = pdl_sync.fetch_and_reconcile(stored_state)
        if not _same_state(state, stored_state):
            sync_sha = state_store.write_remote_state(
                state_config, state, expected_sha=_state_sha,
                message=f"Sync PDL state through Week {state['completed_week']}",
            )
            _state_sha = sync_sha or _state_sha
except Exception as exc:
    st.error("PDL league state could not be synchronized. No stale team inventory will be used.")
    st.exception(exc)
    st.stop()

state_text = json.dumps(state, sort_keys=True)

refresh_col, status_col = st.columns([1, 3])
with refresh_col:
    if st.button(f"Refresh Week {state['current_week']} market snapshot", type="primary", width="stretch"):
        _calculate_snapshot.clear()
        st.rerun()
with status_col:
    st.caption(
        f"PDL through Week {state['completed_week']} · Week {state['current_week']} decision · "
        f"score {float(state.get('cumulative_score', 0.0)):+.0f} · {len(state.get('used_teams', []))} teams used · "
        f"synced for {state.get('pdl_sync', {}).get('entrant', 'Ricky T.')}"
    )

try:
    with st.spinner("Rebuilding current board and remaining-season allocation..."):
        audit = _calculate_snapshot(state_text)
except Exception as exc:
    if bool(state.get("season_complete")):
        st.success("The 2026 Point Differential League season is complete.")
        st.stop()
    st.error("The live PDL engine could not produce a valid board.")
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
champ_readiness = championship_info.get("readiness") or {}
minimum_champ_week = int(policy.get("championship_minimum_supported_week", 10) or 10)
if int(state.get("current_week", 0) or 0) < minimum_champ_week:
    missing_settings = set(champ_readiness.get("missing") or [])
    suffix = (
        " First-place tie handling still needs to be confirmed before championship mode activates."
        if "pool.first_place_tie_rule" in missing_settings else ""
    )
    note(
        f"Championship simulation is intentionally inactive until Week {minimum_champ_week}. "
        f"All {int((state.get('pool') or {}).get('size') or 0)} active entrants and "
        f"{len(state.get('opponents') or [])} opponents are synced from PDL. "
        f"The expected-points recommendation is authoritative.{suffix}"
    )
elif champ_status != "READY_FOR_SIMULATION":
    if champ_status in {"UNAVAILABLE_POOL_STATE_MISSING", "UNAVAILABLE_POOL_STATE_INCOMPLETE"}:
        note(
            "Championship simulation is waiting on remaining league settings or field validation. "
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
hero_top[2].metric("Market line", _favorite_line(pick["team"], pick["current_spread"]))
hero_bottom = st.columns(3)
hero_bottom[0].metric("Model mean point differential", _signed(pick["calibrated_margin"]))
hero_bottom[1].metric("Historical loss-rate est.", _pct(pick["p_loss"]))
hero_bottom[2].metric("Historical 20+ est.", _pct(pick["p_win20"]))

st.caption(
    "Spread source: nflverse/nfldata games.csv fetched for this calculation at "
    f"{audit['snapshot_utc']}. nflverse does not expose a per-line change timestamp in this file, "
    "so PropWar does not pretend the spread itself changed at the calculation time. "
    "Point-differential/loss/20+ estimates are empirical 2006–2025 regular-season favorite outcomes weighted toward similar point spreads; they are model estimates, not sportsbook probabilities."
)

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
        commit_cols[2].metric("Market line at refresh", _favorite_line(committed_pick, r.current_spread))
        commit_cols[3].metric("Model mean point differential", _signed(r.calibrated_margin, 2))
    else:
        st.success(f"War Room pick committed: {committed_pick}")
    note(
        f"{committed_pick} is recorded in the War Room for Week {state['current_week']}. "
        "Make sure the same team is submitted on the official PDL site."
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
            f"I confirm this is the official point differential for {committed_pick} in Week {state['current_week']}.",
            key="margin_final_margin_confirm",
        )
        complete_week = st.form_submit_button(
            f"Complete Week {state['current_week']}",
            type="primary",
            disabled=not authorized,
            width="stretch",
        )
    if complete_week and not confirm_final_margin:
        st.warning("Confirm the official point differential before completing the week.")
    elif complete_week:
        try:
            updated_state = state_store.complete_week_state(state, final_margin)
            commit_sha = _persist_transition(
                state_config,
                state,
                updated_state,
                f"Complete PDL Week {state['current_week']}: {committed_pick} {float(final_margin):+g}",
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
                                  f"({_favorite_line(t, available_rows[available_rows.team.eq(t)].iloc[0].current_spread)})",
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
                    f"Change PDL Week {state['current_week']} pick: {committed_pick} to {replacement}",
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
            f"market line {_favorite_line(t, available_rows[available_rows.team.eq(t)].iloc[0].current_spread)} · "
            f"model mean {_signed(available_rows[available_rows.team.eq(t)].iloc[0].calibrated_margin, 2)}"
        ),
        key="margin_commit_team",
    )
    selected_row = available_rows[available_rows.team.eq(selected_team)].iloc[0]
    selection_cols = st.columns(4)
    selection_cols[0].metric("Selected", selected_team)
    selection_cols[1].metric("Opponent", str(selected_row.opponent))
    selection_cols[2].metric("Market line", _favorite_line(selected_team, selected_row.current_spread))
    selection_cols[3].metric("Model mean point differential", _signed(selected_row.calibrated_margin, 2))

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
                f"Commit PDL Week {state['current_week']} pick: {selected_team}",
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
    "Market line": -board["current_spread"].abs(),
    "Model mean point differential": board["calibrated_margin"],
    "Hist loss est.": board["p_loss"] * 100.0,
    "Hist 20+ est.": board["p_win20"] * 100.0,
    "Future cost": board["future_cost"],
    "Season EV Δ": board["total_season_ev_delta_vs_anchor"],
    "Sacrifice": board["current_sacrifice_vs_anchor"],
})
st.dataframe(
    board_display,
    hide_index=True,
    width="stretch",
    column_config={
        "Market line": st.column_config.NumberColumn(format="%+.1f"),
        "Model mean point differential": st.column_config.NumberColumn(format="%+.2f"),
        "Hist loss est.": st.column_config.NumberColumn(format="%.1f%%"),
        "Hist 20+ est.": st.column_config.NumberColumn(format="%.1f%%"),
        "Future cost": st.column_config.NumberColumn(format="%.2f"),
        "Season EV Δ": st.column_config.NumberColumn(format="%+.2f"),
        "Sacrifice": st.column_config.NumberColumn(format="%.1f"),
    },
)

top_three = board.sort_values(["total_season_ev", "current_spread"], ascending=[False, False]).head(3)
for rank, (_, row) in enumerate(top_three.iterrows(), start=1):
    st.markdown(
        f"**{rank}. {row['team']} vs {row['opponent']}** — {row['team']} -{abs(float(row['current_spread'])):.1f} market line · "
        f"{row['calibrated_margin']:+.2f} model mean · {_pct(row['p_loss'])} hist loss est. · {_pct(row['p_win20'])} hist 20+ est. · "
        f"{row['status']}"
    )

section("Provisional remaining route", "Reservation map only. Posted look-ahead lines outrank market-power forecasts while they genuinely exist.")
route = pd.DataFrame(audit["route"]).copy()
route_display = pd.DataFrame({
    "Week": route["week"].astype(int),
    "Team": route["team"],
    "Opp": route["opponent"],
    "Favorite line": -route["raw_value_spread"].abs(),
    "Model mean point differential": route["calibrated_ev"],
    "Source": route["value_source"].map(_friendly_source),
})
st.dataframe(
    route_display,
    hide_index=True,
    width="stretch",
    column_config={
        "Favorite line": st.column_config.NumberColumn(format="%+.2f"),
        "Model mean point differential": st.column_config.NumberColumn(format="%+.2f"),
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
pdl_meta = state.get("pdl_sync") or {}
note(
    f"League ledger: pdl.kingtuddy.com · {len(state.get('opponents', [])) + 1} active entrants · "
    f"fingerprint {str(pdl_meta.get('data_fingerprint_sha256') or 'unavailable')[:12]}…"
)

history = pd.DataFrame(state.get("weekly_results", []))
if not history.empty:
    st.markdown("#### Completed picks")
    st.dataframe(history, hide_index=True, width="stretch")
else:
    st.caption("No 2026 Point Differential League picks have been completed yet.")

section("PDL sync status", "League state is synchronized automatically from pdl.kingtuddy.com.")
pool = state.get("pool") or {}
readiness = championship_info.get("readiness") or {}
sync_cols = st.columns(4)
sync_cols[0].metric("Active entrants", int(pool.get("size") or 0))
sync_cols[1].metric("Opponents synced", len(state.get("opponents") or []))
sync_cols[2].metric("Weeks graded", int(state.get("completed_week") or 0))
sync_cols[3].metric("Championship starts", f"Week {int(readiness.get('minimum_supported_week') or 10)}")
missing = list(readiness.get("missing") or [])
if missing == ["pool.first_place_tie_rule"]:
    st.caption("Only the first-place tie-handling rule remains to be confirmed before championship simulation becomes eligible in Week 10.")
elif missing:
    st.caption("Championship setup still needs: " + ", ".join(str(x) for x in missing))
else:
    st.caption("PDL field and championship settings are complete.")

section("Data quality", "What the engine actually had available for this calculation.")
quality_cols = st.columns(4)
quality_cols[0].metric("Current games", int(data_quality["current_week_games"]))
quality_cols[1].metric("Current spreads", int(data_quality["current_week_posted_spreads"]))
quality_cols[2].metric("Season games", int(data_quality["season_games"]))
quality_cols[3].metric("Market HFA", f"{float(data_quality['fallback_hfa']):.2f}")
with st.expander("Source mix and technical status"):
    displayed_champ_status = (
        f"INACTIVE_UNTIL_WEEK_{minimum_champ_week}"
        if int(state.get("current_week", 0) or 0) < minimum_champ_week
        else policy.get("championship_status")
    )
    st.json({
        "market_snapshot": audit["snapshot_utc"],
        "championship_status": displayed_champ_status,
        "championship_readiness_missing": championship_info.get("readiness", {}).get("missing", []),
        "pdl_active_entrants": int((state.get("pool") or {}).get("size") or 0),
        "pdl_opponents_synced": len(state.get("opponents") or []),
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

source_footer("Source: nflverse/nfldata games.csv for schedule and spread snapshots. Current-week rows require a posted nflverse spread; future unpriced games use PropWar's market-power allocator. Point-differential/loss/20+ values are historical spread-conditioned model estimates, not factual outcomes or sportsbook probabilities.")
