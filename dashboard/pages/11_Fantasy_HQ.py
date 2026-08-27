from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import streamlit as st


PAGE_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = PAGE_DIR.parent
REPO_ROOT = DASHBOARD_DIR.parent
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_ui import page_intro, section  # noqa: E402
from src.fantasy.sleeper import SleeperClient  # noqa: E402


@st.cache_data(ttl=300, show_spinner=False)
def _resolve_sleeper_user(username_or_id: str) -> dict[str, Any]:
    with SleeperClient() as client:
        return dict(client.fetch_user(username_or_id))


@st.cache_data(ttl=120, show_spinner=False)
def _load_sleeper_leagues(user_id: str, season: str) -> tuple[dict[str, Any], ...]:
    with SleeperClient() as client:
        return tuple(dict(row) for row in client.fetch_user_leagues(user_id, season=season))


@st.cache_data(ttl=120, show_spinner=False)
def _load_league(league_id: str, user_id: str):
    with SleeperClient() as client:
        return client.fetch_normalized_league(league_id, current_user_id=user_id)


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _load_player_catalog() -> dict[str, dict[str, Any]]:
    with SleeperClient() as client:
        return {
            player_id: dict(player)
            for player_id, player in client.fetch_players().items()
        }


@st.cache_data(ttl=60, show_spinner=False)
def _load_nfl_state():
    with SleeperClient() as client:
        return client.fetch_nfl_state()


@st.cache_data(ttl=60, show_spinner=False)
def _load_matchups(league_id: str, week: int):
    if week < 1:
        return ()
    with SleeperClient() as client:
        return client.fetch_matchups(league_id, week)


def _secret_default(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or "").strip()


