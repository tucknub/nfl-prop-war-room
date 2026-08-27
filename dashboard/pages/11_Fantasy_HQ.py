from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
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
from src.fantasy.action_center import build_fantasy_action_center  # noqa: E402
from src.fantasy.exposure import build_my_player_exposure  # noqa: E402
from src.fantasy.league_activity import build_league_activity  # noqa: E402
from src.fantasy.lineup_check import (  # noqa: E402
    NEEDS_ACTION as LINEUP_NEEDS_ACTION,
    build_lineup_check,
)
from src.fantasy.free_agents import (  # noqa: E402
    FANTASY_POSITIONS,
    find_live_free_agents,
)
from src.fantasy.opponent_scout import build_opponent_scout  # noqa: E402
from src.fantasy.live_ownership import (  # noqa: E402
    AVAILABLE,
    MINE,
    OTHER,
    lookup_live_sleeper_player,
    my_players_available_elsewhere,
)
from src.fantasy.roster_health import (  # noqa: E402
    NEEDS_ATTENTION,
    PRE_DRAFT,
    READY,
    WATCH,
    analyze_roster_health,
)
from src.fantasy.sleeper import SleeperClient  # noqa: E402
from src.fantasy.waiver_watch import build_sleeper_waiver_watch  # noqa: E402
from src.fantasy.waiver_fit import build_roster_need_waiver_board  # noqa: E402
from src.fantasy.yahoo import (  # noqa: E402
    DEFAULT_YAHOO_REDIRECT_URI,
    YahooFantasyClient,
    YahooOAuthClient,
    YahooOAuthConfig,
    YahooOAuthToken,
    build_yahoo_oauth_state,
    validate_yahoo_oauth_state,
)


YAHOO_SESSION_KEY = "fantasy_hq_yahoo_tokens"
YAHOO_CALLBACK_KEY = "fantasy_hq_yahoo_processed_code"


@st.cache_data(ttl=300, show_spinner=False)
def _resolve_sleeper_user(username_or_id: str) -> dict[str, Any]:
    with SleeperClient() as client:
        return dict(client.fetch_user(username_or_id))


@st.cache_data(ttl=120, show_spinner=False)
def _load_sleeper_leagues(user_id: str, season: str) -> tuple[dict[str, Any], ...]:
    with SleeperClient() as client:
        return tuple(
            dict(row)
            for row in client.fetch_user_leagues(user_id, season=season)
        )


@st.cache_data(ttl=120, show_spinner=False)
def _load_sleeper_league(league_id: str, user_id: str):
    with SleeperClient() as client:
        return client.fetch_normalized_league(
            league_id,
            current_user_id=user_id,
        )


@st.cache_data(ttl=120, show_spinner=False)
def _load_all_sleeper_states(
    user_id: str,
    league_ids: tuple[str, ...],
):
    with SleeperClient() as client:
        return tuple(
            client.fetch_normalized_league(
                league_id,
                current_user_id=user_id,
            )
            for league_id in league_ids
        )


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


@st.cache_data(ttl=60, show_spinner=False)
def _load_transactions(league_id: str, week: int):
    if week < 1:
        return ()
    with SleeperClient() as client:
        return client.fetch_transactions(league_id, week)


def _format_activity_time(timestamp_ms: int | None) -> str:
    if not timestamp_ms:
        return "—"
    value = datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=ZoneInfo("America/New_York"),
    )
    return value.strftime("%b %d · %I:%M %p ET").replace(" 0", " ")


@st.cache_data(ttl=5 * 60, show_spinner=False)
def _load_sleeper_trending_adds(
    lookback_hours: int,
    limit: int = 100,
):
    with SleeperClient() as client:
        return client.fetch_trending_players(
            "add",
            lookback_hours=lookback_hours,
            limit=limit,
        )


def _secret_default(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or "").strip()


def _yahoo_config() -> YahooOAuthConfig | None:
    client_id = _secret_default("YAHOO_CLIENT_ID")
    client_secret = _secret_default("YAHOO_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    redirect_uri = (
        _secret_default("YAHOO_REDIRECT_URI")
        or DEFAULT_YAHOO_REDIRECT_URI
    )
    return YahooOAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )


def _store_yahoo_token(token: YahooOAuthToken) -> None:
    existing = st.session_state.get(YAHOO_SESSION_KEY) or {}
    refresh_token = token.refresh_token or existing.get("refresh_token")
    st.session_state[YAHOO_SESSION_KEY] = {
        "access_token": token.access_token,
        "refresh_token": refresh_token,
        "expires_at": int(time.time()) + token.expires_in - 60,
    }


def _refresh_yahoo_if_needed(
    config: YahooOAuthConfig | None,
) -> str | None:
    if config is None:
        return None

    session = st.session_state.get(YAHOO_SESSION_KEY) or {}
    access_token = str(session.get("access_token") or "").strip()
    expires_at = int(session.get("expires_at") or 0)
    if access_token and expires_at > int(time.time()):
        return access_token

    refresh_token = (
        str(session.get("refresh_token") or "").strip()
        or _secret_default("YAHOO_REFRESH_TOKEN")
    )
    if not refresh_token:
        return None

    with YahooOAuthClient(config) as client:
        token = client.refresh(refresh_token)
    _store_yahoo_token(token)
    return token.access_token


def _handle_yahoo_callback(config: YahooOAuthConfig | None) -> None:
    error = str(st.query_params.get("error") or "").strip()
    if error:
        st.error("Yahoo authorization was not completed.")
        st.query_params.clear()
        return

    code = str(st.query_params.get("code") or "").strip()
    state = str(st.query_params.get("state") or "").strip()
    if not code and not state:
        return
    if config is None:
        st.error(
            "Yahoo returned an authorization code, but Yahoo app credentials "
            "are not configured."
        )
        return
    if not code or not state:
        st.error("Yahoo returned an incomplete authorization response.")
        return

    if st.session_state.get(YAHOO_CALLBACK_KEY) == code:
        st.query_params.clear()
        return

    try:
        validate_yahoo_oauth_state(state, config.client_secret)
        with YahooOAuthClient(config) as client:
            token = client.exchange_code(code)
        _store_yahoo_token(token)
        st.session_state[YAHOO_CALLBACK_KEY] = code
        st.query_params.clear()
        st.success("Yahoo connected.")
        st.rerun()
    except Exception as exc:
        st.error("Yahoo authorization could not be completed.")
        st.caption(str(exc))


