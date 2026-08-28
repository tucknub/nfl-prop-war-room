from __future__ import annotations

import pandas as pd
import streamlit as st

from access_control import access_mode
from glitch_radar_present import format_american, local_start_label
from glitch_radar_props_cache import shared_prop_snapshot
from player_command_center import build_player_prop_context
from research_data import ROLE_LABELS
from research_ui import section
try:
    from owner_preferences import remembered_sleeper_username
except ImportError:
    from dashboard.owner_preferences import remembered_sleeper_username

from src.fantasy.identity import (
    MATCHED,
    load_ffverse_player_ids,
    resolve_propwar_player_to_sleeper,
)
from src.fantasy.league_selector import (
    build_sleeper_league_options,
    choose_sleeper_league_label,
)
from src.fantasy.player_intelligence import build_player_intelligence_card
from src.fantasy.sleeper import SleeperClient


DEMO_LEAGUE_NAMES = {"test league", "mock league", "demo league"}


def _is_demo_league(row: dict) -> bool:
    return str(row.get("name") or "").strip().casefold() in DEMO_LEAGUE_NAMES


def _mapping(value) -> dict:
    try:
        return dict(value.to_dict()) if hasattr(value, "to_dict") else dict(value)
    except Exception:
        return {}


def owner_player_command_available() -> bool:
    try:
        secrets = _mapping(st.secrets)
    except Exception:
        secrets = {}
    try:
        user = _mapping(st.user)
    except Exception:
        user = {}
    return access_mode(secrets, user) == "OWNER"


def _secret_default(key: str) -> str:
    try:
        return str(st.secrets.get(key, "") or "").strip()
    except Exception:
        return ""


def _remembered_sleeper_username() -> str:
    return remembered_sleeper_username()


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def _command_ffverse_ids() -> pd.DataFrame:
    return load_ffverse_player_ids()


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False)
def _command_player_catalog() -> dict:
    with SleeperClient() as client:
        return {
            str(player_id): dict(player)
            for player_id, player in client.fetch_players().items()
        }


@st.cache_data(ttl=60, show_spinner=False, refresh_mode="background")
def _command_nfl_state():
    with SleeperClient() as client:
        return client.fetch_nfl_state()


@st.cache_data(ttl=300, show_spinner=False, refresh_mode="background")
def _command_sleeper_user(username: str) -> dict:
    with SleeperClient() as client:
        return dict(client.fetch_user(username))


@st.cache_data(ttl=120, show_spinner=False, refresh_mode="background")
def _command_user_leagues(user_id: str, season: str) -> tuple[dict, ...]:
    with SleeperClient() as client:
        return tuple(
            dict(row)
            for row in client.fetch_user_leagues(user_id, season=season)
        )