def _player_row(
    player_id: str,
    *,
    starter: bool,
    reserve: set[str],
    taxi: set[str],
    catalog: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    player = catalog.get(player_id) or {}
    full_name = str(player.get("full_name") or "").strip()
    if not full_name:
        first = str(player.get("first_name") or "").strip()
        last = str(player.get("last_name") or "").strip()
        full_name = f"{first} {last}".strip() or player_id
    if starter:
        role = "Starter"
    elif player_id in reserve:
        role = "IR"
    elif player_id in taxi:
        role = "Taxi"
    else:
        role = "Bench"
    return {
        "Player": full_name,
        "Pos": str(player.get("position") or "—"),
        "NFL": str(player.get("team") or "FA"),
        "Fantasy role": role,
        "Status": str(player.get("status") or "Active").replace("_", " ").title(),
    }


def _record(roster) -> str:
    settings = dict(roster.settings or {})
    wins = int(settings.get("wins") or 0)
    losses = int(settings.get("losses") or 0)
    ties = int(settings.get("ties") or 0)
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _points(roster) -> float:
    settings = dict(roster.settings or {})
    whole = float(settings.get("fpts") or 0)
    decimal = float(settings.get("fpts_decimal") or 0) / 100
    return whole + decimal


page_intro(
    "Fantasy HQ",
    "Your fantasy leagues in one place. Sleeper is live now; Yahoo is the next connection.",
)

st.caption("Owner tool · live read-only fantasy data · no Cloudflare persistence required")

source_a, source_b = st.columns(2)
with source_a:
    with st.container(border=True):
        st.markdown("### Sleeper")
        st.success("Live connection available")
        st.caption("Enter your Sleeper username once to discover your current NFL leagues.")
with source_b:
    with st.container(border=True):
        st.markdown("### Yahoo")
        st.warning("Connection not added yet")
        st.caption("Yahoo OAuth is next so your Yahoo league appears beside Sleeper here.")

default_username = _secret_default("FANTASY_HQ_SLEEPER_USERNAME")
username = st.text_input(
    "Sleeper username",
    value=default_username,
    placeholder="Your Sleeper username",
    help="Read-only. Your Sleeper password is never needed.",
)

if not username.strip():
    st.info("Enter your Sleeper username above to load your leagues.")
    st.stop()

try:
    with st.spinner("Finding your Sleeper leagues..."):
        sleeper_user = _resolve_sleeper_user(username.strip())
        nfl_state = _load_nfl_state()
        season = str(nfl_state.league_season or nfl_state.season)
        leagues = _load_sleeper_leagues(str(sleeper_user["user_id"]), season)
except Exception as exc:
    st.error("Fantasy HQ could not load your Sleeper account.")
    st.caption(str(exc))
    st.stop()

if not leagues:
    st.warning(f"No Sleeper NFL leagues were found for {season}.")
    st.stop()

st.caption(
    f"Sleeper · {sleeper_user.get('display_name') or sleeper_user.get('username') or username} · "
    f"{len(leagues)} league{'s' if len(leagues) != 1 else ''} found · {season}"
)

league_options = {
    f"{row.get('name') or 'Unnamed league'} · {row.get('total_rosters') or '?'} teams": str(row["league_id"])
    for row in leagues
}
selected_label = st.selectbox("League", tuple(league_options))
league_id = league_options[selected_label]

try:
    with st.spinner("Loading league and roster..."):
        league = _load_league(league_id, str(sleeper_user["user_id"]))
except Exception as exc:
    st.error("Fantasy HQ could not load this league.")
    st.caption(str(exc))
    st.stop()

my_roster = next(
    (roster for roster in league.rosters if roster.platform_roster_id == league.my_platform_roster_id),
    None,
)
my_manager = next(
    (manager for manager in league.managers if manager.platform_user_id == league.current_platform_user_id),
    None,
)

section(league.name or "Sleeper league", f"{league.team_count} teams · {league.season} · {league.status.replace('_', ' ').title()}")

metrics = st.columns(4)
metrics[0].metric("My team", (my_manager.team_name if my_manager and my_manager.team_name else my_manager.display_name if my_manager else "Found"))
metrics[1].metric("Record", _record(my_roster) if my_roster else "—")
metrics[2].metric("Points", f"{_points(my_roster):.2f}" if my_roster else "—")
metrics[3].metric("FAAB", f"${league.rules.waiver_budget}" if league.rules.waiver_budget is not None else "—")

roster_tab, matchup_tab, standings_tab, rules_tab = st.tabs(
    ["My roster", "Current matchup", "Standings", "League settings"]
)

with roster_tab:
    if not my_roster or not my_roster.players:
        st.info("Your roster is not populated yet. This is normal before the draft.")
    else:
        with st.spinner("Loading player names..."):
            catalog = _load_player_catalog()
        starter_set = set(my_roster.starters)
        reserve_set = set(my_roster.reserve)
        taxi_set = set(my_roster.taxi)
        rows = [
            _player_row(
                player_id,
                starter=player_id in starter_set,
                reserve=reserve_set,
                taxi=taxi_set,
                catalog=catalog,
            )
            for player_id in my_roster.players
        ]
        role_order = {"Starter": 0, "Bench": 1, "IR": 2, "Taxi": 3}
        rows.sort(key=lambda row: (role_order.get(row["Fantasy role"], 9), row["Pos"], row["Player"]))
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption(
            f"{len(starter_set)} starters · {max(0, len(my_roster.players) - len(starter_set))} non-starters"
        )

with matchup_tab:
    week = int(nfl_state.week or nfl_state.display_week or 0)
    if week < 1 or not my_roster:
        st.info("No regular-season matchup is available yet.")
    else:
        try:
            matchups = _load_matchups(league_id, week)
            mine = next(
                (row for row in matchups if row.platform_roster_id == my_roster.platform_roster_id),
                None,
            )
            opponent = next(
                (
                    row
                    for row in matchups
                    if mine
                    and row.matchup_id == mine.matchup_id
                    and row.platform_roster_id != mine.platform_roster_id
                ),
                None,
            )
            opponent_roster = next(
                (
                    roster
                    for roster in league.rosters
                    if opponent and roster.platform_roster_id == opponent.platform_roster_id
                ),
                None,
            )
            opponent_manager = next(
                (
                    manager
                    for manager in league.managers
                    if opponent_roster and manager.platform_user_id == opponent_roster.platform_user_id
                ),
                None,
            )
            if mine and opponent:
                left, right = st.columns(2)
                left.metric(
                    my_manager.team_name if my_manager and my_manager.team_name else "My team",
                    f"{float(mine.points or 0):.2f}",
                )
                right.metric(
                    opponent_manager.team_name if opponent_manager and opponent_manager.team_name else opponent_manager.display_name if opponent_manager else "Opponent",
                    f"{float(opponent.points or 0):.2f}",
                )
                st.caption(f"Week {week} · live Sleeper matchup")
            else:
                st.info(f"Week {week} matchup is not available yet.")
        except Exception as exc:
            st.warning("Current matchup could not be loaded.")
            st.caption(str(exc))

with standings_tab:
    manager_by_user = {manager.platform_user_id: manager for manager in league.managers}
    standings = []
    for roster in league.rosters:
        manager = manager_by_user.get(roster.platform_user_id or "")
        standings.append(
            {
                "Team": manager.team_name if manager and manager.team_name else manager.display_name if manager else f"Roster {roster.platform_roster_id}",
                "Record": _record(roster),
                "PF": round(_points(roster), 2),
                "Mine": "Yes" if roster.platform_roster_id == league.my_platform_roster_id else "",
            }
        )
    standings.sort(key=lambda row: row["PF"], reverse=True)
    st.dataframe(pd.DataFrame(standings), hide_index=True, width="stretch")

with rules_tab:
    settings = [
        ("Teams", league.team_count),
        ("Roster", " · ".join(league.rules.roster_positions)),
        ("Scoring", "Full PPR" if league.rules.scoring_settings.get("rec") == 1 else f"Reception: {league.rules.scoring_settings.get('rec', 0)}"),
        ("FAAB budget", league.rules.waiver_budget if league.rules.waiver_budget is not None else "—"),
        ("Playoff teams", league.rules.playoff_teams if league.rules.playoff_teams is not None else "—"),
        ("Trade deadline", league.rules.trade_deadline if league.rules.trade_deadline is not None else "—"),
        ("Keepers", league.rules.max_keepers if league.rules.max_keepers is not None else "—"),
        ("Draft", league.draft.status.replace("_", " ").title() if league.draft else "Unavailable"),
    ]
    st.dataframe(pd.DataFrame(settings, columns=["Setting", "Value"]), hide_index=True, width="stretch")

st.divider()
st.markdown("### What comes next")
st.write(
    "Yahoo connects into this same page next. After both providers are visible here, "
    "Fantasy HQ can add cross-league availability, waiver opportunities, start/sit, trades, FAAB, and opponent scouting."
)