def _sleeper_player_row(
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
        "Status": str(player.get("status") or "Active")
        .replace("_", " ")
        .title(),
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


def _render_sleeper() -> None:
    default_username = _secret_default("FANTASY_HQ_SLEEPER_USERNAME")
    username = st.text_input(
        "Sleeper username",
        value=default_username,
        placeholder="Your Sleeper username",
        help="Read-only. Your Sleeper password is never needed.",
    )

    if not username.strip():
        st.info(
            "Enter your Sleeper username above once to load your current NFL leagues."
        )
        st.markdown("### What unlocks immediately")
        preview_rows = [
            ("All-Leagues Action Center", "See every Sleeper league and which ones need attention."),
            ("Roster Health", "Open starters, depth gaps, and injury/status problems."),
            ("Lineup Check", "Slot-aware checks for FLEX, Superflex, WR/RB, WR/TE, IDP, and more."),
            ("Waiver Watch", "Trending available players plus search across the full live free-agent pool."),
            ("Roster Need Matches", "Match lineup needs to players who can legally fill those slots."),
            ("Opponent Scout", "Inspect the actual weekly opponent, roster, injuries, and matchup state."),
            ("League Activity", "Recent adds, drops, waivers, FAAB, trades, and pick movement."),
            ("Cross-League + Exposure", "See MY ROSTER / OWNED / AVAILABLE across leagues and repeated player exposure."),
        ]
        st.dataframe(
            pd.DataFrame(preview_rows, columns=["Fantasy HQ tool", "What it does"]),
            hide_index=True,
            width="stretch",
        )
        st.caption(
            "Nothing above requires Yahoo or the Cloudflare persistence work. "
            "Sleeper loads live after you enter your username."
        )
        return

    try:
        with st.spinner("Finding your Sleeper leagues..."):
            sleeper_user = _resolve_sleeper_user(username.strip())
            nfl_state = _load_nfl_state()
            season = str(nfl_state.league_season or nfl_state.season)
            leagues = _load_sleeper_leagues(
                str(sleeper_user["user_id"]),
                season,
            )
    except Exception as exc:
        st.error("Fantasy HQ could not load your Sleeper account.")
        st.caption(str(exc))
        return

    if not leagues:
        st.warning(f"No Sleeper NFL leagues were found for {season}.")
        return

    st.caption(
        f"{sleeper_user.get('display_name') or sleeper_user.get('username') or username} · "
        f"{len(leagues)} league{'s' if len(leagues) != 1 else ''} · {season}"
    )

    all_league_ids = tuple(
        str(row["league_id"])
        for row in leagues
        if str(row.get("league_id") or "").strip()
    )
    all_states = ()
    all_catalog: dict[str, dict[str, Any]] = {}
    action_center = None
    all_scan_error: str | None = None

    try:
        with st.spinner("Building your all-leagues snapshot..."):
            all_states = _load_all_sleeper_states(
                str(sleeper_user["user_id"]),
                all_league_ids,
            )
            all_catalog = _load_player_catalog()
            action_center = build_fantasy_action_center(
                all_states,
                all_catalog,
            )
    except Exception as exc:
        all_scan_error = str(exc)

    st.markdown("### All-Leagues Action Center")
    if action_center is None:
        st.warning(
            "The all-leagues snapshot could not be completed. "
            "Individual Sleeper leagues are still available below."
        )
        if all_scan_error:
            st.caption(all_scan_error)
    else:
        action_a, action_b, action_c, action_d = st.columns(4)
        action_a.metric("Sleeper leagues", action_center.league_count)
        action_b.metric(
            "Drafted",
            f"{action_center.drafted_count}/{action_center.league_count}",
        )
        action_c.metric(
            "Leagues needing attention",
            action_center.needs_attention_count,
        )
        action_d.metric(
            "Cross-league opportunities",
            action_center.opportunity_count,
        )

        status_labels = {
            READY: "Ready",
            WATCH: "Watch",
            NEEDS_ATTENTION: "Needs attention",
            PRE_DRAFT: "Pre-draft",
        }
        league_rows = [
            {
                "League": row.league_name,
                "Status": status_labels.get(
                    row.status,
                    row.status.replace("_", " ").title(),
                ),
                "Rostered": row.health.roster_size,
                "Starters": (
                    f"{row.health.filled_starter_slots}/"
                    f"{row.health.starter_slots}"
                ),
                "Open starters": row.health.open_starter_slots,
                "Critical": row.health.critical_count,
                "Warnings": row.health.warning_count,
            }
            for row in action_center.leagues
        ]
        st.dataframe(
            pd.DataFrame(league_rows),
            hide_index=True,
            width="stretch",
        )

        if action_center.action_leagues:
            st.markdown("#### What needs your attention")
            alert_rows = []
            for row in action_center.action_leagues:
                issues = row.top_issues
                if not issues:
                    alert_rows.append(
                        {
                            "League": row.league_name,
                            "Level": "WATCH",
                            "Alert": "Review this roster.",
                        }
                    )
                    continue
                for issue in issues:
                    alert_rows.append(
                        {
                            "League": row.league_name,
                            "Level": issue.severity,
                            "Alert": issue.message,
                        }
                    )
            st.dataframe(
                pd.DataFrame(alert_rows),
                hide_index=True,
                width="stretch",
            )
        elif action_center.drafted_count:
            st.success(
                "No drafted Sleeper league currently has a factual "
                "roster-health alert."
            )

        if action_center.pre_draft_count:
            st.caption(
                f"{action_center.pre_draft_count} Sleeper league"
                f"{'s are' if action_center.pre_draft_count != 1 else ' is'} "
                "still pre-draft; roster health will populate automatically "
                "after Sleeper updates the roster."
            )

        if action_center.opportunity_count:
            st.info(
                f"{action_center.opportunity_count} player"
                f"{'s' if action_center.opportunity_count != 1 else ''} "
                "on one of your Sleeper rosters "
                f"{'are' if action_center.opportunity_count != 1 else 'is'} "
                "currently available in another Sleeper league. "
                "Open Cross-league below for the exact players and leagues."
            )

    league_options = {
        f"{row.get('name') or 'Unnamed league'} · "
        f"{row.get('total_rosters') or '?'} teams": str(row["league_id"])
        for row in leagues
    }
    selected_label = st.selectbox(
        "Sleeper league",
        tuple(league_options),
        key="fantasy_hq_sleeper_league",
    )
    league_id = league_options[selected_label]

    try:
        with st.spinner("Loading league and roster..."):
            league = _load_sleeper_league(
                league_id,
                str(sleeper_user["user_id"]),
            )
    except Exception as exc:
        st.error("Fantasy HQ could not load this Sleeper league.")
        st.caption(str(exc))
        return

    my_roster = next(
        (
            roster
            for roster in league.rosters
            if roster.platform_roster_id == league.my_platform_roster_id
        ),
        None,
    )
    my_manager = next(
        (
            manager
            for manager in league.managers
            if manager.platform_user_id == league.current_platform_user_id
        ),
        None,
    )

    pre_draft_mode = bool(
        league.status == "pre_draft"
        or my_roster is None
        or not tuple(my_roster.players)
    )

    section(
        league.name or "Sleeper league",
        f"{league.team_count} teams · {league.season} · "
        f"{league.status.replace('_', ' ').title()}",
    )

    metrics = st.columns(4)
    metrics[0].metric(
        "My team",
        (
            my_manager.team_name
            if my_manager and my_manager.team_name
            else my_manager.display_name
            if my_manager
            else "Found"
        ),
    )
    metrics[1].metric("Record", _record(my_roster) if my_roster else "—")
    metrics[2].metric(
        "Points",
        f"{_points(my_roster):.2f}" if my_roster else "—",
    )
    metrics[3].metric(
        "FAAB",
        (
            "$" + str(league.rules.waiver_budget)
            if league.rules.waiver_budget is not None
            else "—"
        ),
    )

    (
        roster_tab,
        health_tab,
        lineup_tab,
        waiver_tab,
        activity_tab,
        matchup_tab,
        opponent_tab,
        standings_tab,
        rules_tab,
        cross_tab,
    ) = st.tabs(
        [
            "My roster",
            "Roster Health",
            "Lineup Check",
            "Waiver Watch",
            "League Activity",
            "Current matchup",
            "Opponent Scout",
            "Standings",
            "League settings",
            "Cross-league",
        ]
    )

    with roster_tab:
        if not my_roster or not my_roster.players:
            st.info(
                "Your roster is not populated yet. "
                "This is normal before the draft."
            )
        else:
            with st.spinner("Loading player names..."):
                catalog = _load_player_catalog()
            starter_set = set(my_roster.starters)
            reserve_set = set(my_roster.reserve)
            taxi_set = set(my_roster.taxi)
            rows = [
                _sleeper_player_row(
                    player_id,
                    starter=player_id in starter_set,
                    reserve=reserve_set,
                    taxi=taxi_set,
                    catalog=catalog,
                )
                for player_id in my_roster.players
            ]
            role_order = {"Starter": 0, "Bench": 1, "IR": 2, "Taxi": 3}
            rows.sort(
                key=lambda row: (
                    role_order.get(row["Fantasy role"], 9),
                    row["Pos"],
                    row["Player"],
                )
            )
            st.dataframe(
                pd.DataFrame(rows),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                f"{len(starter_set)} starters · "
                f"{max(0, len(my_roster.players) - len(starter_set))} non-starters"
            )

    with health_tab:
        with st.spinner("Checking roster health..."):
            health_catalog = _load_player_catalog()
            health = analyze_roster_health(
                league,
                health_catalog,
            )

        health_a, health_b, health_c, health_d = st.columns(4)
        status_label = {
            READY: "Ready",
            WATCH: "Watch",
            NEEDS_ATTENTION: "Needs attention",
            PRE_DRAFT: "Pre-draft",
        }.get(health.status, health.status.replace("_", " ").title())
        health_a.metric("Roster health", status_label)
        health_b.metric("Rostered", health.roster_size)
        health_c.metric(
            "Starter slots filled",
            f"{health.filled_starter_slots}/{health.starter_slots}",
        )
        health_d.metric("Open starters", health.open_starter_slots)

        if health.status == READY:
            st.success(
                "No factual roster-construction or player-status alerts are "
                "showing right now."
            )
        elif health.status == PRE_DRAFT:
            st.info(
                "This roster is not populated yet. Recheck after the draft."
            )
        elif health.status == NEEDS_ATTENTION:
            st.error(
                "At least one roster-construction or player-availability issue "
                "needs attention."
            )
        else:
            st.warning(
                "The roster is usable, but at least one depth, lineup, or "
                "player-status item is worth watching."
            )

        if health.position_counts:
            position_rows = [
                {"Position": position, "Rostered": count}
                for position, count in health.position_counts.items()
            ]
            st.markdown("##### Position depth")
            st.dataframe(
                pd.DataFrame(position_rows),
                hide_index=True,
                width="stretch",
            )

        st.markdown("##### Alerts")
        if not health.issues:
            st.caption("No current alerts.")
        else:
            issue_rows = [
                {
                    "Level": row.severity,
                    "Area": row.position or "Roster",
                    "Alert": row.message,
                }
                for row in health.issues
            ]
            st.dataframe(
                pd.DataFrame(issue_rows),
                hide_index=True,
                width="stretch",
            )

        st.caption(
            "Roster Health uses league starter requirements and Sleeper's "
            "current roster/player status. It is not a player-ranking model."
        )

    with lineup_tab:
        st.markdown("#### Lineup Check")
        st.caption(
            "Checks your actual Sleeper starter slots for open spots, "
            "player-status risk, and healthy bench players eligible for each slot."
        )

        if pre_draft_mode:
            lineup = None
            st.info(
                "Pre-draft mode: Lineup Check will activate after Sleeper "
                "populates your drafted roster. Configured starter slots are "
                "not treated as lineup mistakes before the draft."
            )
            st.caption(
                f"This league has {len(league.rules.starter_positions)} "
                "configured starter slots."
            )
        else:
            current_week = int(nfl_state.week or nfl_state.display_week or 0)
            lineup_matchup = None
            lineup_matchup_error: str | None = None
            if current_week >= 1 and my_roster is not None:
                try:
                    current_matchups = _load_matchups(league_id, current_week)
                    lineup_matchup = next(
                        (
                            row
                            for row in current_matchups
                            if row.platform_roster_id
                            == my_roster.platform_roster_id
                        ),
                        None,
                    )
                except Exception as exc:
                    lineup_matchup_error = str(exc)

            try:
                lineup_catalog = all_catalog or _load_player_catalog()
                lineup = build_lineup_check(
                    league,
                    lineup_catalog,
                    matchup=lineup_matchup,
                )
            except Exception as exc:
                st.warning("Lineup Check could not be built.")
                st.caption(str(exc))
                lineup = None

            if lineup is None:
                st.info(
                    "Your Sleeper roster is not available yet. "
                    "Lineup Check will populate after the roster exists."
                )
            else:
                lineup_a, lineup_b, lineup_c, lineup_d = st.columns(4)
                lineup_a.metric(
                    "Starters filled",
                    f"{lineup.filled_starter_slots}/{lineup.starter_slots}",
                )
                lineup_b.metric("Needs action", lineup.needs_action_count)
                lineup_c.metric("Watch", lineup.watch_count)
                lineup_d.metric("Healthy bench", lineup.healthy_bench_count)

                if lineup.needs_action:
                    st.error(
                        "At least one starter slot is open, ineligible, "
                        "or occupied by a player with a serious status."
                    )
                elif lineup.needs_watch:
                    st.warning(
                        "No forced lineup issue is showing, but at least one "
                        "Questionable starter is worth monitoring."
                    )
                elif lineup.starter_slots:
                    st.success(
                        "No factual starter-slot or player-status issue is showing."
                    )
                else:
                    st.info("This league has no active starter slots configured.")

                lineup_rows = []
                state_labels = {
                    LINEUP_NEEDS_ACTION: "ACTION",
                    WATCH: "WATCH",
                    READY: "READY",
                }
                for row in lineup.slots:
                    starter = row.starter
                    alternatives = tuple(row.eligible_alternatives)
                    alternative_labels = [
                        f"{player.name} · {player.position} · {player.status}"
                        for player in alternatives[:8]
                    ]
                    if len(alternatives) > 8:
                        alternative_labels.append(
                            f"+{len(alternatives) - 8} more"
                        )
                    lineup_rows.append(
                        {
                            "Slot": row.slot,
                            "Starter": starter.name if starter else "OPEN",
                            "Pos": starter.position if starter else "—",
                            "NFL": starter.nfl_team if starter else "—",
                            "Status": starter.status if starter else "Open",
                            "Check": state_labels.get(row.state, row.state),
                            "Why": row.reason,
                            "Eligible bench options": (
                                " | ".join(alternative_labels) or "—"
                            ),
                        }
                    )

                if lineup_rows:
                    st.dataframe(
                        pd.DataFrame(lineup_rows),
                        hide_index=True,
                        width="stretch",
                    )

                source = (
                    f"Week {current_week} matchup lineup"
                    if lineup.used_matchup_lineup and current_week >= 1
                    else "Current Sleeper roster starters"
                )
                st.caption(f"Lineup source: {source}.")
                if lineup_matchup_error:
                    st.caption(
                        "Current-week matchup data was unavailable, so Lineup "
                        "Check fell back to the roster starter list."
                    )

                st.caption(
                    "Eligible bench options are eligibility/status only, not "
                    "ranked start/sit recommendations. FLEX, WRRB Flex, Rec Flex, "
                    "Super Flex, and IDP Flex use Sleeper slot eligibility."
                )

    with waiver_tab:
        st.markdown("#### Waiver Watch")
        st.caption(
            "Sleeper's trending-add activity filtered to players who are "
            "actually available in this league."
        )

        if pre_draft_mode:
            st.info(
                "Pre-draft mode: Waiver Watch, Roster Need Matches, and the "
                "live free-agent pool will activate after Sleeper populates "
                "roster ownership from the draft."
            )
            st.caption(
                "No ownership or availability warnings are shown before "
                "there is a real roster pool to evaluate."
            )
        else:
            lookback_hours = st.selectbox(
                "Trending window",
                (24, 48, 72),
                format_func=lambda hours: f"Last {hours} hours",
                key="fantasy_hq_waiver_lookback",
            )
            all_league_ids = tuple(
                str(row["league_id"])
                for row in leagues
                if str(row.get("league_id") or "").strip()
            )
            try:
                with st.spinner("Building live Waiver Watch..."):
                    waiver_states = _load_all_sleeper_states(
                        str(sleeper_user["user_id"]),
                        all_league_ids,
                    )
                    waiver_catalog = _load_player_catalog()
                    trending_adds = _load_sleeper_trending_adds(
                        int(lookback_hours),
                        100,
                    )
                    waiver_candidates = build_sleeper_waiver_watch(
                        waiver_states,
                        selected_league_id=league_id,
                        trends=trending_adds,
                        player_catalog=waiver_catalog,
                    )
            except Exception as exc:
                st.warning("Waiver Watch could not be loaded.")
                st.caption(str(exc))
                waiver_candidates = ()
                trending_adds = ()

            if waiver_candidates:
                positions = tuple(
                    sorted(
                        {
                            row.position
                            for row in waiver_candidates
                            if row.position and row.position != "—"
                        }
                    )
                )
                default_positions = tuple(
                    position
                    for position in ("QB", "RB", "WR", "TE", "DEF", "K")
                    if position in positions
                )
                selected_positions = st.multiselect(
                    "Positions",
                    positions,
                    default=default_positions or positions,
                    key="fantasy_hq_waiver_positions",
                )
                filtered = tuple(
                    row
                    for row in waiver_candidates
                    if not selected_positions or row.position in selected_positions
                )

                waiver_a, waiver_b, waiver_c = st.columns(3)
                waiver_a.metric("Trending adds scanned", len(trending_adds))
                waiver_b.metric("Available here", len(waiver_candidates))
                waiver_c.metric(
                    "I roster elsewhere",
                    sum(1 for row in waiver_candidates if row.mine_elsewhere),
                )

                rows = []
                for candidate in filtered[:75]:
                    raw_status = str(candidate.injury_status or "Active")
                    normalized_status = raw_status.replace("_", " ").title()
                    rows.append(
                        {
                            "Player": candidate.player_name,
                            "Pos": candidate.position,
                            "NFL": candidate.nfl_team,
                            "Sleeper adds": candidate.trend_count,
                            "Status": normalized_status,
                            "I roster elsewhere": (
                                " · ".join(candidate.mine_elsewhere) or "—"
                            ),
                            "Owned elsewhere": (
                                " · ".join(candidate.owned_elsewhere) or "—"
                            ),
                        }
                    )

                st.dataframe(
                    pd.DataFrame(rows),
                    hide_index=True,
                    width="stretch",
                )
                st.caption(
                    "Higher add counts mean more Sleeper managers added the player "
                    "during the selected window; this is activity, not a PropWar "
                    "player ranking."
                )
            elif trending_adds:
                st.info(
                    "None of Sleeper's current trending adds are available in this "
                    "league."
                )

            st.markdown("##### Roster Need Matches")
            st.caption(
                "Connects your current Lineup Check issues to players who are "
                "actually available in this league."
            )

            if lineup is None:
                st.info(
                    "Roster Need Matches will populate after Lineup Check can "
                    "identify your current starter slots."
                )
            else:
                try:
                    need_board = build_roster_need_waiver_board(
                        league,
                        lineup,
                        all_catalog or _load_player_catalog(),
                        all_leagues=(all_states or (league,)),
                        trends=trending_adds,
                        limit=75,
                    )
                except Exception as exc:
                    st.warning("Roster Need Matches could not be built.")
                    st.caption(str(exc))
                    need_board = None

                if need_board is not None:
                    need_a, need_b, need_c, need_d = st.columns(4)
                    need_a.metric("Action slots", need_board.action_need_count)
                    need_b.metric("Watch slots", need_board.watch_need_count)
                    need_c.metric("Available fits", len(need_board.matches))
                    need_d.metric(
                        "I roster elsewhere",
                        need_board.familiar_match_count,
                    )

                    if not need_board.needs:
                        st.success(
                            "Lineup Check has no current Action or Watch slot, so "
                            "there is no factual roster need to match right now."
                        )
                    else:
                        need_rows = [
                            {
                                "Need": row.label,
                                "Level": (
                                    "ACTION"
                                    if row.level == LINEUP_NEEDS_ACTION
                                    else "WATCH"
                                ),
                                "Why": row.reason,
                            }
                            for row in need_board.needs
                        ]
                        st.dataframe(
                            pd.DataFrame(need_rows),
                            hide_index=True,
                            width="stretch",
                        )

                        if not need_board.matches:
                            st.info(
                                "No currently available healthy player matched "
                                "these starter-slot needs."
                            )
                        else:
                            match_rows = [
                                {
                                    "Player": row.player_name,
                                    "Pos": row.position,
                                    "NFL": row.nfl_team,
                                    "Status": row.status,
                                    "Fits action slots": (
                                        " · ".join(row.action_slots) or "—"
                                    ),
                                    "Fits watch slots": (
                                        " · ".join(row.watch_slots) or "—"
                                    ),
                                    "Sleeper adds": (
                                        row.trend_count
                                        if row.trend_count > 0
                                        else "—"
                                    ),
                                    "I roster elsewhere": (
                                        " · ".join(row.mine_elsewhere) or "—"
                                    ),
                                }
                                for row in need_board.matches
                            ]
                            st.dataframe(
                                pd.DataFrame(match_rows),
                                hide_index=True,
                                width="stretch",
                            )
                            if need_board.familiar_match_count:
                                st.success(
                                    f"{need_board.familiar_match_count} fit"
                                    f"{'s' if need_board.familiar_match_count != 1 else ''} "
                                    "shown are already on one of your other "
                                    "Sleeper rosters."
                                )

                    st.caption(
                        "Ordering favors players who cover more Action slots, then "
                        "players you already roster elsewhere and current Sleeper "
                        "add activity. This is not a player-value ranking."
                    )

            st.markdown("##### Search all available players")
            st.caption(
                "Not limited to trending adds. Search the complete live Sleeper "
                "player pool against this league's current roster ownership."
            )

            search_a, search_b, search_c = st.columns([1, 2, 1])
            with search_a:
                available_position = st.selectbox(
                    "Free-agent position",
                    ("ALL", *FANTASY_POSITIONS),
                    key="fantasy_hq_available_position",
                )
            with search_b:
                available_search = st.text_input(
                    "Free-agent search",
                    placeholder="Player name",
                    key="fantasy_hq_available_search",
                ).strip()
            with search_c:
                available_familiar_only = st.checkbox(
                    "Only players I roster elsewhere",
                    value=False,
                    key="fantasy_hq_available_familiar_only",
                )

            try:
                available_catalog = all_catalog or _load_player_catalog()
                available_rows = find_live_free_agents(
                    league,
                    available_catalog,
                    all_leagues=(all_states or (league,)),
                    query=available_search,
                    position=available_position,
                    mine_elsewhere_only=available_familiar_only,
                    limit=100,
                )
            except Exception as exc:
                st.warning("All-player free-agent search could not be loaded.")
                st.caption(str(exc))
                available_rows = ()

            familiar_available = sum(1 for row in available_rows if row.familiar)
            available_a, available_b = st.columns(2)
            available_a.metric("Available matches", len(available_rows))
            available_b.metric("I roster elsewhere", familiar_available)

            if not available_rows:
                if not league.ownership_ready:
                    st.info(
                        "Sleeper ownership is not initialized for this league yet."
                    )
                elif available_familiar_only:
                    st.info(
                        "No player you roster in another scanned Sleeper league "
                        "matches these filters and is available here."
                    )
                elif available_search:
                    st.info("No available player matched this search.")
                else:
                    st.info("No available player matched the selected filters.")
            else:
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Player": row.name,
                                "Pos": row.position,
                                "NFL": row.nfl_team,
                                "Status": row.status,
                                "I roster elsewhere": (
                                    " · ".join(row.mine_elsewhere) or "—"
                                ),
                            }
                            for row in available_rows
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
                if familiar_available:
                    st.success(
                        f"{familiar_available} available player"
                        f"{'s' if familiar_available != 1 else ''} shown "
                        f"{'are' if familiar_available != 1 else 'is'} already "
                        "on one of your other Sleeper rosters."
                    )

            st.caption(
                "Availability is factual live Sleeper roster absence. "
                "This search does not assign a player-quality score."
            )

            st.markdown(
                "[Trending data provided by Sleeper](https://sleeper.com/)"
            )

    with activity_tab:
        st.markdown("#### League Activity")
        st.caption(
            "Recent adds, drops, waivers and trades from Sleeper for the "
            "selected league."
        )

        if pre_draft_mode:
            st.info(
                "Pre-draft mode: League Activity will switch on after the "
                "draft. The NFL preseason week is not treated as your fantasy "
                "league's active transaction week here."
            )
        else:
            current_activity_week = int(
                nfl_state.week or nfl_state.display_week or 0
            )
            if current_activity_week < 1:
                st.info(
                    "No regular-season transaction week is available yet."
                )
            else:
                activity_weeks = tuple(
                    range(
                        max(1, current_activity_week - 3),
                        current_activity_week + 1,
                    )
                )
                activity_week = st.selectbox(
                    "Activity week",
                    tuple(reversed(activity_weeks)),
                    format_func=lambda value: f"Week {value}",
                    key="fantasy_hq_activity_week",
                )

                try:
                    activity_transactions = _load_transactions(
                        league_id,
                        int(activity_week),
                    )
                    activity_catalog = all_catalog or _load_player_catalog()
                    activity = build_league_activity(
                        league,
                        activity_transactions,
                        activity_catalog,
                    )
                except Exception as exc:
                    st.warning("League Activity could not be loaded.")
                    st.caption(str(exc))
                    activity = None

                if activity is not None:
                    activity_a, activity_b, activity_c, activity_d = st.columns(4)
                    activity_a.metric(
                        "Transactions",
                        activity.transaction_count,
                    )
                    activity_b.metric("Adds", activity.add_count)
                    activity_c.metric("Drops", activity.drop_count)
                    activity_d.metric("Trades", activity.trade_count)

                    if not activity.transactions:
                        st.info(
                            f"No Sleeper transactions were returned for "
                            f"Week {activity_week}."
                        )
                    else:
                        activity_rows = []
                        for transaction in activity.transactions:
                            add_text = " · ".join(
                                f"{row.name} ({row.team_name})"
                                for row in transaction.adds
                            ) or "—"
                            drop_text = " · ".join(
                                f"{row.name} ({row.team_name})"
                                for row in transaction.drops
                            ) or "—"

                            faab_parts = []
                            if transaction.waiver_bid is not None:
                                faab_parts.append(
                                    "Bid $" + str(transaction.waiver_bid)
                                )
                            for transfer in transaction.faab_transfers:
                                if transfer.amount is None:
                                    continue
                                sender = transfer.sender_team or "Unknown"
                                receiver = transfer.receiver_team or "Unknown"
                                faab_parts.append(
                                    "$"
                                    + str(transfer.amount)
                                    + f" {sender} → {receiver}"
                                )

                            activity_rows.append(
                                {
                                    "When": _format_activity_time(
                                        transaction.sort_timestamp_ms
                                    ),
                                    "Type": transaction.type_label,
                                    "Status": transaction.status.replace(
                                        "_", " "
                                    ).title(),
                                    "Teams": (
                                        " · ".join(transaction.teams) or "—"
                                    ),
                                    "Adds": add_text,
                                    "Drops": drop_text,
                                    "FAAB / bid": (
                                        " · ".join(faab_parts) or "—"
                                    ),
                                    "Picks": (
                                        transaction.traded_pick_count
                                        if transaction.traded_pick_count
                                        else "—"
                                    ),
                                }
                            )

                        st.dataframe(
                            pd.DataFrame(activity_rows),
                            hide_index=True,
                            width="stretch",
                        )
                        st.caption(
                            "Activity is direct Sleeper transaction data. "
                            "Pending transactions remain labeled Pending rather "
                            "than being treated as completed moves."
                        )

    with matchup_tab:
        if pre_draft_mode:
            st.info(
                "Pre-draft mode: your fantasy matchup will appear after the "
                "draft and Sleeper publishes roster/matchup data."
            )
        else:
            week = int(nfl_state.week or nfl_state.display_week or 0)
            if week < 1 or not my_roster:
                st.info("No regular-season matchup is available yet.")
            else:
                try:
                    matchups = _load_matchups(league_id, week)
                    mine = next(
                        (
                            row
                            for row in matchups
                            if row.platform_roster_id
                            == my_roster.platform_roster_id
                        ),
                        None,
                    )
                    opponent = next(
                        (
                            row
                            for row in matchups
                            if mine
                            and row.matchup_id == mine.matchup_id
                            and row.platform_roster_id
                            != mine.platform_roster_id
                        ),
                        None,
                    )
                    opponent_roster = next(
                        (
                            roster
                            for roster in league.rosters
                            if opponent
                            and roster.platform_roster_id
                            == opponent.platform_roster_id
                        ),
                        None,
                    )
                    opponent_manager = next(
                        (
                            manager
                            for manager in league.managers
                            if opponent_roster
                            and manager.platform_user_id
                            == opponent_roster.platform_user_id
                        ),
                        None,
                    )
                    if mine and opponent:
                        left, right = st.columns(2)
                        left.metric(
                            (
                                my_manager.team_name
                                if my_manager and my_manager.team_name
                                else "My team"
                            ),
                            f"{float(mine.points or 0):.2f}",
                        )
                        right.metric(
                            (
                                opponent_manager.team_name
                                if opponent_manager
                                and opponent_manager.team_name
                                else opponent_manager.display_name
                                if opponent_manager
                                else "Opponent"
                            ),
                            f"{float(opponent.points or 0):.2f}",
                        )
                        st.caption(f"Week {week} · live Sleeper matchup")
                    else:
                        st.info(f"Week {week} matchup is not available yet.")
                except Exception as exc:
                    st.warning("Current matchup could not be loaded.")
                    st.caption(str(exc))

    with opponent_tab:
        st.markdown("#### Opponent Scout")
        st.caption(
            "Factual live Sleeper scouting for your current weekly opponent. "
            "No projected winner or player ranking is inferred."
        )

        if pre_draft_mode:
            st.info(
                "Pre-draft mode: Opponent Scout will activate once Sleeper "
                "has drafted rosters and a real fantasy matchup pairing."
            )
        else:
            scout_week = int(nfl_state.week or nfl_state.display_week or 0)
            if scout_week < 1 or not my_roster:
                st.info("No regular-season opponent is available yet.")
            else:
                try:
                    scout_matchups = _load_matchups(league_id, scout_week)
                    scout_catalog = all_catalog or _load_player_catalog()
                    scout = build_opponent_scout(
                        league,
                        scout_matchups,
                        week=scout_week,
                        player_catalog=scout_catalog,
                    )
                except Exception as exc:
                    st.warning("Opponent Scout could not be loaded.")
                    st.caption(str(exc))
                    scout = None

                if scout is None:
                    st.info(
                        f"Week {scout_week} opponent pairing is not available yet."
                    )
                else:
                    scout_a, scout_b, scout_c, scout_d = st.columns(4)
                    scout_a.metric("Opponent", scout.opponent_name)
                    scout_b.metric("Record", scout.opponent_record)
                    scout_c.metric("Season PF", f"{scout.opponent_points_for:.2f}")
                    scout_d.metric("Starter alerts", scout.starter_alert_count)

                    score_left, score_right = st.columns(2)
                    score_left.metric(
                        "My live matchup points",
                        (
                            f"{float(scout.my_matchup_points):.2f}"
                            if scout.my_matchup_points is not None
                            else "—"
                        ),
                    )
                    score_right.metric(
                        "Opponent live matchup points",
                        (
                            f"{float(scout.opponent_matchup_points):.2f}"
                            if scout.opponent_matchup_points is not None
                            else "—"
                        ),
                    )

                    if scout.open_starter_slots:
                        st.warning(
                            f"Opponent currently has {scout.open_starter_slots} "
                            "unfilled starter slot"
                            f"{'s' if scout.open_starter_slots != 1 else ''}."
                        )

                    st.markdown("##### Starter availability")
                    if not scout.starters:
                        st.info("Opponent starters have not been populated yet.")
                    else:
                        starter_rows = [
                            {
                                "Player": row.name,
                                "Pos": row.position,
                                "NFL": row.nfl_team,
                                "Status": row.status,
                                "Week points": (
                                    row.points if row.points is not None else "—"
                                ),
                            }
                            for row in scout.starters
                        ]
                        st.dataframe(
                            pd.DataFrame(starter_rows),
                            hide_index=True,
                            width="stretch",
                        )

                        if scout.serious_starter_count:
                            st.error(
                                f"{scout.serious_starter_count} opponent starter"
                                f"{'s have' if scout.serious_starter_count != 1 else ' has'} "
                                "an Out/IR/PUP/Suspended/Doubtful status."
                            )
                        if scout.questionable_starter_count:
                            st.warning(
                                f"{scout.questionable_starter_count} opponent starter"
                                f"{'s are' if scout.questionable_starter_count != 1 else ' is'} "
                                "currently Questionable."
                            )
                        if not scout.starter_alert_count:
                            st.success(
                                "No opponent starter currently carries a serious "
                                "or Questionable Sleeper status."
                            )

                    st.markdown("##### Opponent position depth")
                    if scout.position_counts:
                        st.dataframe(
                            pd.DataFrame(
                                [
                                    {"Position": position, "Rostered": count}
                                    for position, count in scout.position_counts.items()
                                ]
                            ),
                            hide_index=True,
                            width="stretch",
                        )

                    with st.expander(
                        f"Opponent bench / reserve ({len(scout.bench)})",
                        expanded=False,
                    ):
                        if not scout.bench:
                            st.caption("No non-starter players are populated.")
                        else:
                            st.dataframe(
                                pd.DataFrame(
                                    [
                                        {
                                            "Player": row.name,
                                            "Pos": row.position,
                                            "NFL": row.nfl_team,
                                            "Slot": row.fantasy_slot,
                                            "Status": row.status,
                                            "Week points": (
                                                row.points
                                                if row.points is not None
                                                else "—"
                                            ),
                                        }
                                        for row in scout.bench
                                    ]
                                ),
                                hide_index=True,
                                width="stretch",
                            )

                    st.caption(
                        "Opponent Scout reflects Sleeper roster, matchup, and "
                        "player-status facts only. It does not project the matchup."
                    )

    with standings_tab:
        if pre_draft_mode:
            st.info(
                "Pre-draft standings are informational only; records and "
                "points will begin changing once the fantasy season starts."
            )

        manager_by_user = {
            manager.platform_user_id: manager
            for manager in league.managers
        }
        standings = []
        for roster in league.rosters:
            manager = manager_by_user.get(roster.platform_user_id or "")
            standings.append(
                {
                    "Team": (
                        manager.team_name
                        if manager and manager.team_name
                        else manager.display_name
                        if manager
                        else f"Roster {roster.platform_roster_id}"
                    ),
                    "Record": _record(roster),
                    "PF": round(_points(roster), 2),
                    "Mine": (
                        "Yes"
                        if roster.platform_roster_id
                        == league.my_platform_roster_id
                        else ""
                    ),
                }
            )
        standings.sort(key=lambda row: row["PF"], reverse=True)
        st.dataframe(
            pd.DataFrame(standings),
            hide_index=True,
            width="stretch",
        )

    with rules_tab:
        if pre_draft_mode:
            st.success(
                "League settings are available now and are the most useful "
                "pre-draft Fantasy HQ section."
            )

        settings = [
            ("Teams", league.team_count),
            ("Roster", " · ".join(league.rules.roster_positions)),
            (
                "Scoring",
                (
                    "Full PPR"
                    if league.rules.scoring_settings.get("rec") == 1
                    else f"Reception: "
                    f"{league.rules.scoring_settings.get('rec', 0)}"
                ),
            ),
            (
                "FAAB budget",
                (
                    league.rules.waiver_budget
                    if league.rules.waiver_budget is not None
                    else "—"
                ),
            ),
            (
                "Playoff teams",
                (
                    league.rules.playoff_teams
                    if league.rules.playoff_teams is not None
                    else "—"
                ),
            ),
            (
                "Trade deadline",
                (
                    league.rules.trade_deadline
                    if league.rules.trade_deadline is not None
                    else "—"
                ),
            ),
            (
                "Keepers",
                (
                    league.rules.max_keepers
                    if league.rules.max_keepers is not None
                    else "—"
                ),
            ),
            (
                "Draft",
                (
                    league.draft.status.replace("_", " ").title()
                    if league.draft
                    else "Unavailable"
                ),
            ),
        ]
        st.dataframe(
            pd.DataFrame(settings, columns=["Setting", "Value"]),
            hide_index=True,
            width="stretch",
        )


    with cross_tab:
        st.markdown("#### Sleeper cross-league ownership")
        if pre_draft_mode:
            st.info(
                "This selected league is still pre-draft. Cross-league "
                "ownership and exposure will fill in automatically as your "
                "Sleeper drafts populate rosters."
            )

        st.caption(
            "Live roster ownership across every Sleeper NFL league found for "
            "this account. Draft results will appear here as Sleeper rosters update."
        )

        catalog = all_catalog
        if not all_states:
            st.warning("Cross-league ownership could not be loaded.")
            if all_scan_error:
                st.caption(all_scan_error)

        if all_states:
            scan_a, scan_b = st.columns(2)
            scan_a.metric("Sleeper leagues scanned", len(all_states))

            actionable = my_players_available_elsewhere(all_states)
            scan_b.metric(
                "My players free elsewhere",
                len(actionable),
            )

            exposure = build_my_player_exposure(all_states)
            st.markdown("##### My Player Exposure")
            exposure_a, exposure_b, exposure_c, exposure_d = st.columns(4)
            exposure_a.metric(
                "Distinct players",
                exposure.distinct_player_count,
            )
            exposure_b.metric(
                "Multi-league players",
                exposure.multi_league_player_count,
            )
            exposure_c.metric(
                "Max leagues / player",
                exposure.max_league_count,
            )
            exposure_d.metric(
                "My roster slots",
                exposure.total_roster_slots,
            )

            exposure_positions = tuple(
                sorted(
                    {
                        str(
                            (catalog.get(row.sleeper_player_id) or {}).get(
                                "position"
                            )
                            or "—"
                        ).upper()
                        for row in exposure.players
                    }
                    - {"—"}
                )
            )
            exposure_filter_a, exposure_filter_b = st.columns([1, 2])
            with exposure_filter_a:
                exposure_multi_only = st.checkbox(
                    "Only players owned in 2+ leagues",
                    value=False,
                    key="fantasy_hq_exposure_multi_only",
                )
            with exposure_filter_b:
                exposure_selected_positions = st.multiselect(
                    "Exposure positions",
                    exposure_positions,
                    default=exposure_positions,
                    key="fantasy_hq_exposure_positions",
                )

            exposure_rows = []
            for exposure_row in exposure.players:
                if exposure_multi_only and not exposure_row.multi_league:
                    continue
                player = catalog.get(exposure_row.sleeper_player_id) or {}
                position = str(player.get("position") or "—").upper()
                if (
                    exposure_selected_positions
                    and position not in exposure_selected_positions
                ):
                    continue
                name = str(player.get("full_name") or "").strip()
                if not name:
                    first = str(player.get("first_name") or "").strip()
                    last = str(player.get("last_name") or "").strip()
                    name = (
                        f"{first} {last}".strip()
                        or exposure_row.sleeper_player_id
                    )
                exposure_rows.append(
                    {
                        "Player": name,
                        "Pos": position,
                        "NFL": str(player.get("team") or "FA"),
                        "Leagues owned": exposure_row.league_count,
                        "Where": " · ".join(
                            f"{item.league_name} ({item.roster_slot})"
                            for item in exposure_row.leagues
                        ),
                        "Starts": exposure_row.starter_count,
                        "Bench": exposure_row.bench_count,
                        "IR": exposure_row.reserve_count,
                        "Taxi": exposure_row.taxi_count,
                    }
                )

            exposure_rows.sort(
                key=lambda row: (
                    -int(row["Leagues owned"]),
                    -int(row["Starts"]),
                    str(row["Player"]).casefold(),
                )
            )
            if exposure_rows:
                st.dataframe(
                    pd.DataFrame(exposure_rows),
                    hide_index=True,
                    width="stretch",
                )
            elif exposure.players:
                st.info("No owned player matches the exposure filters.")
            else:
                st.info(
                    "No drafted Sleeper roster exposure is available yet."
                )

            st.caption(
                "Exposure is ownership only, not a recommendation to diversify "
                "or concentrate. Pre-draft leagues add exposure after rosters populate."
            )

            st.markdown("##### My players available in another league")
            if not actionable:
                st.info(
                    "No current player on one of your Sleeper rosters is "
                    "available in another scanned Sleeper league yet."
                )
            else:
                action_rows = []
                for item in actionable:
                    player = catalog.get(item.sleeper_player_id) or {}
                    name = str(player.get("full_name") or "").strip()
                    if not name:
                        first = str(player.get("first_name") or "").strip()
                        last = str(player.get("last_name") or "").strip()
                        name = (
                            f"{first} {last}".strip()
                            or item.sleeper_player_id
                        )
                    action_rows.append(
                        {
                            "Player": name,
                            "Pos": str(player.get("position") or "—"),
                            "NFL": str(player.get("team") or "FA"),
                            "I roster him in": " · ".join(item.mine_in),
                            "Available in": " · ".join(item.available_in),
                            "Opponent-owned in": (
                                " · ".join(item.owned_elsewhere_in) or "—"
                            ),
                        }
                    )
                action_rows.sort(
                    key=lambda row: (
                        row["Pos"],
                        row["Player"],
                    )
                )
                st.dataframe(
                    pd.DataFrame(action_rows),
                    hide_index=True,
                    width="stretch",
                )

            st.markdown("##### Look up any player")
            search = st.text_input(
                "Player search",
                placeholder="e.g. Jonathan Taylor",
                key="fantasy_hq_cross_league_player_search",
            ).strip()

            if search:
                normalized_search = search.casefold()
                candidates = []
                for player_id, player in catalog.items():
                    name = str(player.get("full_name") or "").strip()
                    if not name:
                        first = str(player.get("first_name") or "").strip()
                        last = str(player.get("last_name") or "").strip()
                        name = f"{first} {last}".strip()
                    if not name or normalized_search not in name.casefold():
                        continue
                    candidates.append(
                        (
                            0 if name.casefold().startswith(normalized_search) else 1,
                            name.casefold(),
                            str(player_id),
                            name,
                            str(player.get("position") or "—"),
                            str(player.get("team") or "FA"),
                        )
                    )

                candidates.sort()
                candidates = candidates[:40]
                if not candidates:
                    st.info("No Sleeper NFL player matched that search.")
                else:
                    option_map = {
                        f"{name} · {position} · {team}": player_id
                        for _, _, player_id, name, position, team in candidates
                    }
                    selected_player = st.selectbox(
                        "Player",
                        tuple(option_map),
                        key="fantasy_hq_cross_league_player",
                    )
                    selected_id = option_map[selected_player]
                    ownership = lookup_live_sleeper_player(
                        all_states,
                        selected_id,
                    )
                    status_rows = []
                    for row in ownership.statuses:
                        if row.status == MINE:
                            status = "MY ROSTER"
                        elif row.status == OTHER:
                            status = (
                                "OWNED"
                                + (
                                    f" · {row.owner_name}"
                                    if row.owner_name
                                    else ""
                                )
                            )
                        elif row.status == AVAILABLE:
                            status = "AVAILABLE"
                        else:
                            status = "UNKNOWN"
                        status_rows.append(
                            {
                                "League": row.league_name,
                                "Status": status,
                                "Slot": row.roster_slot or "—",
                            }
                        )

                    st.dataframe(
                        pd.DataFrame(status_rows),
                        hide_index=True,
                        width="stretch",
                    )
                    available_count = len(ownership.available_in)
                    if available_count:
                        st.success(
                            f"Available in {available_count} Sleeper league"
                            f"{'s' if available_count != 1 else ''}: "
                            + ", ".join(ownership.available_in)
                        )
                    elif ownership.mine_in:
                        st.info(
                            "You already roster this player in every scanned "
                            "league where he is not opponent-owned."
                        )
                    else:
                        st.caption(
                            "This player is not currently available in the "
                            "scanned Sleeper leagues."
                        )


