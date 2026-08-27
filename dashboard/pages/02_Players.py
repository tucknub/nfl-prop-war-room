from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from access_control import access_mode
from glitch_radar_present import format_american, local_start_label
from glitch_radar_props_cache import shared_prop_snapshot
from player_command_center import build_player_prop_context
from src.fantasy.identity import (
    MATCHED,
    load_ffverse_player_ids,
    resolve_propwar_player_to_sleeper,
)
from src.fantasy.league_selector import build_sleeper_league_options
from src.fantasy.player_intelligence import build_player_intelligence_card
from src.fantasy.sleeper import SleeperClient

from research_data import (
    ROLE_LABELS, available_seasons, load_production_data, load_situational_data,
    opponent_from_game_id, player_profile, player_selector_rows, player_window_table,
    primary_rows, team_window_summary,
)
from research_ui import (
    enable_browser_history_sync, initialize_query_control, kpi_row, methodology_expander,
    nfl_week_axis_values, note, page_intro, parse_int, query_value, ratio_text,
    responsive_table, role_noun, searchable_selectbox, section, selection_summary,
    source_footer, update_query_from_widget,
)
from supporting_evidence import home_evidence_message, player_role_sentence, role_fingerprint_contexts
from role_change import build_role_change_signal


def _whole(value: object) -> int:
    return 0 if pd.isna(value) else int(float(value))


def _mapping(value) -> dict:
    try:
        return dict(value.to_dict()) if hasattr(value, "to_dict") else dict(value)
    except Exception:
        return {}


def _owner_mode() -> bool:
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
    return (
        str(st.session_state.get("fantasy_hq_sleeper_username") or "").strip()
        or _secret_default("FANTASY_HQ_SLEEPER_USERNAME")
    )


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