@st.cache_data(ttl=120, show_spinner=False, refresh_mode="background")
def _command_all_league_states(
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


def _player_name_from_sleeper(player: dict, fallback: str) -> str:
    return (
        str(player.get("full_name") or "").strip()
        or (
            str(player.get("first_name") or "").strip()
            + " "
            + str(player.get("last_name") or "").strip()
        ).strip()
        or fallback
    )


def render_owner_player_command_center(
    *,
    propwar_player_id: str,
    historical_player_name: str,
    historical_team: str,
    position: str,
    season: int,
    end_week: int,
    role_family: str,
    role_change,
) -> None:
    section(
        "Live decision context",
        "Owner-only sportsbook + Sleeper context for this same exact player identity.",
    )

    try:
        reverse = resolve_propwar_player_to_sleeper(
            propwar_player_id,
            ffverse_player_ids=_command_ffverse_ids(),
        )
    except Exception as exc:
        st.warning("Live player identity could not be resolved.")
        st.caption(str(exc))
        return

    if reverse.status != MATCHED or not reverse.sleeper_id:
        st.info(
            "Live command data is withheld because this PropWar player does not have one exact maintained Sleeper ID."
        )
        if reverse.reason_codes:
            st.caption("Identity: " + " · ".join(reverse.reason_codes))
        return

    try:
        catalog = _command_player_catalog()
        sleeper_player = dict(catalog.get(reverse.sleeper_id) or {})
    except Exception as exc:
        st.warning("Current Sleeper player metadata could not be loaded.")
        st.caption(str(exc))
        return

    if not sleeper_player:
        st.info("The exact Sleeper ID is known, but the current Sleeper player catalog returned no metadata.")
        return

    current_name = _player_name_from_sleeper(
        sleeper_player,
        historical_player_name,
    )
    current_team = (
        str(sleeper_player.get("team") or "FA").strip().upper()
        or "FA"
    )
    current_position = (
        str(sleeper_player.get("position") or position).strip().upper()
        or position
    )

    try:
        nfl_state = _command_nfl_state()
        live_season = str(
            getattr(nfl_state, "league_season", None)
            or getattr(nfl_state, "season", None)
            or ""
        ).strip()
    except Exception:
        nfl_state = None
        live_season = ""

    with st.container(border=True):
        st.markdown(f"### {current_name} · {current_team} · {current_position}")
        identity_bits = [
            f"PropWar {propwar_player_id}",
            f"Sleeper {reverse.sleeper_id}",
            "exact maintained ID match",
        ]
        st.caption(" · ".join(identity_bits))

        top_a, top_b, top_c, top_d = st.columns(4)
        top_a.metric("Role signal", role_change.classification)
        top_b.metric("Usage trend", role_change.trend)
        top_c.metric(
            "Role shift",
            (
                f"{role_change.shift_pp:+.1f} pp"
                if role_change.shift_pp is not None
                else "—"
            ),
            help="Last 2 vs Last 8 normal-game share",
        )
        top_d.metric("Role confidence", role_change.confidence)

        role_context = (
            f"Historical role evidence: {season} through Week {end_week} · "
            f"{ROLE_LABELS.get(role_family, role_family)} · {historical_team}"
        )
        st.caption(role_context)
        if current_team != str(historical_team).strip().upper():
            st.warning(
                f"Team changed across contexts: historical role rows show {historical_team}; "
                f"current Sleeper metadata shows {current_team}."
            )

        comparable = bool(live_season and str(season) == live_season)
        if not comparable:
            st.info(
                "ROLE/LINE MISMATCH: NOT SCORED — historical role evidence and the live sportsbook context "
                "are from different seasons. PropWar will not manufacture a cross-season workload edge."
            )

        st.markdown("#### Live sportsbook")
        parlay_key = _secret_default("PARLAY_API_KEY")
        prop_context = None
        deep = None
        if not parlay_key:
            st.caption("PARLAY_API_KEY is not configured, so live player-prop context is unavailable.")
        else:
            try:
                with st.spinner("Loading shared live prop snapshot..."):
                    deep = shared_prop_snapshot(parlay_key)
                prop_context = build_player_prop_context(
                    deep.get("rows", ()) or (),
                    player_name=current_name,
                    nfl_team=current_team,
                    price_outliers=deep.get("price_outliers", ()) or (),
                    line_gaps=deep.get("line_gaps", ()) or (),
                    ladder_violations=deep.get("ladder_violations", ()) or (),
                )
            except Exception as exc:
                st.warning("Live sportsbook context could not be loaded.")
                st.caption(str(exc))

        if prop_context is not None:
            market_a, market_b, market_c = st.columns(3)
            market_a.metric(
                "Game",
                prop_context.games[0] if prop_context.games else "—",
            )
            market_b.metric("Prop markets", prop_context.market_count)
            market_c.metric("Books visible", prop_context.book_count)

            action = prop_context.action
            if action.action in {"CHECK", "SHOP"}:
                st.warning(f"**PROP ACTION: {action.action}** — {action.headline}")
            elif action.action == "NO EDGE FLAGGED":
                st.success(f"**PROP ACTION: {action.action}**")
            else:
                st.info(f"**PROP ACTION: {action.action}** — {action.headline}")
            st.caption(action.reason)

            if action.book:
                action_parts = [action.book]
                if action.side:
                    action_parts.append(action.side)
                if action.line is not None:
                    action_parts.append(f"{action.line:g}")
                if action.price is not None:
                    action_parts.append(format_american(action.price))
                st.write("**Primary price:** " + " · ".join(action_parts))
            if action.peer_book:
                peer_parts = [action.peer_book]
                if action.peer_line is not None:
                    peer_parts.append(f"{action.peer_line:g}")
                if action.peer_price is not None:
                    peer_parts.append(format_american(action.peer_price))
                st.caption("Comparison: " + " · ".join(peer_parts))

            if prop_context.best_prices:
                st.markdown("##### Current best prices at my books")
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Market": row.market_label,
                                "Line": row.line,
                                "Best OVER": (
                                    f"{row.over_book} {format_american(row.over_price)}"
                                    if row.over_book and row.over_price is not None
                                    else "—"
                                ),
                                "Best UNDER": (
                                    f"{row.under_book} {format_american(row.under_price)}"
                                    if row.under_book and row.under_price is not None
                                    else "—"
                                ),
                            }
                            for row in prop_context.best_prices
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )
            if deep and deep.get("fetched_at"):
                st.caption(
                    "Shared Deep Prop Radar snapshot · refreshed "
                    + local_start_label(deep.get("fetched_at"))
                )

        st.markdown("#### Fantasy")
        username = _remembered_sleeper_username()
        if not username:
            st.caption(
                "Fantasy context is not loaded here yet. Open Fantasy HQ once or configure "
                "FANTASY_HQ_SLEEPER_USERNAME; no password is needed."
            )
        else:
            try:
                sleeper_user = _command_sleeper_user(username)
                fantasy_season = live_season or str(
                    getattr(nfl_state, "season", "") or ""
                ).strip()
                raw_leagues = _command_user_leagues(
                    str(sleeper_user["user_id"]),
                    fantasy_season,
                )
                real_leagues = tuple(
                    row for row in raw_leagues if not _is_demo_league(row)
                )
                demo_leagues = tuple(
                    row for row in raw_leagues if _is_demo_league(row)
                )
                ordered_leagues = (
                    (*real_leagues, *demo_leagues)
                    if real_leagues
                    else tuple(raw_leagues)
                )
                league_options = dict(
                    build_sleeper_league_options(ordered_leagues)
                )
                league_ids = tuple(league_options.values())
                all_states = _command_all_league_states(
                    str(sleeper_user["user_id"]),
                    league_ids,
                )
                real_league_ids = {
                    str(row.get("league_id") or "").strip()
                    for row in real_leagues
                    if str(row.get("league_id") or "").strip()
                }
                real_states = tuple(
                    state
                    for state in all_states
                    if state.platform_league_id in real_league_ids
                )
            except Exception as exc:
                st.warning("Fantasy ownership context could not be loaded.")
                st.caption(str(exc))
                all_states = ()
                league_options = {}

            if all_states and league_options:
                labels = tuple(league_options)
                demo_ids = {
                    str(row.get("league_id") or "").strip()
                    for row in raw_leagues
                    if _is_demo_league(row)
                    and str(row.get("league_id") or "").strip()
                }
                selector_key = (
                    f"player_command_league_v2_{propwar_player_id}"
                )
                initial_label = choose_sleeper_league_label(
                    league_options,
                    demo_league_ids=demo_ids,
                    current_label=str(
                        st.session_state.get(selector_key) or ""
                    ),
                    legacy_label=str(
                        st.session_state.get("fantasy_hq_sleeper_league") or ""
                    ),
                    prefer_real=bool(real_states),
                )
                if (
                    initial_label
                    and str(st.session_state.get(selector_key) or "").strip()
                    not in league_options
                ):
                    st.session_state[selector_key] = initial_label

                selected_label = st.selectbox(
                    "Fantasy league context",
                    labels,
                    key=selector_key,
                )
                selected_id = league_options[selected_label]
                selected_league = next(
                    (
                        league
                        for league in all_states
                        if league.platform_league_id == selected_id
                    ),
                    all_states[0],
                )
                card_states = (
                    real_states
                    if real_states
                    and selected_league.platform_league_id not in demo_ids
                    else (selected_league,)
                )
                try:
                    card = build_player_intelligence_card(
                        selected_league,
                        card_states,
                        reverse.sleeper_id,
                        catalog,
                    )
                except Exception as exc:
                    st.warning("Fantasy player intelligence could not be built.")
                    st.caption(str(exc))
                    card = None

                if card is not None:
                    fan_a, fan_b, fan_c, fan_d = st.columns(4)
                    status_label = card.selected_league_status.replace("_", " ").title()
                    fan_a.metric("This league", status_label)
                    owner_label = card.selected_league_owner or (
                        "Available"
                        if card.is_available_here
                        else "Other roster"
                        if card.selected_league_status == "OTHER"
                        else "—"
                    )
                    fan_b.metric(
                        "Current owner",
                        owner_label,
                    )
                    fan_c.metric(
                        "Current slot",
                        card.selected_league_slot or "—",
                    )
                    fan_d.metric(
                        "My exposure",
                        f"{card.my_league_count}/{len(card_states)} leagues",
                    )

                    if card.selected_league_status == "MINE":
                        st.success(
                            f"**FANTASY ACTION:** MY ROSTER · currently {card.selected_league_slot or 'rostered'} in {selected_league.name}."
                        )
                    elif card.selected_league_status == "AVAILABLE":
                        st.info(
                            f"**FANTASY ACTION:** AVAILABLE · evaluate this player against {selected_league.name}'s roster needs."
                        )
                    elif card.selected_league_status == "OTHER":
                        st.info(
                            f"**FANTASY ACTION:** OWNED · {card.selected_league_owner or 'another roster'} has this player. "
                            "Use Manager Intelligence for roster-fit trade context."
                        )
                    else:
                        st.caption("Fantasy ownership is not safe enough to classify for this league.")

                    ownership_rows = [
                        {
                            "League": row.league_name,
                            "Status": row.status.replace("_", " ").title(),
                            "Owner": row.owner_name or (
                                "Other roster" if row.status == "OTHER" else "—"
                            ),
                            "Slot": row.roster_slot or "—",
                        }
                        for row in card.ownership
                    ]
                    if ownership_rows:
                        with st.expander("Cross-league ownership / exposure"):
                            st.dataframe(
                                pd.DataFrame(ownership_rows),
                                hide_index=True,
                                width="stretch",
                            )

        st.caption(
            "Command Center combines exact identity-linked facts from separate systems. "
            "Historical role evidence stays labeled separately from live 2026 market/fantasy context until same-season role data exists."
        )



__all__ = [
    "owner_player_command_available",
    "render_owner_player_command_center",
]
