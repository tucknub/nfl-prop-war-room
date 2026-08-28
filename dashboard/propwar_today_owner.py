from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

try:
    from access_control import access_mode
    from glitch_radar_action import BET, PASS, WATCH, ev_action, glitch_action
    from glitch_radar_books import filter_actionable_alerts, filter_actionable_ev
    from glitch_radar_grouping import market_label
    from glitch_radar_live import build_snapshot
    from glitch_radar_present import (
        expected_ev_pct,
        event_phase_label,
        fair_american_from_probability,
        format_american,
        game_name,
        local_start_label,
    )
    from glitch_radar_props_cache import shared_prop_snapshot
    from propwar_today import (
        FANTASY,
        HIGH,
        LOW,
        MARGIN,
        MARKET,
        MEDIUM,
        ROLE,
        TodayAction,
        rank_today_actions,
    )
    from research_data import (
        ROLE_LABELS,
        available_seasons,
        available_weeks,
        primary_rows,
        team_window_summary,
    )
    from role_change import DROP, SURGE, build_team_role_change_table
except ImportError:
    from dashboard.access_control import access_mode
    from dashboard.glitch_radar_action import BET, PASS, WATCH, ev_action, glitch_action
    from dashboard.glitch_radar_books import filter_actionable_alerts, filter_actionable_ev
    from dashboard.glitch_radar_grouping import market_label
    from dashboard.glitch_radar_live import build_snapshot
    from dashboard.glitch_radar_present import (
        expected_ev_pct,
        event_phase_label,
        fair_american_from_probability,
        format_american,
        game_name,
        local_start_label,
    )
    from dashboard.glitch_radar_props_cache import shared_prop_snapshot
    from dashboard.propwar_today import (
        FANTASY,
        HIGH,
        LOW,
        MARGIN,
        MARKET,
        MEDIUM,
        ROLE,
        TodayAction,
        rank_today_actions,
    )
    from dashboard.research_data import (
        ROLE_LABELS,
        available_seasons,
        available_weeks,
        primary_rows,
        team_window_summary,
    )
    from dashboard.role_change import DROP, SURGE, build_team_role_change_table

try:
    from owner_preferences import remembered_sleeper_username
except ImportError:
    from dashboard.owner_preferences import remembered_sleeper_username

from src.fantasy.action_feed import build_weekly_action_feed
from src.fantasy.sleeper import SleeperClient
from src.fantasy.weekly_context import fetch_league_weekly_contexts
from src.margin import live_engine_v2 as margin_live
from src.margin import state_store


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


def _secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "") or "").strip()
    except Exception:
        return ""


def _remembered_sleeper_username() -> str:
    return remembered_sleeper_username()


@st.cache_data(ttl=600, show_spinner=False, refresh_mode="background")
def _today_market_snapshot() -> dict:
    return build_snapshot()


@st.cache_data(ttl=300, show_spinner=False, refresh_mode="background")
def _today_sleeper_user(username: str) -> dict:
    with SleeperClient() as client:
        return dict(client.fetch_user(username))


@st.cache_data(ttl=60, show_spinner=False, refresh_mode="background")
def _today_nfl_state():
    with SleeperClient() as client:
        return client.fetch_nfl_state()


@st.cache_data(ttl=120, show_spinner=False, refresh_mode="background")
def _today_leagues(user_id: str, season: str) -> tuple[dict, ...]:
    with SleeperClient() as client:
        return tuple(
            dict(row)
            for row in client.fetch_user_leagues(user_id, season=season)
        )


@st.cache_data(ttl=120, show_spinner=False, refresh_mode="background")
def _today_all_states(user_id: str, league_ids: tuple[str, ...]):
    with SleeperClient() as client:
        return client.fetch_normalized_leagues(
            league_ids,
            current_user_id=user_id,
            max_workers=3,
        )


@st.cache_data(ttl=6 * 60 * 60, show_spinner=False, refresh_mode="background")
def _today_player_catalog() -> dict:
    with SleeperClient() as client:
        return {
            str(player_id): dict(player)
            for player_id, player in client.fetch_players().items()
        }