def _render_owner_command_center(
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
        "Player Command Center",
        "Owner-only live sportsbook + Sleeper context for this same exact player identity.",
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
                league_options = dict(
                    build_sleeper_league_options(raw_leagues)
                )
                league_ids = tuple(league_options.values())
                all_states = _command_all_league_states(
                    str(sleeper_user["user_id"]),
                    league_ids,
                )
            except Exception as exc:
                st.warning("Fantasy ownership context could not be loaded.")
                st.caption(str(exc))
                all_states = ()
                league_options = {}

            if all_states and league_options:
                preferred_label = str(
                    st.session_state.get("fantasy_hq_sleeper_league") or ""
                ).strip()
                labels = tuple(league_options)
                default_index = (
                    labels.index(preferred_label)
                    if preferred_label in labels
                    else 0
                )
                selected_label = st.selectbox(
                    "Fantasy league context",
                    labels,
                    index=default_index,
                    key=f"player_command_league_{propwar_player_id}",
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
                try:
                    card = build_player_intelligence_card(
                        selected_league,
                        all_states,
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
                    fan_b.metric(
                        "Current owner",
                        card.selected_league_owner or (
                            "Available"
                            if card.is_available_here
                            else "—"
                        ),
                    )
                    fan_c.metric(
                        "Current slot",
                        card.selected_league_slot or "—",
                    )
                    fan_d.metric(
                        "My exposure",
                        f"{card.my_league_count}/{len(all_states)} leagues",
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
                            f"**FANTASY ACTION:** OWNED · {card.selected_league_owner or 'another manager'} has this player. "
                            "Use Manager Intelligence for roster-fit trade context."
                        )
                    else:
                        st.caption("Fantasy ownership is not safe enough to classify for this league.")

                    ownership_rows = [
                        {
                            "League": row.league_name,
                            "Status": row.status.replace("_", " ").title(),
                            "Owner": row.owner_name or "—",
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


enable_browser_history_sync()
page_intro("Player Role Profile", "What role does this player currently have, and how has it changed?")
summary_slot = st.empty()
seasons = available_seasons()
season_state = initialize_query_control("players", "season", "players_season", seasons, parser=parse_int)
with st.expander("Change season"):
    season = st.selectbox("Season", seasons, key="players_season", on_change=update_query_from_widget, args=("season", "players_season"), kwargs={"clear_query": ("player", "family", "week")})

data = primary_rows()
season_data = data[data["season"].eq(season)]
week_text = query_value("week")
requested_week = int(week_text) if week_text.isdigit() else None
season_weeks = sorted(season_data["week"].dropna().astype(int).unique().tolist())
if requested_week is not None and requested_week not in season_weeks:
    st.warning(f"Week not found for {season}: {week_text}")
    st.stop()
selector_week = requested_week if requested_week is not None else max(season_weeks)
players = player_selector_rows(season_data, selector_week)
player_options = players["player_id"].astype(str).tolist()
labels = players.set_index(players["player_id"].astype(str)).apply(lambda row: f"{row['player_name']} · {row['team']} · {row['position']}", axis=1).to_dict()
player_state = initialize_query_control("players", "player", "players_player", player_options)
selector_cols = st.columns([2.2, 1.2])
with selector_cols[0]:
    player_id = searchable_selectbox("Search or select player", player_options, format_func=lambda value: labels.get(value, value), key="players_player", on_change=update_query_from_widget, args=("player", "players_player"), kwargs={"clear_query": ("family",)})
family_rows = season_data[season_data["player_id"].astype(str).eq(player_id)]
families = family_rows["role_family"].dropna().astype(str).unique().tolist()
family_state = initialize_query_control("players", "family", "players_family", families)
with selector_cols[1]:
    role_family = st.selectbox("Role family", families, format_func=ROLE_LABELS.get, key="players_family", on_change=update_query_from_widget, args=("family", "players_family"))
if season_state.invalid_query or player_state.invalid_query or family_state.invalid_query:
    if season_state.invalid_query: st.warning("The requested season was not found.")
    if player_state.invalid_query: st.warning("Player not found. Search for and select a valid player.")
    if family_state.invalid_query: st.warning("The requested role family is unavailable for this player.")
    st.stop()

profile = player_profile(player_id, season, role_family)
if requested_week is not None:
    profile = profile[profile["week"].le(requested_week)].copy()
if profile.empty:
    st.info("No player rows match the selected filters.")
    st.stop()
player = profile.iloc[-1]
end_week = requested_week if requested_week is not None else int(profile["week"].max())
selection_summary(f"{player['player_name']} · {player['team']} · {player['position']}", f"{season} · {ROLE_LABELS[role_family]}", f"{profile['week'].nunique()} qualifying games through Week {end_week}", target=summary_slot)

if (
    query_value("origin") == "home"
    and query_value("focus") == player_id
    and query_value("focus_family") == role_family
):
    origin_message = home_evidence_message(
        season, end_week, player_id, role_family, team=str(player["team"])
    )
    if origin_message:
        note(origin_message)

windows = player_window_table(profile, end_week)
window_index = windows.set_index("Window")
team_rank_rows = team_window_summary(season, str(player["team"]), role_family, end_week, "Season", "Normal game")
rank_positions = team_rank_rows.reset_index().loc[team_rank_rows.reset_index()["player_id"].astype(str).eq(player_id), "index"]
role_rank = int(rank_positions.iloc[0]) + 1 if not rank_positions.empty else 0

team_last8 = team_window_summary(season, str(player["team"]), role_family, end_week, 8, "Normal game")
team_last2 = team_window_summary(season, str(player["team"]), role_family, end_week, 2, "Normal game")
role_change = build_role_change_signal(
    player_id=player_id,
    position=str(player["position"]),
    windows=windows,
    team_last8=team_last8,
    team_last2=team_last2,
    profile=profile,
)

section(
    "What changed?",
    "Role Change Detector compares normal-game ownership across Last 8, Last 4, and Last 2 without changing the canonical role math.",
)
with st.container(border=True):
    st.markdown(f"### {player['player_name']} — {role_change.classification}")
    change_cols = st.columns(4)
    change_cols[0].metric(
        "Last 8",
        "—" if role_change.last8_share is None else f"{role_change.last8_share:.1%}",
        help=f"{role_change.last8_games} qualifying games",
    )
    change_cols[1].metric(
        "Last 4",
        "—" if role_change.last4_share is None else f"{role_change.last4_share:.1%}",
        help=f"{role_change.last4_games} qualifying games",
    )
    change_cols[2].metric(
        "Last 2",
        "—" if role_change.last2_share is None else f"{role_change.last2_share:.1%}",
        (
            None
            if role_change.shift_pp is None
            else f"{role_change.shift_pp:+.1f} pp vs Last 8"
        ),
        help=f"{role_change.last2_games} qualifying games",
    )
    rank_text = "—"
    if role_change.rank_comparable and role_change.rank_label_last2:
        rank_text = role_change.rank_label_last2
        if (
            role_change.rank_label_last8
            and role_change.rank_label_last8 != role_change.rank_label_last2
        ):
            rank_text = f"{role_change.rank_label_last8} → {role_change.rank_label_last2}"
    change_cols[3].metric("Team role rank", rank_text)

    st.markdown(
        f"**Usage trend:** {role_change.trend}  ·  "
        f"**Confidence:** {role_change.confidence}"
    )
    if role_change.evidence:
        st.caption(" · ".join(role_change.evidence))
    st.caption(
        "Role shift is measured in percentage points of matching normal-game team opportunity. "
        "It is a workload signal, not a projection."
    )

if _owner_mode():
    _render_owner_command_center(
        propwar_player_id=player_id,
        historical_player_name=str(player["player_name"]),
        historical_team=str(player["team"]),
        position=str(player["position"]),
        season=season,
        end_week=end_week,
        role_family=role_family,
        role_change=role_change,
    )

st.info(player_role_sentence(
    str(player["player_name"]), str(player["team"]), str(player["position"]), ROLE_LABELS[role_family],
    role_rank, len(team_rank_rows), float(window_index.loc["Season", "Normal share"]),
    float(window_index.loc["Last 4", "Normal share"]), int(window_index.loc["Last 4", "Games"]),
))

def _window_detail(label: str) -> str:
    row = window_index.loc[label]
    games = int(row["Games"])
    nominal = None if label == "Season" else int(label.split()[-1])
    suffix = f" · fewer than {nominal}" if nominal and games < nominal else ""
    return f"{int(row['Normal raw'])} / {int(row['Normal denominator'])} · {games} games{suffix}"

kpi_row([(label, f"{window_index.loc[label, 'Normal share']:.1%}", _window_detail(label)) for label in ["Season", "Last 8", "Last 4", "Last 2"]])
suspected_weeks = profile.loc[profile["suspected_partial_game"], "week"].astype(int).tolist()
kpi_items = [
    ("Normal-game count", f"{int(profile['raw_opportunities_normal'].sum())} / {int(profile['team_opportunities_normal'].sum())}", "Player / team opportunities"),
    ("Team role rank", f"{role_rank} of {len(team_rank_rows)}", ROLE_LABELS[role_family]),
    ("Qualifying games", str(profile["week"].nunique()), f"Through Week {end_week}"),
]
if suspected_weeks:
    kpi_items.append(("Participation", "Suspected", "Weeks " + ", ".join(map(str, suspected_weeks)) + " remain included"))
kpi_row(kpi_items)

section("Weekly opportunity", "Normal game and all plays remain separate; hover for counts.")
chart_mode = st.segmented_control("Chart measure", ["Share", "Raw opportunities", "Team denominator"], default="Share", label_visibility="collapsed", key="players_chart_measure")
if chart_mode == "Share":
    chart_data = profile[["week", "metric_all", "metric_normal", "raw_opportunities_all", "team_opportunities_all", "raw_opportunities_normal", "team_opportunities_normal"]].melt(
        id_vars=["week", "raw_opportunities_all", "team_opportunities_all", "raw_opportunities_normal", "team_opportunities_normal"], value_vars=["metric_all", "metric_normal"], var_name="series", value_name="value"
    )
    chart_data["Series"] = chart_data["series"].map({"metric_all": "All plays", "metric_normal": "Normal game"})
    chart_data["Raw"] = chart_data.apply(lambda row: row["raw_opportunities_all"] if row["series"] == "metric_all" else row["raw_opportunities_normal"], axis=1)
    chart_data["Denominator"] = chart_data.apply(lambda row: row["team_opportunities_all"] if row["series"] == "metric_all" else row["team_opportunities_normal"], axis=1)
    y = alt.Y("value:Q", title="Share", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0, 1]))
else:
    source = "raw_opportunities_all" if chart_mode == "Raw opportunities" else "team_opportunities_all"
    chart_data = profile[["week", "raw_opportunities_all", "team_opportunities_all"]].copy()
    chart_data["value"] = chart_data[source]
    chart_data = chart_data.rename(columns={"raw_opportunities_all": "Raw", "team_opportunities_all": "Denominator"})
    chart_data["Series"] = chart_mode
    y = alt.Y("value:Q", title=chart_mode)
chart_data = chart_data.rename(columns={"week": "Week"}).dropna(subset=["Week", "value"])
if chart_data["Week"].nunique() < 2:
    st.info("Fewer than two qualifying weekly points are available; no trend line is shown.")
else:
    chart = alt.Chart(chart_data).mark_line(point=alt.OverlayMarkDef(size=48), strokeWidth=2.2).encode(
        x=alt.X("Week:Q", scale=alt.Scale(domain=[1, 18]), axis=alt.Axis(values=nfl_week_axis_values(), tickMinStep=1, title="NFL week")),
        y=y, color=alt.Color("Series:N", legend=alt.Legend(orient="top", title=None)),
        tooltip=[alt.Tooltip("Week:Q", format=".0f"), "Series:N", alt.Tooltip("value:Q", format=".1%" if chart_mode == "Share" else ".0f"), alt.Tooltip("Raw:Q", format=".0f"), alt.Tooltip("Denominator:Q", format=".0f")],
    ).properties(height=245)
    st.altair_chart(chart, width="stretch")

profile_weeks = set(profile["week"].dropna().astype(int))
bye_weeks, missing_weeks = [], []
assignments = profile[["week", "team"]].drop_duplicates().sort_values("week")
for week in range(1, end_week + 1):
    if week in profile_weeks:
        continue
    prior_assignment = assignments[assignments["week"].le(week)]
    assigned_team = str(prior_assignment.iloc[-1]["team"] if not prior_assignment.empty else assignments.iloc[0]["team"])
    team_played = bool((season_data["team"].eq(assigned_team) & season_data["week"].eq(week)).any())
    (missing_weeks if team_played else bye_weeks).append(week)
status = []
if bye_weeks: status.append("Bye: " + ", ".join(map(str, bye_weeks)))
if missing_weeks: status.append("Team played; no qualifying player row: " + ", ".join(map(str, missing_weeks)))
if status: note(" · ".join(status))

if season >= 2023:
    section("Role fingerprint", "Up to six useful contexts that describe the player's assignment.")
    situation = load_situational_data()
    situation = situation[(situation["season"].eq(season)) & (situation["week"].le(end_week)) & situation["player_id"].astype(str).eq(player_id) & situation["role_family"].eq(role_family)]
    situation = situation[situation["context"].isin(role_fingerprint_contexts(role_family))]
    situ = situation.groupby("context", as_index=False).agg(Raw=("raw_opportunities", "sum"), Denominator=("team_opportunities", "sum"), Games=("game_id", "nunique")) if not situation.empty else pd.DataFrame()
    if not situ.empty:
        situ = situ[situ["Denominator"].gt(0)].copy()
        situ["Share"] = situ["Raw"] / situ["Denominator"] * 100
        situ["Context"] = situ["context"].str.replace("_", " ").str.title()
        cards = [{"title": row["Context"], "subtitle": f"{int(row['Games'])} qualifying games", "metrics": [("Ownership", ratio_text(row["Raw"], row["Denominator"], role_noun(role_family)), "Player / same-team opportunities")]} for _, row in situ.iterrows()]
        responsive_table(situ[["Context", "Raw", "Denominator", "Share", "Games"]], cards, key="player_situational", height=360, percent_columns=["Share"])
    else:
        st.info("No valid situational denominators are available for this player.")

section("Team comparison", "Who shares this same team opportunity?")
peer_cards = [{"rank": f"#{rank}", "title": row["player_name"], "subtitle": f"{player['team']} · {row['position']}", "metrics": [("Season ownership", ratio_text(row["raw_opportunities"], row["team_denominator"], role_noun(role_family)), "Normal game")], "href": f"/players?player={row['player_id']}&season={season}&family={role_family}&week={end_week}"} for rank, (_, row) in enumerate(team_rank_rows.head(6).iterrows(), 1)]
peer_table = team_rank_rows.head(10).copy()
peer_table["Share"] = peer_table["share"] * 100
peer_table = peer_table.rename(columns={"player_name": "Player", "position": "Position", "raw_opportunities": "Raw", "team_denominator": "Denominator", "sample_games": "Games"})
responsive_table(peer_table[["Player", "Position", "Raw", "Denominator", "Share", "Games"]], peer_cards, key="player_peers", height=360, percent_columns=["Share"])

section("Weekly counts", "Each row retains its game-week team assignment.")
game_log = profile.copy()
game_log["Opponent"] = game_log.apply(lambda row: opponent_from_game_id(row["game_id"], row["team"]), axis=1)
production = load_production_data()
production = production[production["season"].eq(season) & production["player_id"].astype(str).eq(player_id)]
if not production.empty:
    game_log = game_log.merge(production[["game_id", "carries", "targets", "receptions", "rushing_yards", "receiving_yards"]], on="game_id", how="left")
cards = []
for _, row in game_log.sort_values("week", ascending=False).iterrows():
    participation = str(row["partial_game_note"])
    cards.append({"rank": f"Week {int(row['week'])}", "title": f"{row['team']} vs {row['Opponent']}", "subtitle": participation if "Suspected" in participation else f"{row['team']} segment", "metrics": [("All plays", ratio_text(row["raw_opportunities_all"], row["team_opportunities_all"], role_noun(role_family)), "Player / team"), ("Normal game", ratio_text(row["raw_opportunities_normal"], row["team_opportunities_normal"], role_noun(role_family)), "Player / team"), ("Production", f"{_whole(row.get('carries'))} carries · {_whole(row.get('targets'))} targets", f"{_whole(row.get('receptions'))} receptions")]})
display = game_log[["week", "team", "Opponent", "raw_opportunities_all", "team_opportunities_all", "metric_all", "raw_opportunities_normal", "team_opportunities_normal", "metric_normal", "partial_game_note"]].rename(columns={"week": "Week", "team": "Team", "raw_opportunities_all": "All raw", "team_opportunities_all": "All denominator", "metric_all": "All share", "raw_opportunities_normal": "Normal raw", "team_opportunities_normal": "Normal denominator", "metric_normal": "Normal share", "partial_game_note": "Participation"})
display["All share"] *= 100
display["Normal share"] *= 100
responsive_table(display, cards, key="player_weekly", height=520, percent_columns=["All share", "Normal share"])

team_history = profile[["week", "team"]].drop_duplicates().sort_values("week")
if team_history["team"].nunique() > 1:
    segments = ", ".join(f"{team_name} Weeks {group['week'].min()}–{group['week'].max()}" for team_name, group in team_history.groupby("team", sort=False))
    note(f"Team history: {segments}. The heading reflects the selected boundary; weekly rows retain game-week teams.")

methodology_expander([
    "Window shares sum player and matching team opportunities before division.",
    "Bye weeks are distinguished from weeks when the team played without a qualifying player row.",
    "Confirmed partial games remain excluded; suspected rows remain visible and included.",
])
source_footer("Canonical player identity and team-week attribution are preserved.")