def _render_yahoo(
    config: YahooOAuthConfig | None,
    access_token: str | None,
) -> None:
    if config is None:
        st.warning(
            "Yahoo Fantasy API access has not been configured for PropWar yet."
        )
        st.markdown("**One-time Yahoo access setup**")
        st.markdown(
            "1. Apply for Yahoo Fantasy Sports API access. Yahoo currently "
            "reviews applications before granting access.\n"
            "2. Use PropWar / Fantasy HQ as the product and request read-only "
            "Fantasy Football data for personal fantasy-league management.\n"
            f"3. After approval, set the OAuth callback URL to "
            f"{DEFAULT_YAHOO_REDIRECT_URI}.\n"
            "4. Add YAHOO_CLIENT_ID and YAHOO_CLIENT_SECRET to the "
            "PropWar Streamlit secrets."
        )
        st.link_button(
            "Apply for Yahoo Fantasy API",
            "https://sports.yahoo.com/developer/access/",
        )
        return

    if access_token is None:
        state = build_yahoo_oauth_state(config.client_secret)
        auth_url = config.authorization_url(state=state)
        st.info(
            "Yahoo is ready to connect. Authorization happens on Yahoo; "
            "PropWar never receives your Yahoo password."
        )
        st.link_button(
            "Connect Yahoo",
            auth_url,
            type="primary",
        )
        st.caption(f"OAuth callback: {config.redirect_uri}")
        return

    top_left, top_right = st.columns([4, 1])
    with top_left:
        st.success("Yahoo connected")
        st.caption(
            "Private Yahoo fantasy data is being read with your authorized "
            "OAuth token."
        )
    with top_right:
        if st.button("Disconnect Yahoo", width="stretch"):
            st.session_state.pop(YAHOO_SESSION_KEY, None)
            st.session_state.pop(YAHOO_CALLBACK_KEY, None)
            st.rerun()

    try:
        with YahooFantasyClient(access_token) as client:
            with st.spinner("Loading your Yahoo fantasy football teams..."):
                teams = client.fetch_user_nfl_teams()
    except Exception as exc:
        st.error("Fantasy HQ could not load your Yahoo fantasy teams.")
        st.caption(str(exc))
        return

    if not teams:
        st.warning(
            "No Yahoo fantasy football teams were returned for the current "
            "NFL game."
        )
        return

    options = {
        f"{team.name} · {team.league_key}": team
        for team in teams
    }
    selected = st.selectbox(
        "Yahoo team",
        tuple(options),
        key="fantasy_hq_yahoo_team",
    )
    team = options[selected]

    try:
        with YahooFantasyClient(access_token) as client:
            with st.spinner("Loading Yahoo league and roster..."):
                league = client.fetch_league(team.league_key)
                roster = client.fetch_team_roster(team.team_key)
    except Exception as exc:
        st.error("Fantasy HQ could not load this Yahoo league.")
        st.caption(str(exc))
        return

    section(
        league.name,
        f"Yahoo · {league.season or 'NFL'} · "
        f"{league.num_teams or '?'} teams",
    )

    metrics = st.columns(4)
    metrics[0].metric("My team", team.name)
    metrics[1].metric("Teams", league.num_teams or "—")
    metrics[2].metric("Current week", league.current_week or "—")
    metrics[3].metric(
        "Draft",
        (
            league.draft_status.replace("_", " ").title()
            if league.draft_status
            else "—"
        ),
    )

    roster_tab, settings_tab = st.tabs(["My roster", "League"])
    with roster_tab:
        if not roster:
            st.info("Yahoo returned an empty roster.")
        else:
            rows = [
                {
                    "Player": player.name,
                    "Pos": player.display_position or "—",
                    "NFL": player.nfl_team or "FA",
                    "Fantasy role": player.selected_position or "—",
                    "Status": player.status or "Active",
                }
                for player in roster
            ]
            starter_rows = [
                row
                for row in rows
                if row["Fantasy role"] not in {"BN", "IR", "IL", "NA"}
            ]
            bench_rows = [
                row
                for row in rows
                if row["Fantasy role"] in {"BN", "IR", "IL", "NA"}
            ]
            st.dataframe(
                pd.DataFrame(starter_rows + bench_rows),
                hide_index=True,
                width="stretch",
            )
            st.caption(
                f"{len(starter_rows)} starters · "
                f"{len(bench_rows)} bench/reserve"
            )

    st.markdown(
        "[Fantasy data provided by Yahoo Fantasy]"
        "(https://football.fantasysports.yahoo.com/)"
    )

    with settings_tab:
        st.dataframe(
            pd.DataFrame(
                [
                    ("Platform", "Yahoo"),
                    ("League", league.name),
                    ("Season", league.season or "—"),
                    ("Teams", league.num_teams or "—"),
                    ("Current week", league.current_week or "—"),
                    ("Scoring type", league.scoring_type or "—"),
                    ("Draft status", league.draft_status or "—"),
                ],
                columns=["Setting", "Value"],
            ),
            hide_index=True,
            width="stretch",
        )