@st.cache_data(ttl=5 * 60, show_spinner=False, refresh_mode="background")
def _today_trending_adds():
    with SleeperClient() as client:
        return client.fetch_trending_players(
            "add",
            lookback_hours=24,
            limit=100,
        )


@st.cache_data(ttl=5 * 60, show_spinner=False, refresh_mode="background")
def _today_fantasy_feed(
    user_id: str,
    league_ids: tuple[str, ...],
    current_week: int,
    parlay_key: str,
):
    states = _today_all_states(user_id, league_ids)
    catalog = _today_player_catalog()
    snapshot = shared_prop_snapshot(parlay_key)
    trends = _today_trending_adds()

    matchup_map = {}
    transaction_map = {}
    errors: list[str] = []

    active_leagues = {
        league.platform_league_id: league
        for league in states
        if (
            league.status != "pre_draft"
            and league.ownership_ready
            and league.my_platform_roster_id
        )
    }
    if current_week >= 1 and active_leagues:
        contexts = fetch_league_weekly_contexts(
            tuple(active_leagues),
            current_week=current_week,
            transaction_weeks=tuple(
                range(max(1, current_week - 3), current_week + 1)
            ),
            max_workers=3,
        )
        for context in contexts:
            league = active_leagues[context.league_id]
            matchup_map[context.league_id] = next(
                (
                    row
                    for row in context.matchups
                    if row.platform_roster_id == league.my_platform_roster_id
                ),
                None,
            )
            transaction_map[context.league_id] = context.transactions
            label = league.name or context.league_id
            errors.extend(
                f"{label} {error}"
                for error in context.errors
            )

    feed = build_weekly_action_feed(
        states,
        catalog,
        snapshot.get("rows", ()),
        current_week=current_week,
        trends=trends,
        matchups_by_league=matchup_map,
        transactions_by_league=transaction_map,
        limit=20,
    )
    return feed, tuple(errors)


@st.cache_data(ttl=5 * 60, show_spinner=False)
def _today_role_actions(live_season: int) -> tuple[TodayAction, ...]:
    seasons = set(available_seasons())
    if live_season not in seasons:
        return ()

    weeks = available_weeks(live_season)
    if not weeks:
        return ()
    end_week = max(int(week) for week in weeks)

    data = primary_rows()
    current = data[
        data["season"].eq(live_season)
        & data["week"].le(end_week)
    ]
    teams = sorted(
        current["team"].dropna().astype(str).unique().tolist()
    )
    actions: list[TodayAction] = []

    for team in teams:
        for family in ROLE_LABELS:
            table = build_team_role_change_table(
                role_family=family,
                last8=team_window_summary(
                    live_season,
                    team,
                    family,
                    end_week,
                    8,
                    "Normal game",
                ),
                last4=team_window_summary(
                    live_season,
                    team,
                    family,
                    end_week,
                    4,
                    "Normal game",
                ),
                last2=team_window_summary(
                    live_season,
                    team,
                    family,
                    end_week,
                    2,
                    "Normal game",
                ),
            )
            if table.empty:
                continue

            strong = table[
                table["classification"].isin({SURGE, DROP})
                & table["confidence"].eq("HIGH")
            ]
            for _, row in strong.iterrows():
                shift = float(row["shift_pp"])
                l8 = float(row["last8_share"]) * 100
                l4 = float(row["last4_share"]) * 100
                l2 = float(row["last2_share"]) * 100
                rank8 = row.get("rank_last8")
                rank2 = row.get("rank_last2")
                rank_text = ""
                if pd.notna(rank8) and pd.notna(rank2):
                    prefix = str(row.get("position") or "")
                    rank_text = (
                        f" · team rank {prefix}{int(rank8)} → "
                        f"{prefix}{int(rank2)}"
                    )
                player_id = str(row["player_id"])
                href = (
                    "/players?"
                    + urlencode(
                        {
                            "player": player_id,
                            "season": live_season,
                            "family": family,
                            "week": end_week,
                        }
                    )
                )
                actions.append(
                    TodayAction(
                        category=ROLE,
                        priority=HIGH,
                        title=(
                            f"{row['player_name']} · "
                            f"{row['classification']}"
                        ),
                        action="Open role evidence",
                        why=(
                            f"Normal-game share {l8:.1f}% → {l4:.1f}% → "
                            f"{l2:.1f}% ({shift:+.1f} pp Last 2 vs Last 8)"
                            f"{rank_text}."
                        ),
                        confidence="HIGH",
                        freshness=f"{live_season} Week {end_week}",
                        href=href,
                        score=335.0 + abs(shift) * 2.0,
                        source="Role Change Detector",
                    )
                )

    return tuple(actions)


