from __future__ import annotations

from typing import Any, Mapping

import pandas as pd
import streamlit as st

from research_ui import section
from src.knockout import engine, waiver_advisor


def _latest_elimination(state: Mapping[str, Any]) -> dict[str, Any] | None:
    rows = list(state.get("eliminations") or [])
    if not rows:
        return None
    return max(rows, key=lambda row: int(row.get("week", 0)))


def _latest_release(state: Mapping[str, Any]) -> dict[str, Any] | None:
    rows = list(state.get("released_rosters") or [])
    if not rows:
        return None
    return max(rows, key=lambda row: int(row.get("week", 0)))


def _candidate_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {
                "Decision": row["decision"],
                "Player": row["player"],
                "Pos": row["position"],
                "Source": row["source"],
                "Lineup +": row.get("lineup_delta"),
                "Bid": f"${int(row.get('recommended_bid') or 0)}",
                "Hard max": f"${int(row.get('max_bid') or 0)}",
                "Drop": row.get("drop_player") or "—",
                "Why": row.get("why") or "",
            }
            for row in rows
        ]
    )
    if not frame.empty:
        frame["Lineup +"] = pd.to_numeric(frame["Lineup +"], errors="coerce").round(1)
    return frame


def render_knockout_war_room(state: dict[str, Any]) -> dict[str, Any]:
    decision = engine.knockout_decision_summary(state)
    board = waiver_advisor.build_waiver_war_room(state)
    faab = board["faab_context"]
    connection = state.get("espn_connection") or {}

    section(
        "This Week",
        "The short version: field state, spending power, and the next decision that actually matters.",
    )
    cols = st.columns(4)
    cols[0].metric("Week", int(state.get("current_week", 0)))
    cols[1].metric("Teams alive", decision["teams_alive"])
    cols[2].metric("FAAB", f"${int(state.get('faab_remaining', 0))}")
    cols[3].metric(
        "FAAB rank",
        f"#{faab['rank']} of {faab['team_count']}" if faab["available"] else "Not synced",
    )
    if faab["available"]:
        st.caption(
            f"Active-team median FAAB: ${faab['median']:.0f}. "
            f"PropWar action: {decision['next_action']} · roster risk {decision['roster_risk']['level']}."
        )
    else:
        st.caption(
            f"PropWar action: {decision['next_action']} · roster risk {decision['roster_risk']['level']}. "
            "Resync ESPN to add full-league FAAB context."
        )

    section(
        "The Chop",
        "The latest eliminated roster is treated as a new mini-draft, but only players still available on ESPN can be recommended.",
    )
    eliminated = _latest_elimination(state)
    released = _latest_release(state)
    if eliminated is None:
        completed = engine.completed_elimination_count(state)
        if completed > 0:
            inactive = [
                str(row.get("team") or "").strip()
                for row in connection.get("team_roster_status") or []
                if int(row.get("roster_count") or 0) == 0 and str(row.get("team") or "").strip()
            ]
            detail = f" Current ESPN roster state shows: {', '.join(inactive)}." if inactive else ""
            st.info(
                f"{completed} eliminations are complete based on the Week {int(state.get('current_week', 0))} league phase."
                f"{detail} ESPN is not exposing enough historical scoring data to assign the exact chop order, "
                "so PropWar ranks the current waiver pool without inventing provenance."
            )
        else:
            st.info("No elimination has been recorded yet.")
    else:
        team = str(eliminated.get("team") or "Unknown team")
        week = int(eliminated.get("week", 0))
        if released is not None and int(released.get("week", -1)) == week:
            release_names = {
                str(row.get("player") or "").strip().casefold()
                for row in released.get("players") or []
            }
            available_names = {
                str(row.get("player") or "").strip().casefold()
                for row in connection.get("available_players") or []
            }
            still_available = len(release_names & available_names)
            st.success(
                f"Week {week}: {team} eliminated · {len(release_names)} players released · "
                f"{still_available} still available in the synced ESPN pool."
            )
        else:
            st.warning(
                f"Week {week}: {team} is recorded as eliminated, but its full released roster is not yet captured."
            )

    section(
        "Waiver War Room",
        "ADD means a material current-lineup upgrade. VALUE means useful depth or a smaller upgrade. PASS means PropWar would preserve the roster spot and FAAB at the current evidence level.",
    )
    if not board["enabled"]:
        st.warning(board["reason"])
    else:
        actionable = [row for row in board["candidates"] if row["decision"] != "PASS"]
        if actionable:
            st.dataframe(
                _candidate_frame(actionable[:12]),
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("No synced player currently clears PropWar's ADD or VALUE threshold.")
        passes = [row for row in board["candidates"] if row["decision"] == "PASS"]
        if passes:
            with st.expander("Top passes", expanded=False):
                st.dataframe(
                    _candidate_frame(passes[:5]),
                    hide_index=True,
                    width="stretch",
                )
        st.caption(
            f"Current-lineup projection coverage: {board['projection_coverage']:.0%}. "
            "Bid and hard-max figures are PropWar decision estimates, not claims about the exact winning bid."
        )

    section(
        "My Claim Plan",
        "Ordered claims with same-slot fallbacks, so losing the first target does not leave the waiver cycle unfinished.",
    )
    if not board["claim_plan"]:
        st.caption("No claim plan yet. PropWar currently prefers holding FAAB or needs a fresher ESPN sync.")
    else:
        plan = pd.DataFrame(board["claim_plan"]).rename(
            columns={
                "priority": "Priority",
                "player": "Player",
                "position": "Pos",
                "bid": "Bid",
                "max_bid": "Hard max",
                "drop": "Drop",
                "condition": "When",
            }
        )
        plan["Bid"] = plan["Bid"].map(lambda value: f"${int(value)}")
        plan["Hard max"] = plan["Hard max"].map(lambda value: f"${int(value)}")
        st.dataframe(plan, hide_index=True, width="stretch")

    section(
        "Survival",
        "Keep this simple until live field projections are trustworthy. No fake elimination percentage.",
    )
    risk = decision["roster_risk"]
    surv = st.columns(3)
    surv[0].metric("Roster risk", risk["level"])
    current_score = connection.get("source_current_score")
    surv[1].metric("Current score", "Not started" if current_score is None else f"{float(current_score):.1f}")
    surv[2].metric(
        "Projected lineup",
        f"{board['baseline_lineup_projection']:.1f}" if board.get("enabled") else "Not ready",
    )
    st.caption(risk["reason"])
    return board


__all__ = ["render_knockout_war_room"]
