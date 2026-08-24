from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st


PAGE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = PAGE_DIR.parent
REPO_ROOT = DASHBOARD_DIR.parent
MARGIN_DIR = REPO_ROOT / "research" / "margin_v1"
for path in (DASHBOARD_DIR, MARGIN_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from research_ui import note, page_intro, section, source_footer  # noqa: E402
import run_live_margin_2026 as margin_live  # noqa: E402


NFL_TEAMS = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LAC", "LA", "LV", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
]


@st.cache_data(ttl=300, show_spinner=False)
def _calculate_snapshot(state_text: str) -> dict:
    state = json.loads(state_text)
    return margin_live.run(state, future_posted_mode="live")


def _pct(value: float) -> str:
    return f"{float(value) * 100:.1f}%"


def _signed(value: float, digits: int = 1) -> str:
    return f"{float(value):+.{digits}f}"


def _friendly_source(value: str) -> str:
    return {
        "CURRENT_MARKET": "Current market",
        "POSTED_LOOKAHEAD": "Posted look-ahead",
        "MARKET_RATING_INFERRED": "Model forecast",
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


page_intro(
    "Margin War Room",
    "One-use NFL team allocation for the 2026 Margin Pool. Only the current week's recommendation is actionable; every future slot is provisional.",
)

state_text = margin_live.DEFAULT_STATE.read_text(encoding="utf-8")
state = json.loads(state_text)

refresh_col, status_col = st.columns([1, 3])
with refresh_col:
    if st.button("Refresh live markets", type="primary", use_container_width=True):
        _calculate_snapshot.clear()
        st.rerun()
with status_col:
    st.caption(
        f"State: Week {state['current_week']} · score {float(state.get('cumulative_score', 0.0)):+.0f} · "
        f"{len(state.get('used_teams', []))} teams used · read-only dashboard"
    )

try:
    with st.spinner("Rebuilding current board and remaining-season allocation..."):
        audit = _calculate_snapshot(state_text)
except Exception as exc:
    st.error("The live Margin engine could not produce a valid board.")
    st.exception(exc)
    st.stop()

pick = audit["pick"]
anchor = audit["anchor"]
policy = audit["policy"]
data_quality = audit["data_quality"]
used = set(str(x) for x in audit.get("used_teams", []))

if policy.get("championship_status") != "READY_FOR_SIMULATION":
    note(
        "Championship mode is not active yet because pool size/opponent inventories have not been loaded. "
        "The expected-points recommendation below is authoritative for now."
    )

section("Current decision", "The answer first. Refresh near the pool deadline before committing the pick.")
hero = st.columns(6)
hero[0].metric("PICK", str(pick["team"]))
hero[1].metric("Opponent", str(pick["opponent"]))
hero[2].metric("Current spread", _signed(pick["current_spread"]))
hero[3].metric("Expected margin", _signed(pick["calibrated_margin"]))
hero[4].metric("Loss probability", _pct(pick["p_loss"]))
hero[5].metric("20+ probability", _pct(pick["p_win20"]))

if str(pick["team"]) == str(anchor["team"]):
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

policy_cols = st.columns(4)
policy_cols[0].metric("Anchor", str(anchor["team"]))
policy_cols[1].metric("Future cost", f"{pick['future_cost']:.2f}")
policy_cols[2].metric("Season EV Δ vs anchor", f"{pick['total_season_ev_delta_vs_anchor']:+.2f}")
policy_cols[3].metric("Policy", str(policy.get("pick_reason", "")).replace("_", " ").title())

section("Weekly board", "Unused teams ranked from the current market through remaining-season opportunity cost.")
board = pd.DataFrame(audit["board"]).copy()
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
    "P(loss)": board["p_loss"],
    "P(20+)": board["p_win20"],
    "Future cost": board["future_cost"],
    "Season EV Δ": board["total_season_ev_delta_vs_anchor"],
    "Sacrifice": board["current_sacrifice_vs_anchor"],
})
st.dataframe(
    board_display,
    hide_index=True,
    use_container_width=True,
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
st.caption("Probability columns are shown as decimals by the engine and formatted as percentages in the table.")

# Streamlit's percentage NumberColumn expects already-percent values for the desired visible scale.
# Render a compact human-readable top-three beneath the full analytical table.
top_three = board.sort_values(["total_season_ev", "current_spread"], ascending=[False, False]).head(3)
for rank, (_, row) in enumerate(top_three.iterrows(), start=1):
    st.markdown(
        f"**{rank}. {row['team']} vs {row['opponent']}** — {row['current_spread']:+.1f} spread · "
        f"{row['calibrated_margin']:+.2f} expected · {_pct(row['p_loss'])} loss · {_pct(row['p_win20'])} 20+ · "
        f"{row['status']}"
    )

section("Provisional remaining route", "Reservation map only. Posted look-ahead lines outrank model forecasts while they genuinely exist.")
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
    use_container_width=True,
    column_config={
        "Projected spread": st.column_config.NumberColumn(format="%+.2f"),
        "Calibrated EV": st.column_config.NumberColumn(format="%+.2f"),
    },
)
note("Do not follow this route blindly. After every completed week, the remaining route is deleted and rebuilt.", amber=True)

section("My pool state", "Authoritative state currently lives in the Margin JSON file and is updated after each real selection/result.")
state_cols = st.columns(4)
state_cols[0].metric("Current week", int(state["current_week"]))
state_cols[1].metric("Cumulative score", f"{float(state.get('cumulative_score', 0.0)):+.0f}")
state_cols[2].metric("Teams used", len(used))
state_cols[3].metric("Teams remaining", 32 - len(used))
_render_inventory(used)

history = pd.DataFrame(state.get("weekly_results", []))
if not history.empty:
    st.markdown("#### Completed picks")
    st.dataframe(history, hide_index=True, use_container_width=True)
else:
    st.caption("No 2026 Margin Pool picks have been completed yet.")

section("Data quality", "What the engine actually had available for this calculation.")
quality_cols = st.columns(4)
quality_cols[0].metric("Current games", int(data_quality["current_week_games"]))
quality_cols[1].metric("Current spreads", int(data_quality["current_week_posted_spreads"]))
quality_cols[2].metric("Season games", int(data_quality["season_games"]))
quality_cols[3].metric("Fallback HFA", f"{float(data_quality['fallback_hfa']):.2f}")
with st.expander("Source mix and technical status"):
    st.json({
        "market_snapshot": audit["snapshot_utc"],
        "championship_status": policy.get("championship_status"),
        "value_source_counts": data_quality.get("remaining_value_source_counts", {}),
        "posted_market_games_used_for_fallback": data_quality.get("snapshot_posted_market_games_used_for_fallback"),
        "anchor_ev_threshold": policy.get("anchor_ev_threshold"),
        "current_spread_sacrifice_cap": policy.get("current_spread_sacrifice_cap"),
    })

note(
    "This first dashboard version is intentionally read-only. Tell ChatGPT the team you actually used and the final margin; "
    "the authoritative state will be updated and the next week's dashboard will start from that inventory."
)
source_footer("NFL schedule/market data: nflverse/nflreadpy. Margin probabilities and allocation logic: validated Margin V1 research branch.")