@st.cache_data(ttl=300, show_spinner=False)
def _today_margin_state(_config: dict) -> dict:
    state, _ = state_store.fetch_remote_state(_config)
    return state


@st.cache_data(ttl=300, show_spinner=False)
def _today_margin_audit(state_text: str) -> dict:
    return margin_live.run(
        json.loads(state_text),
        future_posted_mode="live",
    )


def _event_time_for_market_row(snapshot: dict, row: dict) -> object:
    direct = row.get("commence_time")
    if direct:
        return direct

    quotes = tuple(
        quote
        for quote in (snapshot.get("quotes", ()) or ())
        if isinstance(quote, dict) and quote.get("commence_time")
    )
    if not quotes:
        return None

    away = str(row.get("away_team") or "").strip()
    home = str(row.get("home_team") or "").strip()
    if away and home:
        expected_event = f"{away} @ {home}".strip().casefold()
        for quote in quotes:
            event = str(quote.get("event") or "").strip().casefold()
            if event == expected_event:
                return quote.get("commence_time")

    # Some EV payloads have arrived without a usable away/home pair even though
    # the same market exists in the live odds payload. Recover the event by the
    # actionable quote itself: book + market + price + team selection.
    selection = str(
        row.get("selection") or row.get("side") or ""
    ).strip().casefold()
    book = str(row.get("book") or "").strip().casefold()
    market = str(row.get("market") or "moneyline").strip().casefold()
    try:
        price = int(float(row.get("price")))
    except (TypeError, ValueError):
        price = None

    candidate_times: list[object] = []
    for quote in quotes:
        quote_book = str(quote.get("book") or "").strip().casefold()
        quote_market = str(quote.get("market") or "").strip().casefold()
        event = str(quote.get("event") or "").strip().casefold()
        try:
            quote_price = int(float(quote.get("odds_american")))
        except (TypeError, ValueError):
            quote_price = None

        if book and quote_book != book:
            continue
        if market and quote_market and quote_market != market:
            continue
        if price is not None and quote_price != price:
            continue
        if selection and selection not in event:
            continue
        candidate_times.append(quote.get("commence_time"))

    unique_times = tuple(dict.fromkeys(candidate_times))
    return unique_times[0] if len(unique_times) == 1 else None