page_intro(
    "Fantasy HQ",
    "Your live Sleeper fantasy command center. Yahoo is optional and can wait.",
)

st.caption(
    "Owner tool · live read-only Sleeper data · "
    "the site-wide historical research badge above is separate from Fantasy HQ freshness"
)

yahoo_config = _yahoo_config()
_handle_yahoo_callback(yahoo_config)

try:
    yahoo_access_token = _refresh_yahoo_if_needed(yahoo_config)
except Exception as exc:
    yahoo_access_token = None
    st.warning("Yahoo authorization needs to be refreshed.")
    st.caption(str(exc))

source_a, source_b = st.columns(2)
with source_a:
    with st.container(border=True):
        st.markdown("### Sleeper")
        st.success("Live")
        st.caption("Public read-only API · username discovery")
with source_b:
    with st.container(border=True):
        st.markdown("### Yahoo")
        if yahoo_access_token:
            st.success("Connected")
            st.caption("Optional provider · already authorized")
        else:
            st.info("Optional · parked")
            st.caption("Not required to use Fantasy HQ or your Sleeper tools")

sleeper_tab, yahoo_tab = st.tabs(["Sleeper leagues", "Yahoo leagues"])
with sleeper_tab:
    _render_sleeper()
with yahoo_tab:
    _render_yahoo(yahoo_config, yahoo_access_token)

st.divider()
st.caption(
    "Fantasy HQ currently includes live Sleeper league discovery, all-leagues action center, "
    "roster health, lineup checks, waiver tools, opponent scouting, league activity, "
    "standings/settings, cross-league ownership, and player exposure."
)
