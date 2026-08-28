from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from access_control import access_mode  # noqa: E402
from glitch_radar_live import american_to_decimal, build_snapshot, evaluate_profit_boost  # noqa: E402
from glitch_radar_books import (  # noqa: E402
    USER_BOOKS,
    comparison_books_seen,
    filter_actionable_alerts,
    filter_actionable_ev,
    filter_actionable_two_leg,
    user_books_seen,
)
from glitch_radar_grouping import market_label  # noqa: E402
from glitch_radar_action import (  # noqa: E402
    BET,
    PASS,
    WATCH,
    ev_action,
    glitch_action,
    peer_implied_probability_gap_range,
    peer_prices_for_alert,
)
from glitch_radar_history import (  # noqa: E402
    BASELINE,
    AGING,
    DISAPPEARED,
    FRESH,
    IMPROVED,
    NEW,
    REAPPEARED,
    STALE,
    UNCHANGED,
    WORSENED,
    MarketHistoryStore,
    build_market_observations,
    ev_opportunity_key,
    glitch_opportunity_key,
    freshness_status,
    history_for_key,
    history_summary,
    recent_history_changes,
    update_market_history,
)
from glitch_radar_history_private import (  # noqa: E402
    PrivateMarketHistoryStore,
    history_config_from_secrets,
)
from src.margin import state_store  # noqa: E402
from glitch_radar_present import (  # noqa: E402
    event_phase_label,
    expected_ev_pct,
    fair_american_from_probability,
    format_american,
    game_name,
    local_start_label,
    probability_edge_points,
    value_tier,
)


def _mapping(value) -> dict:
    try:
        return dict(value.to_dict()) if hasattr(value, "to_dict") else dict(value)
    except Exception:
        return {}


def _require_owner() -> None:
    try:
        secrets = _mapping(st.secrets)
    except Exception:
        secrets = {}
    try:
        user = _mapping(st.user)
    except Exception:
        user = {}
    if access_mode(secrets, user) != "OWNER":
        st.error("Glitch Radar is an owner-only PropWar tool.")
        st.stop()


@st.cache_data(ttl=600, show_spinner=False)
def _live_snapshot() -> dict:
    return build_snapshot()


@st.cache_resource
def _market_history_store() -> MarketHistoryStore:
    return MarketHistoryStore()


@st.cache_resource
def _durable_market_history_store() -> PrivateMarketHistoryStore | None:
    try:
        secrets = _mapping(st.secrets)
    except Exception:
        return None
    config = history_config_from_secrets(secrets)
    if config is None:
        return None
    if not state_store.owner_write_authorized(config):
        return None
    return PrivateMarketHistoryStore(config)