def _market_actions(
    snapshot: dict,
    *,
    force_preseason: bool = False,
) -> tuple[TodayAction, ...]:
    actions: list[TodayAction] = []
    fetched = local_start_label(snapshot.get("fetched_at"))

    alerts = filter_actionable_alerts(
        snapshot.get("alerts", ()) or ()
    )
    for alert in alerts:
        radar = glitch_action(alert)
        if radar.action == PASS:
            continue
        quote = alert.get("quote", {}) or {}
        book = str(quote.get("book") or "Book")
        price = format_american(quote.get("odds_american"))
        market = str(quote.get("market") or "market").replace("_", " ")
        side = str(quote.get("side") or "").strip()
        threshold = quote.get("threshold")
        detail = " ".join(
            value
            for value in (
                market,
                side,
                str(threshold) if threshold is not None else "",
            )
            if value
        )
        edge = float(radar.edge_points or 0.0)
        score = (
            440.0 + max(edge, 0.0) * 4.0
            if radar.action == BET
            else 275.0 + max(edge, 0.0) * 2.0
        )
        actions.append(
            TodayAction(
                category=MARKET,
                priority=HIGH if radar.action == BET else MEDIUM,
                title=f"{book} {price} · {quote.get('event') or 'NFL'}",
                action=radar.action,
                why=(
                    f"{detail or 'Same-market price'} · "
                    f"{radar.reason}"
                ),
                confidence="HIGH" if radar.action == BET else "MEDIUM",
                freshness=f"Glitch Radar · {fetched}",
                href="/glitch-radar",
                score=score,
                source="Glitch Radar",
            )
        )

    ev_rows = filter_actionable_ev(
        snapshot.get("ev", ()) or ()
    )
    for row in ev_rows:
        radar = ev_action(row)
        if radar.action == PASS:
            continue
        selection = str(
            row.get("selection") or row.get("side") or "Bet"
        ).strip()
        display_market = str(
            row.get("display_market") or market_label(row)
        ).strip()
        book = str(row.get("book") or "Book")
        price = format_american(row.get("price"))
        fair_prob = row.get("fair_prob_pct")
        fair = fair_american_from_probability(fair_prob)
        ev = expected_ev_pct(row.get("price"), fair_prob)
        market_event_time = _event_time_for_market_row(snapshot, row)
        phase = event_phase_label(market_event_time)
        is_preseason = force_preseason or phase == "PRESEASON"
        score = (
            410.0 + max(float(ev or 0.0), 0.0) * 3.0
            if radar.action == BET
            else 250.0 + max(float(ev or 0.0), 0.0)
        )
        if is_preseason:
            score = min(score, 245.0 + max(float(ev or 0.0), 0.0))
        actions.append(
            TodayAction(
                category=MARKET,
                priority=(
                    MEDIUM
                    if is_preseason
                    else HIGH if radar.action == BET else MEDIUM
                ),
                title=(
                    f"{selection} {display_market} · "
                    f"{book} {price}"
                ),
                action=radar.action,
                why=(
                    f"{'PRESEASON · ' if is_preseason else ''}"
                    f"Fair line {format_american(fair)} · "
                    f"estimated EV {float(ev):+.1f}% · {radar.reason}"
                    if ev is not None
                    else (
                        f"{'PRESEASON · ' if is_preseason else ''}{radar.reason}"
                    )
                ),
                confidence=(
                    "MEDIUM"
                    if is_preseason
                    else "HIGH" if radar.action == BET else "MEDIUM"
                ),
                freshness=f"Glitch Radar · {fetched}",
                href="/glitch-radar",
                score=score,
                source="Glitch Radar",
            )
        )

    return tuple(actions)


def _fantasy_actions(
    *,
    username: str,
    live_season: str,
    current_week: int,
    parlay_key: str,
) -> tuple[tuple[TodayAction, ...], tuple[str, ...]]:
    if not username or not live_season or not parlay_key:
        return (), ()
    if current_week < 1:
        # Fantasy HQ can still be used for draft/preseason roster work, but its
        # market-backed action feed should not promote preseason NFL prop context
        # as regular-season fantasy evidence on the global homepage.
        return (), ()

    user = _today_sleeper_user(username)
    leagues = _today_leagues(
        str(user["user_id"]),
        live_season,
    )
    active_leagues = tuple(
        row
        for row in leagues
        if str(row.get("status") or "").strip().casefold()
        not in {"pre_draft", "drafting"}
    )
    league_ids = tuple(
        str(row["league_id"])
        for row in active_leagues
        if str(row.get("league_id") or "").strip()
    )
    if not league_ids:
        return (), ()

    feed, errors = _today_fantasy_feed(
        str(user["user_id"]),
        league_ids,
        current_week,
        parlay_key,
    )
    actions: list[TodayAction] = []
    for row in feed.actions:
        impact = (
            f" · {row.impact_points:+.2f} projected lineup pts"
            if row.impact_points is not None
            else ""
        )
        faab = (
            f" · FAAB {row.faab_range}, target {row.faab_target}"
            if row.faab_range and row.faab_target
            else f" · FAAB {row.faab_range}"
            if row.faab_range
            else ""
        )
        actions.append(
            TodayAction(
                category=FANTASY,
                priority=row.priority,
                title=f"{row.league_name} · {row.title}",
                action=row.action,
                why=f"{row.detail}{impact}{faab}",
                confidence=row.confidence,
                freshness=(
                    f"Sleeper live · Week {current_week}"
                    if current_week >= 1
                    else "Sleeper live · preseason"
                ),
                href=(
                    "/fantasy-hq?"
                    + urlencode({"fh_sleeper": username})
                    if username
                    else "/fantasy-hq"
                ),
                score=float(row.score),
                source="Fantasy HQ",
            )
        )
    return tuple(actions), errors


