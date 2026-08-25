from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from access_control import access_mode  # noqa: E402
from glitch_radar_live import build_snapshot, evaluate_profit_boost  # noqa: E402
from glitch_radar_books import (  # noqa: E402
    USER_BOOKS,
    comparison_books_seen,
    filter_actionable_alerts,
    filter_actionable_ev,
    filter_actionable_two_leg,
    user_books_seen,
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


def _detail_rows(rows: list[dict], empty_message: str, label: str) -> None:
    if not rows:
        st.info(empty_message)
        return
    for index, row in enumerate(rows, start=1):
        with st.expander(f"{label} #{index}", expanded=index == 1):
            st.json(row)


_require_owner()

st.markdown("## My Glitch Radar")
st.caption("No-key NFL market scanner · personalized to my sportsbooks · cached 10 minutes")

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
evs = filter_actionable_ev(raw_evs)
my_books_seen = user_books_seen(books)
comparison_books = comparison_books_seen(books)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Glitch alerts", len(alerts))
m2.metric("Arbs", len(arbs))
m3.metric("Middles", len(middles))
m4.metric("+EV", len(evs))

st.caption(
    f"Fetched {snapshot.get('fetched_at', '—')} · {len(quotes)} quotes · "
    f"my books currently seen: {', '.join(my_books_seen) if my_books_seen else 'none in preview'} · "
    f"demo requests left this hour: {snapshot.get('demo_remaining_hour', '—')}"
)

st.info(
    "Actionable books: FanDuel, DraftKings, Caesars, bet365, Hard Rock Bet. "
    "Other books may still be used as market references, but Glitch Radar will not tell me to place a bet there."
)

if st.button("Force fresh scan", type="primary"):
    _live_snapshot.clear()
    st.rerun()

errors = snapshot.get("errors", []) or []
if errors:
    with st.expander("Feed warnings"):
        for error in errors:
            st.warning(error)

radar_tab, arb_tab, middle_tab, ev_tab, boost_tab, source_tab = st.tabs(
    ["Radar", "Arbs", "Middles", "+EV", "Boost Lab", "Source"]
)

with radar_tab:
    if not alerts:
        st.success("No major same-market price outlier is visible at one of my books in the current preview.")
    else:
        rank = {"P0": 0, "P1": 1, "P2": 2, "TEST": 3}
        for alert in sorted(alerts, key=lambda row: rank.get(row.get("severity", "P2"), 9)):
            quote = alert.get("quote", {}) or {}
            severity = alert.get("severity", "")
            title = (
                f"{severity} · {quote.get('book', '')} · {quote.get('event', '')} · "
                f"{quote.get('market', '')} {quote.get('side', '')} "
                f"{quote.get('threshold') if quote.get('threshold') is not None else ''} · "
                f"{quote.get('odds_american', ''):+d}"
                if isinstance(quote.get("odds_american"), int)
                else f"{severity} · Price outlier"
            )
            if severity == "P0":
                st.error(title)
            else:
                st.warning(title)
            with st.expander("Why it flagged"):
                st.json(alert)
    st.caption(
        "The full visible market can contribute to the comparison baseline, including books I do not use. "
        "Only a mispriced side at one of my five sportsbooks is surfaced as an actionable alert."
    )

with arb_tab:
    _detail_rows(
        arbs,
        "No arbitrage opportunity using only two of my sportsbooks is in the current public preview.",
        "Arbitrage",
    )

with middle_tab:
    if not middles:
        st.info("No middle using only my sportsbooks is in the current public preview.")
    for index, row in enumerate(middles, start=1):
        over = row.get("over", {}) or {}
        under = row.get("under", {}) or {}
        st.warning(
            f"{row.get('away_team', '')} @ {row.get('home_team', '')} · "
            f"{over.get('book', '')} O{over.get('line', '')} {over.get('price', '')} / "
            f"{under.get('book', '')} U{under.get('line', '')} {under.get('price', '')}"
        )
        with st.expander(f"Middle #{index} details"):
            st.json(row)

with ev_tab:
    if not evs:
        st.info("No +EV opportunity at one of my sportsbooks is in the current public preview.")
    for index, row in enumerate(evs, start=1):
        st.write(
            f"**{row.get('side', '')}** · **{row.get('book', '')} {row.get('price', '')}** · "
            f"edge **{row.get('edge_pct', '?')}%** · fair **{row.get('fair_prob_pct', '?')}%**"
        )
        with st.expander(f"+EV #{index} details"):
            st.json(row)
    st.caption("The fair-value anchor can still be Pinnacle or another comparison source; the bet itself must be at one of my books.")

with boost_tab:
    st.caption("For account-specific sportsbook boosts that public market feeds cannot see.")
    sportsbook = st.selectbox("Sportsbook", USER_BOOKS, key="glitch_boost_book")
    c1, c2 = st.columns(2)
    original_odds = c1.number_input("Original American odds", value=300, step=5)
    fair_odds = c2.number_input("Consensus/fair American odds", value=300, step=5)
    c3, c4 = st.columns(2)
    boost_pct = c3.number_input("Profit boost %", value=100.0, step=5.0)
    stake = c4.number_input("Stake", value=20.0, min_value=0.0, step=1.0)
    if st.button("Evaluate boost"):
        result = evaluate_profit_boost(
            int(original_odds), int(fair_odds), float(boost_pct) / 100, float(stake)
        )
        st.caption(f"Evaluating {sportsbook}")
        b1, b2, b3 = st.columns(3)
        b1.metric("Boosted odds", f"{result['boosted_odds']:+d}")
        b2.metric("Estimated EV", f"{result['ev_pct'] * 100:.1f}%")
        b3.metric("Expected value", f"${result['expected_value_dollars']:.2f}")

with source_tab:
    st.write("My actionable books:")
    st.write(", ".join(USER_BOOKS))
    st.write("My books currently visible in this preview:")
    st.write(", ".join(my_books_seen) if my_books_seen else "None returned in this preview")
    st.write("Comparison-only books currently visible in this preview:")
    st.write(", ".join(comparison_books) if comparison_books else "None returned")
    with st.expander("Command-center snapshot"):
        st.json(snapshot.get("command_center", {}))
    st.caption(
        "Comparison-only books can help establish fair value or expose an outlier, but they are never presented as a place for me to bet. "
        "This page uses official no-auth public API surfaces and does not require a separate PropWar API key."
    )