def _pct(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def _number(value: object, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _humanize(key: str) -> str:
    return key.replace("_", " ").replace(".", " · ").strip().title()


def _flat_rows(value: Any, prefix: str = "", limit: int = 32) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def visit(node: Any, path: str) -> None:
        if len(rows) >= limit:
            return
        if isinstance(node, dict):
            for key, child in node.items():
                visit(child, f"{path}.{key}" if path else str(key))
            return
        if isinstance(node, (list, tuple)):
            simple = all(not isinstance(item, (dict, list, tuple)) for item in node)
            if simple:
                rows.append({"Field": _humanize(path), "Value": ", ".join(str(item) for item in node) or "—"})
            else:
                for index, child in enumerate(node, start=1):
                    visit(child, f"{path}.{index}")
            return
        rows.append({"Field": _humanize(path), "Value": "—" if node is None else str(node)})

    visit(value, prefix)
    return rows


def _evidence_table(items: list[tuple[str, object]]) -> None:
    st.table(
        [
            {"Field": label, "Value": "—" if value is None or value == "" else str(value)}
            for label, value in items
        ]
    )


def _event_context(row: dict) -> str:
    pieces = [game_name(row)]
    phase = event_phase_label(row.get("commence_time"))
    if phase:
        pieces.append(phase)
    if row.get("commence_time"):
        pieces.append(local_start_label(row.get("commence_time")))
    return " · ".join(pieces)


def _alternate_text(row: dict) -> str:
    alternates = row.get("alternate_books", []) or []
    values: list[str] = []
    for alternate in alternates:
        if not isinstance(alternate, dict) or not alternate.get("book"):
            continue
        values.append(f"{alternate.get('book')} {format_american(alternate.get('price'))}")
    return ", ".join(values)


def _ev_sort_key(row: dict) -> tuple[int, float]:
    phase_rank = 1 if event_phase_label(row.get("commence_time")) == "PRESEASON" else 0
    ev = expected_ev_pct(row.get("price"), row.get("fair_prob_pct"))
    return phase_rank, -(ev if ev is not None else -999.0)


def _history_price_line(record: dict | None) -> str:
    if not record:
        return ""
    status = str(record.get("status") or "").upper()
    previous = record.get("previous_price")
    current = record.get("current_price")
    book = str(record.get("book") or "Book").strip()
    if status in {IMPROVED, WORSENED} and previous is not None and current is not None:
        return (
            f"{book} moved {format_american(previous)} → {format_american(current)} "
            f"· {status}"
        )
    if status == NEW:
        return "NEW since the previous scan"
    if status == REAPPEARED:
        return "REAPPEARED after disappearing from the prior scan"
    if status == BASELINE:
        return "Baseline observation for this owner session"
    if status == UNCHANGED:
        return "Still available at the same price as the prior scan"
    return status


def _history_triplet_line(record: dict | None) -> str:
    if not record:
        return ""
    opening = record.get("opening_price")
    previous = record.get("previous_price")
    current = record.get("current_price")
    return (
        f"Opening {format_american(opening)} · "
        f"Previous {format_american(previous)} · "
        f"Current {format_american(current)}"
    )


def _history_time_line(record: dict | None) -> str:
    if not record:
        return ""
    first_seen = record.get("first_seen")
    last_seen = record.get("last_seen")
    freshness = freshness_status(last_seen)
    return (
        f"First detected: {local_start_label(first_seen)} · "
        f"Last confirmed: {local_start_label(last_seen)} · "
        f"Freshness: {freshness}"
    )


def _movement_rows(
    rows: list[dict],
) -> list[dict[str, object]]:
    display: list[dict[str, object]] = []
    for row in rows:
        event = str(row.get("event") or "").strip() or (
            f"{row.get('away_team', '')} @ {row.get('home_team', '')}".strip(" @")
        )
        detail = " ".join(
            part
            for part in (
                str(row.get("market") or "").strip(),
                str(row.get("side") or "").strip(),
                str(row.get("threshold"))
                if row.get("threshold") is not None
                else "",
            )
            if part
        )
        display.append(
            {
                "Status": str(row.get("status") or ""),
                "Type": str(row.get("kind") or ""),
                "Book": str(row.get("book") or ""),
                "Event": event,
                "Market": detail,
                "Opening": format_american(row.get("opening_price")),
                "Previous": format_american(row.get("previous_price")),
                "Current": format_american(row.get("current_price")),
                "First detected": local_start_label(row.get("first_seen")),
                "Changed": local_start_label(row.get("changed_at")),
            }
        )
    return display


def _render_action(action) -> None:
    message = f"ACTION: {action.action} — {action.reason}"
    if action.action == BET:
        st.success(message)
    elif action.action == PASS:
        st.info(message)
    else:
        st.warning(message)


def _render_ev_card(row: dict, *, show_evidence: bool = True) -> None:
    selection = str(row.get("selection") or row.get("side") or "Bet").strip()
    display_market = str(row.get("display_market") or market_label(row)).strip()
    bet_name = f"{selection} {display_market}".strip()
    book = str(row.get("book") or "Sportsbook").strip()
    price = format_american(row.get("price"))
    fair_probability = row.get("fair_prob_pct")
    fair_odds = fair_american_from_probability(fair_probability)
    fair_price = format_american(fair_odds)
    ev = expected_ev_pct(row.get("price"), fair_probability)
    edge = probability_edge_points(row)
    tier = value_tier(ev)
    anchor = str(row.get("sharp_anchor") or "market").strip().title()
    implied = row.get("book_implied_pct")
    phase = event_phase_label(row.get("commence_time"))
    alternate_text = _alternate_text(row)
    history_record = row.get("_history") if isinstance(row.get("_history"), dict) else None
    action = ev_action(row)

    with st.container(border=True):
        title_col, tier_col = st.columns([4, 1])
        with title_col:
            st.markdown(f"#### {bet_name} · {book} {price}")
            st.caption(_event_context(row))
            if alternate_text:
                st.caption(f"Alternate: {alternate_text}")
        with tier_col:
            st.markdown(f"**{tier}**")

        c1, c2, c3 = st.columns(3)
        c1.metric("Current price", price)
        c2.metric("Fair line", fair_price)
        c3.metric("Estimated EV", f"{ev:+.1f}%" if ev is not None else "—")

        movement_line = _history_price_line(history_record)
        if movement_line:
            st.markdown(f"**WHY NOW:** {movement_line}")
        triplet_line = _history_triplet_line(history_record)
        if triplet_line:
            st.caption(triplet_line)
        time_line = _history_time_line(history_record)
        if time_line:
            st.caption(time_line)
        _render_action(action)

        if implied is not None and fair_probability is not None and edge is not None:
            st.markdown(
                f"**Why it surfaced:** {book} implies **{_pct(implied)}**, while the {anchor}-derived "
                f"fair estimate is **{_pct(fair_probability)}**. That is a **+{edge:.2f} percentage-point** "
                f"gap, with {price} available versus roughly {fair_price} fair."
            )
        else:
            st.markdown("**Why it surfaced:** the market feed identified this as a positive expected-value price at one of my books.")

        if phase == "PRESEASON":
            st.warning(
                "PRESEASON price signal. Rotations, inactive decisions, and late lineup news can move these markets quickly; "
                "this is not a regular-season confidence grade."
            )
        else:
            st.caption(
                "Price/value signal — not classified as a sportsbook error. Estimated EV assumes the feed's fair probability is accurate."
            )

        if show_evidence:
            with st.expander("Market evidence"):
                _evidence_table(
                    [
                        ("Game", game_name(row)),
                        ("Phase", phase or "Not labeled by current preview"),
                        ("Start", local_start_label(row.get("commence_time"))),
                        ("Bet", bet_name),
                        ("Sportsbook", book),
                        ("Current price", price),
                        ("Alternate prices", alternate_text or "None at another configured book"),
                        ("Book implied probability", _pct(implied)),
                        ("Fair probability", _pct(fair_probability)),
                        ("Fair line", fair_price),
                        ("Probability gap", f"+{edge:.3f} pts" if edge is not None else "—"),
                        ("Estimated EV", f"{ev:+.2f}%" if ev is not None else "—"),
                        ("Sharp/fair anchor", anchor),
                        ("Action", action.action),
                        ("Movement", _history_price_line(history_record) or "No prior scan comparison"),
                        ("Opening price", format_american(history_record.get("opening_price")) if history_record else "—"),
                        ("Previous price", format_american(history_record.get("previous_price")) if history_record else "—"),
                        ("Current tracked price", format_american(history_record.get("current_price")) if history_record else "—"),
                        ("First detected", local_start_label(history_record.get("first_seen")) if history_record else "—"),
                        ("Last confirmed", local_start_label(history_record.get("last_seen")) if history_record else "—"),
                        ("Freshness", freshness_status(history_record.get("last_seen")) if history_record else "—"),
                    ]
                )


def _render_glitch_card(alert: dict, *, show_evidence: bool = True) -> None:
    quote = alert.get("quote", {}) or {}
    severity = str(alert.get("severity") or "P2")
    book = str(quote.get("book") or "Sportsbook")
    price = format_american(quote.get("odds_american"))
    event = str(quote.get("event") or "Game")
    market = str(quote.get("market") or "market").replace("_", " ")
    side = str(quote.get("side") or "").strip()
    threshold = quote.get("threshold")
    consensus = alert.get("consensus_implied_prob")
    try:
        consensus_pct = float(consensus) * 100
    except (TypeError, ValueError):
        consensus_pct = None
    fair_odds = fair_american_from_probability(consensus_pct)
    payout_multiple = alert.get("profit_multiple_vs_peers")
    relative = alert.get("relative_prob_deviation")
    sign_mismatch = bool(alert.get("sign_mismatch"))
    history_record = alert.get("_history") if isinstance(alert.get("_history"), dict) else None
    peer_prices = alert.get("_peer_prices") if isinstance(alert.get("_peer_prices"), (list, tuple)) else ()
    peer_text = ", ".join(
        f"{row.get('book')} {format_american(row.get('price'))}"
        for row in peer_prices
        if isinstance(row, dict)
    )
    peer_gap = peer_implied_probability_gap_range(quote.get("odds_american"), peer_prices)
    action = glitch_action(alert)

    with st.container(border=True):
        st.markdown(f"#### {severity} GLITCH WATCH · {book} {price}")
        detail = " ".join(part for part in [market, side, str(threshold) if threshold is not None else ""] if part).strip()
        st.caption(f"{event} · {detail or 'same-market price anomaly'}")
        c1, c2, c3 = st.columns(3)
        c1.metric("Flagged price", price)
        c2.metric("Peer fair line", format_american(fair_odds))
        c3.metric("Peer payout multiple", f"{_number(payout_multiple)}×")

        movement_line = _history_price_line(history_record)
        if movement_line:
            st.markdown(f"**WHY NOW:** {movement_line}")
        if peer_text:
            st.caption(f"My other visible books: {peer_text}")
        if peer_gap is not None:
            low, high = peer_gap
            gap_text = (
                f"{low:.1f} pp"
                if abs(low - high) < 0.05
                else f"{low:.1f}–{high:.1f} pp"
            )
            st.markdown(
                f"**Market gap:** {book} is currently **{gap_text} lower implied probability** "
                "than my other visible books on this exact wager."
            )
        triplet_line = _history_triplet_line(history_record)
        if triplet_line:
            st.caption(triplet_line)
        time_line = _history_time_line(history_record)
        if time_line:
            st.caption(time_line)
        _render_action(action)

        if sign_mismatch:
            st.error(
                "Meaningful sign mismatch: this price crosses even money and is also "
                "at least 10 implied-probability points away from peer consensus."
            )
        else:
            st.warning("This price is materially different from the same market at peer books.")
        st.caption("Potential sportsbook pricing anomaly. Settlement/obvious-error void risk is not yet scored by this preview.")
        if show_evidence:
            with st.expander("Anomaly evidence"):
                _evidence_table(
                    [
                        ("Event", event),
                        ("Sportsbook", book),
                        ("Market", detail or market),
                        ("Flagged price", price),
                        ("Peer consensus probability", _pct(consensus_pct)),
                        ("Peer fair line", format_american(fair_odds)),
                        (
                            "Relative probability deviation",
                            f"{float(relative) * 100:.1f}%" if isinstance(relative, (int, float)) else "—",
                        ),
                        ("Profit multiple vs peers", f"{_number(payout_multiple)}×"),
                        ("Sign mismatch", "Yes" if sign_mismatch else "No"),
                        ("Action", action.action),
                        ("Movement", _history_price_line(history_record) or "No prior scan comparison"),
                        ("Opening price", format_american(history_record.get("opening_price")) if history_record else "—"),
                        ("Previous price", format_american(history_record.get("previous_price")) if history_record else "—"),
                        ("Current tracked price", format_american(history_record.get("current_price")) if history_record else "—"),
                        ("First detected", local_start_label(history_record.get("first_seen")) if history_record else "—"),
                        ("Last confirmed", local_start_label(history_record.get("last_seen")) if history_record else "—"),
                        ("Freshness", freshness_status(history_record.get("last_seen")) if history_record else "—"),
                        ("My peer-book prices", peer_text or "No exact matching peer quote at another configured book"),
                    ]
                )


def _render_middle_card(row: dict, *, show_evidence: bool = True) -> None:
    over = row.get("over", {}) or {}
    under = row.get("under", {}) or {}
    try:
        window = float(under.get("line")) - float(over.get("line"))
    except (TypeError, ValueError):
        window = None

    with st.container(border=True):
        st.markdown(f"#### MIDDLE · {game_name(row)}")
        if window is not None:
            st.caption(f"{window:g}-point middle window")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**OVER {over.get('line', '—')} · {over.get('book', '—')}**")
            st.write(format_american(over.get("price")))
        with c2:
            st.markdown(f"**UNDER {under.get('line', '—')} · {under.get('book', '—')}**")
            st.write(format_american(under.get("price")))
        st.caption("Both required legs are restricted to sportsbooks I actually use.")
        if show_evidence:
            with st.expander("Middle evidence"):
                _evidence_table(
                    [
                        ("Game", game_name(row)),
                        ("Over book", over.get("book")),
                        ("Over line", over.get("line")),
                        ("Over price", format_american(over.get("price"))),
                        ("Under book", under.get("book")),
                        ("Under line", under.get("line")),
                        ("Under price", format_american(under.get("price"))),
                        ("Middle window", f"{window:g} points" if window is not None else "—"),
                    ]
                )


def _render_generic_opportunity(row: dict, label: str) -> None:
    with st.container(border=True):
        st.markdown(f"#### {label.upper()} · {game_name(row)}")
        summary_bits: list[str] = []
        for key, label_text in (("profit_pct", "profit"), ("arb_pct", "arb"), ("edge_pct", "edge")):
            if row.get(key) is not None:
                summary_bits.append(f"{label_text} {_pct(row.get(key))}")
        if summary_bits:
            st.caption(" · ".join(summary_bits))
        with st.expander(f"{label} evidence"):
            rows = _flat_rows(row)
            if rows:
                st.table(rows)
            else:
                st.write("No additional structured evidence was returned by the feed.")


FEATURED_ARB_MIN_EDGE_PCT = 2.0


def _arb_edge_pct(row: dict) -> float | None:
    try:
        implied_sum = float(row.get("implied_sum"))
    except (TypeError, ValueError):
        implied_sum = None
    if implied_sum is not None:
        return (1.0 - implied_sum) * 100.0

    for key in ("profit_pct", "arb_pct", "edge_pct"):
        if row.get(key) is not None:
            try:
                return float(row.get(key))
            except (TypeError, ValueError):
                pass
    return None


def _render_arb_card(row: dict, *, show_evidence: bool = True) -> None:
    home = row.get("best_home", {}) or {}
    away = row.get("best_away", {}) or {}
    edge = _arb_edge_pct(row)
    phase = event_phase_label(row.get("commence_time"))

    with st.container(border=True):
        st.markdown(f"#### ARBITRAGE · {game_name(row)}")
        meta = []
        if phase:
            meta.append(phase)
        if row.get("commence_time"):
            meta.append(local_start_label(row.get("commence_time")))
        if edge is not None:
            meta.append(f"implied-sum edge {edge:.2f}%")
        if meta:
            st.caption(" · ".join(meta))

        st.markdown("**BET BOTH SIDES**")
        left, right = st.columns(2)
        with left:
            st.markdown(
                f"**{row.get('home_team') or 'Home'} · {home.get('book') or '—'}**"
            )
            st.write(format_american(home.get("price")))
        with right:
            st.markdown(
                f"**{row.get('away_team') or 'Away'} · {away.get('book') or '—'}**"
            )
            st.write(format_american(away.get("price")))

        try:
            home_decimal = american_to_decimal(int(float(home.get("price"))))
            away_decimal = american_to_decimal(int(float(away.get("price"))))
            implied_sum = (1.0 / home_decimal) + (1.0 / away_decimal)
            home_units = 100.0 / (implied_sum * home_decimal)
            away_units = 100.0 / (implied_sum * away_decimal)
            locked_roi = ((1.0 / implied_sum) - 1.0) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            implied_sum = None
            home_units = None
            away_units = None
            locked_roi = None

        if (
            home_units is not None
            and away_units is not None
            and locked_roi is not None
        ):
            st.caption(
                f"100-unit equal-payout example: {home_units:.1f}u home + "
                f"{away_units:.1f}u away · locked ROI ≈ {locked_roi:.2f}% "
                "if both displayed prices are still available."
            )

        if edge is not None and edge < FEATURED_ARB_MIN_EDGE_PCT:
            st.warning(
                "THIN ARB — positive on the displayed prices, but below PropWar's "
                f"{FEATURED_ARB_MIN_EDGE_PCT:.0f}% featured-opportunity threshold. "
                "Recheck both books before acting."
            )
        else:
            st.success(
                "ARB — both displayed prices imply a combined probability below 100%. "
                "Recheck both books immediately because either leg can move."
            )

        if show_evidence:
            with st.expander("Arbitrage evidence"):
                _evidence_table(
                    [
                        ("Game", game_name(row)),
                        ("Start", local_start_label(row.get("commence_time"))),
                        ("Home side", row.get("home_team")),
                        ("Home book", home.get("book")),
                        ("Home price", format_american(home.get("price"))),
                        ("Away side", row.get("away_team")),
                        ("Away book", away.get("book")),
                        ("Away price", format_american(away.get("price"))),
                        ("Implied-sum edge", f"{edge:.3f}%" if edge is not None else "—"),
                        (
                            "Equal-payout ROI",
                            f"{locked_roi:.3f}%"
                            if locked_roi is not None
                            else "—",
                        ),
                    ]
                )


def _render_top_board(alerts: list[dict], arbs: list[dict], middles: list[dict], evs: list[dict]) -> None:
    st.markdown("### Best opportunities now")
    st.caption(
        "Highest-priority actionable signals across my sportsbooks. Glitches and arbs outrank ordinary +EV prices; "
        "regular/postseason value ranks ahead of routine preseason value."
    )

    shown = 0
    for alert in alerts:
        if shown >= 3:
            break
        if glitch_action(alert).action == PASS:
            continue
        _render_glitch_card(alert, show_evidence=False)
        shown += 1

    for row in sorted(
        arbs,
        key=lambda value: _arb_edge_pct(value) or 0.0,
        reverse=True,
    ):
        if shown >= 3:
            break
        edge = _arb_edge_pct(row)
        if edge is None or edge < FEATURED_ARB_MIN_EDGE_PCT:
            continue
        _render_arb_card(row, show_evidence=False)
        shown += 1

    for row in middles:
        if shown >= 3:
            break
        _render_middle_card(row, show_evidence=False)
        shown += 1

    for row in evs:
        if shown >= 3:
            break
        if ev_action(row).action == PASS:
            continue
        _render_ev_card(row, show_evidence=False)
        shown += 1

    if shown == 0:
        st.info("Nothing actionable is showing in the current preview scan.")


_require_owner()

st.markdown("## Markets")
st.caption("Glitch Radar is the primary live market engine · my configured books · movement, price anomalies, line shopping, and current opportunities · cached 10 minutes")

with st.spinner("Checking current NFL market data..."):
    snapshot = _live_snapshot()

raw_alerts = snapshot.get("alerts", []) or []
raw_arbs = snapshot.get("arbs", []) or []
raw_middles = snapshot.get("middles", []) or []
raw_evs = snapshot.get("ev", []) or []
quotes = snapshot.get("quotes", []) or []
books = snapshot.get("books", []) or []

alerts = filter_actionable_alerts(raw_alerts)
arbs = filter_actionable_two_leg(raw_arbs)
middles = filter_actionable_two_leg(raw_middles)
evs = sorted(filter_actionable_ev(raw_evs), key=_ev_sort_key)
rank = {"P0": 0, "P1": 1, "P2": 2, "TEST": 3}
alerts = sorted(alerts, key=lambda row: rank.get(row.get("severity", "P2"), 9))
my_books_seen = user_books_seen(books)
comparison_books = comparison_books_seen(books)
missing_books = [book for book in USER_BOOKS if book not in my_books_seen]

observations = build_market_observations(alerts, evs)
history_backend = "In-memory fallback"
history_warning = ""
try:
    durable_store = _durable_market_history_store()
    if durable_store is not None:
        market_history = durable_store.update(
            observations,
            fetched_at=str(snapshot.get("fetched_at") or ""),
        )
        history_backend = "Private durable history"
    else:
        market_history = _market_history_store().update(
            observations,
            fetched_at=str(snapshot.get("fetched_at") or ""),
        )
except Exception as exc:
    history_warning = str(exc)
    market_history = _market_history_store().update(
        observations,
        fetched_at=str(snapshot.get("fetched_at") or ""),
    )

for alert in alerts:
    alert["_history"] = history_for_key(
        market_history,
        glitch_opportunity_key(alert),
    )
    alert["_peer_prices"] = list(
        peer_prices_for_alert(alert, quotes, user_books_only=True)
    )
for row in evs:
    row["_history"] = history_for_key(
        market_history,
        ev_opportunity_key(row),
    )

movement_summary = history_summary(market_history)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Glitch watches", len(alerts))
m2.metric("Arbs", len(arbs))
m3.metric("Middles", len(middles))
m4.metric("Value plays", len(evs))

status_col, refresh_col = st.columns([4, 1])
with status_col:
    st.caption(
        f"{len(quotes)} quotes scanned · {len(my_books_seen)}/{len(USER_BOOKS)} of my books visible · "
        f"last scan {local_start_label(snapshot.get('fetched_at'))} · demo requests left: {snapshot.get('demo_remaining_hour', '—')}"
    )
    if missing_books:
        st.caption(
            f"Not returned in this preview: {', '.join(missing_books)}. "
            "This does not remove them from my configured sportsbook list."
        )
with refresh_col:
    if st.button("Force fresh scan", type="primary", width="stretch"):
        _live_snapshot.clear()
        st.rerun()

errors = snapshot.get("errors", []) or []
if errors:
    with st.expander("Feed warnings"):
        for error in errors:
            st.warning(error)

st.markdown("### Since last scan")
scan_a, scan_b, scan_c, scan_d = st.columns(4)
scan_a.metric("New / returned", movement_summary["new"])
scan_b.metric("Improved", movement_summary["improved"])
scan_c.metric("Worsened", movement_summary["worsened"])
scan_d.metric("Disappeared", movement_summary["disappeared"])
st.caption(
    f"History backend: {history_backend} · unique 10-minute/fresh scans only · "
    f"{int(market_history.get('scan_count') or 0)} scans tracked."
)
if history_warning:
    st.warning(
        "Durable market history could not be updated, so this run is using in-memory fallback."
    )
    with st.expander("History persistence warning"):
        st.caption(history_warning)

recent_changes = list(recent_history_changes(market_history, limit=50))
current_scan = str(snapshot.get("fetched_at") or "")
scan_changes = [
    row
    for row in recent_changes
    if str(row.get("changed_at") or "") == current_scan
]
if scan_changes:
    st.markdown("#### What moved now")
    st.dataframe(
        _movement_rows(scan_changes),
        hide_index=True,
        width="stretch",
    )

if recent_changes:
    with st.expander("Recent movement history", expanded=False):
        st.dataframe(
            _movement_rows(recent_changes[:25]),
            hide_index=True,
            width="stretch",
        )

disappeared_rows = market_history.get("disappeared", []) or []
if disappeared_rows:
    with st.expander("What disappeared since the prior scan"):
        for row in disappeared_rows[:12]:
            kind = str(row.get("kind") or "Signal")
            book = str(row.get("book") or "Book")
            event = str(row.get("event") or "").strip() or (
                f"{row.get('away_team', '')} @ {row.get('home_team', '')}".strip(" @")
            )
            side = str(row.get("side") or "").strip()
            st.write(
                f"**{kind} · {book} {format_american(row.get('current_price'))}** — "
                f"{event} · {side or row.get('market', 'market')} · "
                f"first seen {local_start_label(row.get('first_seen'))}"
            )

_render_top_board(alerts, arbs, middles, evs)

st.divider()

glitch_tab, arb_tab, middle_tab, ev_tab, more_tab = st.tabs(
    ["Glitches", "Arbs", "Middles", "+EV Prices", "More"],
    key="markets_primary_tabs",
    on_change="rerun",
)
boost_tab = more_tab
source_tab = more_tab

if glitch_tab.open:
    with glitch_tab:
        st.markdown("### Potential sportsbook errors")
        st.caption("Same-market prices that materially disagree with peers at one of my sportsbooks.")
        if not alerts:
            st.success("No major same-market pricing anomaly is visible at one of my books in the current preview.")
        for alert in alerts:
            _render_glitch_card(alert)
    
if arb_tab.open:
    with arb_tab:
        st.markdown("### Guaranteed-price opportunities")
        st.caption("Only shown when every required leg is at a sportsbook I use.")
        if not arbs:
            st.info("No actionable arbitrage using only my sportsbooks is in the current preview.")
        for row in sorted(
            arbs,
            key=lambda value: _arb_edge_pct(value) or 0.0,
            reverse=True,
        ):
            _render_arb_card(row)
    
if middle_tab.open:
    with middle_tab:
        st.markdown("### Middle windows")
        st.caption("Different lines at my books that can create a range where both bets win.")
        if not middles:
            st.info("No middle using only my sportsbooks is in the current preview.")
        for row in middles:
            _render_middle_card(row)
    
if ev_tab.open:
    with ev_tab:
        st.markdown("### Positive expected-value prices")
        st.caption(
            "These are ordinary market prices that look better than the feed's sharp-derived fair line. "
            "They are not automatically sportsbook glitches."
        )
        if not evs:
            st.info("No +EV price at one of my sportsbooks is in the current preview.")
        for row in evs:
            _render_ev_card(row)
    
if boost_tab.open:
    with boost_tab:
        st.markdown("### Account-specific Boost Lab")
        st.caption("Use this for a boost shown inside one of my sportsbook accounts that the public feed cannot see.")
        sportsbook = st.selectbox("Sportsbook", USER_BOOKS, key="glitch_boost_book")
        c1, c2 = st.columns(2)
        original_odds = c1.number_input("Original American odds", value=300, step=5)
        fair_odds = c2.number_input("Consensus/fair American odds", value=300, step=5)
        c3, c4 = st.columns(2)
        boost_pct = c3.number_input("Profit boost %", value=100.0, step=5.0)
        stake = c4.number_input("Stake", value=20.0, min_value=0.0, step=1.0)
        if st.button("Evaluate boost", type="primary"):
            result = evaluate_profit_boost(
                int(original_odds), int(fair_odds), float(boost_pct) / 100, float(stake)
            )
            ev_pct = float(result["ev_pct"]) * 100
            with st.container(border=True):
                st.markdown(f"#### {value_tier(ev_pct)} · {sportsbook}")
                b1, b2, b3 = st.columns(3)
                b1.metric("Boosted odds", format_american(result["boosted_odds"]))
                b2.metric("Estimated EV", f"{ev_pct:+.1f}%")
                b3.metric("Expected value", f"${result['expected_value_dollars']:.2f}")
                st.write(
                    f"Original price **{format_american(original_odds)}** · fair line **{format_american(fair_odds)}** · "
                    f"profit boost **{boost_pct:.0f}%** · stake **${stake:.2f}**"
                )
                if ev_pct > 0:
                    st.success("The boost creates a positive estimated price edge versus the fair line you entered.")
                else:
                    st.warning("The boost does not overcome the fair-price gap you entered.")
                st.caption(
                    "The result is only as good as the fair line entered. Always benchmark a boost against the current market, "
                    "not its advertised pre-boost price."
                )
    
if source_tab.open:
    with source_tab:
        st.divider()
        st.markdown("### Sportsbook and feed coverage")
        c1, c2 = st.columns(2)
        with c1:
            with st.container(border=True):
                st.markdown("#### My actionable books")
                for book in USER_BOOKS:
                    status = "VISIBLE NOW" if book in my_books_seen else "NOT IN CURRENT PREVIEW"
                    st.write(f"**{book}** — {status}")
        with c2:
            with st.container(border=True):
                st.markdown("#### Comparison-only books")
                if comparison_books:
                    for book in comparison_books:
                        st.write(book)
                else:
                    st.write("None returned in this preview.")
                st.caption("These books can help establish fair value but are never presented as a place for me to bet.")
    
        _evidence_table(
            [
                ("Quotes scanned", len(quotes)),
                ("My books visible", f"{len(my_books_seen)}/{len(USER_BOOKS)}"),
                ("Last scan", local_start_label(snapshot.get("fetched_at"))),
                ("Demo requests left this hour", snapshot.get("demo_remaining_hour", "—")),
                ("Actionable books", ", ".join(USER_BOOKS)),
                ("Comparison books visible", ", ".join(comparison_books) if comparison_books else "None"),
            ]
        )
    
        with st.expander("Feed diagnostics"):
            diagnostics = _flat_rows(snapshot.get("command_center", {}), limit=40)
            if diagnostics:
                st.table(diagnostics)
            else:
                st.write("No command-center diagnostic fields were returned.")
            st.caption("Diagnostics are kept here for troubleshooting; the betting tabs above are the decision interface.")

        st.markdown("[Open deeper Market Research →](/deep-prop-radar)")
    