def _margin_missing_field_inputs(state: dict) -> tuple[str, ...]:
    pool = state.get("pool") or {}
    missing: list[str] = []
    if not pool.get("size"):
        missing.append("pool size")
    if not pool.get("pick_deadline"):
        missing.append("pick deadline")
    if pool.get("picks_visible_before_deadline") is None:
        missing.append("pick visibility")
    if not pool.get("first_place_tie_rule"):
        missing.append("tie rule")
    if not (state.get("opponents") or []):
        missing.append("opponent field")
    return tuple(missing)


def _margin_action() -> TodayAction | None:
    try:
        secrets = _mapping(st.secrets)
        config = state_store.config_from_secrets(secrets)
    except Exception:
        config = None
    if config is None or not state_store.owner_write_authorized(config):
        return None

    state = _today_margin_state(config)
    if bool(state.get("season_complete")):
        return None

    state_text = json.dumps(state, sort_keys=True)
    audit = _today_margin_audit(state_text)
    pick = audit["pick"]
    decision = state.get("current_decision") or {}
    committed = (
        str(decision.get("committed_pick") or "")
        if str(decision.get("status") or "") == "COMMITTED"
        else ""
    )
    recommendation = str(pick["team"])
    week = int(state["current_week"])
    missing_field_inputs = _margin_missing_field_inputs(state)
    field_ready = not missing_field_inputs
    confidence = "HIGH" if field_ready else "MEDIUM"

    if committed and committed != recommendation:
        priority = HIGH
        action = f"REVIEW {committed} → {recommendation}"
        why_prefix = (
            f"Your recorded pick is {committed}, but the refreshed engine "
            f"currently prefers {recommendation}."
        )
        score = 395.0
    elif committed:
        priority = MEDIUM
        action = f"HOLD / REVIEW {recommendation}"
        why_prefix = (
            f"Your recorded pick {committed} still matches the current engine."
        )
        score = 285.0
    else:
        priority = HIGH if field_ready else MEDIUM
        action = f"PICK {recommendation}"
        why_prefix = (
            f"No team is recorded yet for Week {week}; the engine currently "
            f"recommends {recommendation}."
        )
        score = 370.0

    return TodayAction(
        category=MARGIN,
        priority=priority,
        title=(
            f"Week {week} · {recommendation} vs {pick['opponent']}"
        ),
        action=action,
        why=(
            f"{why_prefix} Spread {float(pick['current_spread']):+.1f} · "
            f"expected margin {float(pick['calibrated_margin']):+.2f} · "
            f"loss {float(pick['p_loss']) * 100:.1f}% · "
            f"20+ {float(pick['p_win20']) * 100:.1f}%."
            + (
                " Provisional pool context — still missing "
                + ", ".join(missing_field_inputs)
                + "."
                if missing_field_inputs
                else ""
            )
        ),
        confidence=confidence,
        freshness=(
            "Margin engine · "
            + local_start_label(audit.get("snapshot_utc"))
        ),
        href="/margin",
        score=score,
        source="Margin War Room",
    )


