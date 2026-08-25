from datetime import datetime, timezone
import streamlit as st

from glitch_radar.live_no_key import build_no_key_snapshot
from glitch_radar.no_key_store import load_no_key_snapshot
from glitch_radar.promos import evaluate_profit_boost
from glitch_radar.math_utils import implied_probability

st.set_page_config(
    page_title="NFL Glitch Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

@st.cache_data(ttl=600, show_spinner=False)
def get_live_snapshot():
    data = build_no_key_snapshot()
    data["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return data

def opportunities(payload):
    if not isinstance(payload, dict):
        return []
    return payload.get("opportunities", []) or []

def load_best_available():
    try:
        live = get_live_snapshot()
        if live.get("quotes") or live.get("arbitrage") or live.get("middles") or live.get("ev"):
            return live, True
    except Exception as e:
        st.warning(f"Live fetch failed; using the most recent local snapshot if available. ({e})")
    return load_no_key_snapshot(), False

snap, is_live = load_best_available()
quotes = snap.get("quotes", []) or []
alerts = snap.get("local_alerts", []) or []
arbs = opportunities(snap.get("arbitrage", {}))
middles = opportunities(snap.get("middles", {}))
evs = opportunities(snap.get("ev", {}))

st.title("NFL Glitch Radar")
st.caption("No-key NFL radar · refreshes from public API data · $0 recurring cost")

status = "LIVE" if is_live else "CACHED"
fetched = snap.get("fetched_at") or snap.get("timestamp") or "—"
st.caption(f"{status} · data fetched {fetched}")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Alerts", len(alerts))
m2.metric("Arbs", len(arbs))
m3.metric("Middles", len(middles))
m4.metric("+EV", len(evs))

if st.button("Force fresh scan"):
    get_live_snapshot.clear()
    st.rerun()

errors = snap.get("errors", []) or []
if errors:
    with st.expander("Feed warnings"):
        for err in errors:
            st.warning(err)

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["🚨 Radar", "🔴 Arbs", "🟠 Middles", "🎯 +EV", "🎁 Boost"]
)

with tab1:
    if not alerts:
        st.success("No local anomaly alert currently meets the detector thresholds.")
    else:
        rank = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "TEST": 4}
        for a in sorted(alerts, key=lambda x: rank.get(x.get("severity", "P3"), 9)):
            sev = a.get("severity", "")
            typ = a.get("type", "").replace("_", " ").title()
            with st.expander(f"{sev} · {typ}", expanded=sev == "P0"):
                st.json(a)

    st.caption(
        "No-key odds preview is limited to the provider's public demo scope, so absence of an alert "
        "does not mean every NFL player prop at every book was checked."
    )

with tab2:
    if not arbs:
        st.info("No arbitrage opportunity returned by the current no-auth preview.")
    for a in arbs:
        st.error("Possible cross-book arbitrage")
        st.json(a)

with tab3:
    if not middles:
        st.info("No totals middle returned by the current no-auth preview.")
    for m in middles:
        over = m.get("over", {}) or {}
        under = m.get("under", {}) or {}
        st.warning(
            f"{m.get('away_team','')} @ {m.get('home_team','')} · "
            f"{over.get('book','')} O{over.get('line','')} {over.get('price','')} / "
            f"{under.get('book','')} U{under.get('line','')} {under.get('price','')}"
        )
        with st.expander("Details"):
            st.json(m)

with tab4:
    if not evs:
        st.info("No +EV opportunity returned by the current no-auth preview.")
    for e in evs:
        st.write(
            f"**{e.get('side','')}** · **{e.get('book','')} {e.get('price','')}** · "
            f"edge **{e.get('edge_pct','?')}%** · fair **{e.get('fair_prob_pct','?')}%**"
        )
        with st.expander("Details"):
            st.json(e)

with tab5:
    st.caption("Use this for a personalized profit boost that public feeds cannot see.")
    c1, c2 = st.columns(2)
    odds = c1.number_input("Original American odds", value=300, step=5)
    fair_odds = c2.number_input("Consensus/fair American odds", value=300, step=5)
    c3, c4 = st.columns(2)
    boost_pct = c3.number_input("Profit boost %", value=100.0, step=5.0) / 100
    stake = c4.number_input("Stake", value=20.0, min_value=0.0)
    if st.button("Evaluate boost"):
        fair_prob = implied_probability(int(fair_odds))
        r = evaluate_profit_boost(int(odds), fair_prob, boost_pct, stake)
        b1, b2, b3 = st.columns(3)
        b1.metric("Boosted odds", f"{r['boosted_odds']:+d}")
        b2.metric("Estimated EV", f"{r['ev_pct']*100:.1f}%")
        b3.metric("Expected value", f"${r['expected_profit_dollars']:.2f}")

with st.sidebar:
    st.header("About this mode")
    st.write(
        "This cloud-safe view does not depend on Windows Task Scheduler or persistent disk. "
        "It fetches fresh no-key data when opened and caches it for 10 minutes."
    )
    st.write(f"Quotes in preview: {len(quotes)}")
    st.write(f"Demo requests left this hour: {snap.get('demo_remaining_hour','—')}")