def _live_context() -> tuple[str, int, str]:
    try:
        state = _today_nfl_state()
    except Exception:
        return "", 0, ""
    season = str(
        getattr(state, "league_season", None)
        or getattr(state, "season", None)
        or ""
    ).strip()
    season_type = str(
        getattr(state, "season_type", "") or ""
    ).strip().casefold()
    try:
        leg = int(getattr(state, "leg", 0) or 0)
    except (TypeError, ValueError):
        leg = 0
    week = (
        leg
        if season_type in {"regular", "reg"} and 1 <= leg <= 18
        else 0
    )
    return season, week, season_type


def _render_action_card(rank: int, row: TodayAction) -> None:
    with st.container(border=True):
        top_a, top_b = st.columns([4, 1])
        with top_a:
            st.caption(
                f"#{rank} · {row.category} · {row.priority} · {row.source}"
            )
            st.markdown(f"### {row.title}")
        with top_b:
            st.markdown(f"**{row.action}**")

        st.write(row.why)
        st.caption(
            f"Confidence: {row.confidence} · Freshness: {row.freshness}"
        )
        st.link_button(
            f"Open {row.source}",
            row.href,
            width="stretch",
        )


def render_propwar_today_if_owner() -> None:
    if not _owner_mode():
        return

    st.markdown("## What Should I Do?")
    st.caption(
        "The few current actions PropWar believes deserve attention across "
        "markets, fantasy, role changes, and Margin. Every card shows the action, "
        "why it surfaced, confidence, freshness, and the source evidence."
    )

    actions: list[TodayAction] = []
    errors: list[str] = []

    live_season, current_week, season_type = _live_context()
    live_preseason = season_type.startswith("pre")

    try:
        actions.extend(
            _market_actions(
                _today_market_snapshot(),
                force_preseason=live_preseason,
            )
        )
    except Exception as exc:
        errors.append(f"Market radar: {exc}")

    username = _remembered_sleeper_username()
    parlay_key = _secret("PARLAY_API_KEY")
    try:
        fantasy_actions, fantasy_errors = _fantasy_actions(
            username=username,
            live_season=live_season,
            current_week=current_week,
            parlay_key=parlay_key,
        )
        actions.extend(fantasy_actions)
        errors.extend(fantasy_errors)
    except Exception as exc:
        errors.append(f"Fantasy HQ: {exc}")

    if live_season.isdigit():
        try:
            actions.extend(
                _today_role_actions(int(live_season))
            )
        except Exception as exc:
            errors.append(f"Role Change Detector: {exc}")

    try:
        margin = _margin_action()
        if margin is not None:
            actions.append(margin)
    except Exception as exc:
        errors.append(f"Margin War Room: {exc}")

    ranked = rank_today_actions(actions, limit=6)

    status_a, status_b, status_c = st.columns(3)
    status_a.metric("Top actions", len(ranked))
    status_b.metric(
        "HIGH priority",
        sum(row.priority == HIGH for row in ranked),
    )
    status_c.metric(
        "Sources represented",
        len({row.source for row in ranked}),
    )

    if not ranked:
        st.info(
            "No current owner action clears the available feeds right now. "
            "Open the individual tools for diagnostics and coverage."
        )
    else:
        for row_start in range(0, len(ranked), 2):
            row_columns = st.columns(2)
            for offset, row in enumerate(ranked[row_start : row_start + 2]):
                rank = row_start + offset + 1
                with row_columns[offset]:
                    _render_action_card(rank, row)

    if username and current_week < 1:
        st.caption(
            "Fantasy actions are intentionally kept inside Fantasy HQ during preseason; "
            "PropWar Today begins promoting market-backed fantasy moves in the regular season."
        )

    if (
        live_season.isdigit()
        and int(live_season) not in set(available_seasons())
    ):
        st.caption(
            f"Role alerts are not mixed into Today yet because published Role "
            f"Intelligence does not contain {live_season} regular-season workload. "
            "They will activate automatically when same-season role data exists."
        )

    if errors:
        with st.expander("Partial source warnings", expanded=False):
            for error in errors:
                st.caption(error)

    st.caption(
        "PropWar Today composes existing tool outputs; it does not create a "
        "second projection model. Missing or stale sources are omitted rather "
        "than guessed."
    )


__all__ = ["render_propwar_today_if_owner"]
