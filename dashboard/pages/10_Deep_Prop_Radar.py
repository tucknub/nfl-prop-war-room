from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

DASHBOARD_DIR = Path(__file__).resolve().parents[1]
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

from access_control import access_mode  # noqa: E402
from glitch_radar_books import USER_BOOKS  # noqa: E402
from glitch_radar_present import event_phase_label, format_american, local_start_label  # noqa: E402
from glitch_radar_props import (  # noqa: E402
    PROP_CREDITS_PER_SCAN,
    analyze_props,
    fetch_full_props,
)

DEEP_CACHE_SECONDS = 10_800  # 3 hours; protects the permanent 1,000-credit free allowance.


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
        st.error("Deep Prop Radar is an owner-only PropWar tool.")
        st.stop()


def _api_key() -> str:
    try:
        return str(st.secrets.get("PARLAY_API_KEY", "") or "").strip()
    except Exception:
        return ""


@st.cache_data(ttl=DEEP_CACHE_SECONDS, show_spinner=False)
def _deep_snapshot(_key: str) -> dict:
    rows = fetch_full_props(_key)
    result = analyze_props(rows)
    result["rows"] = rows
    result["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return result


def _game(row: dict) -> str:
    away = str(row.get("away_team") or "").strip()
    home = str(row.get("home_team") or "").strip()
    return f"{away} @ {home}" if away and home else away or home or "NFL game"


def _market(row: dict) -> str:
    label = str(row.get("market_label") or "").strip()
    if label:
        return label
    return str(row.get("market") or "prop").replace("_", " ").title()


def _context(row: dict) -> str:
    parts = [_game(row)]
    phase = event_phase_label(row.get("commence_time"))
    if phase:
        parts.append(phase)
    if row.get("commence_time"):
        parts.append(local_start_label(row.get("commence_time")))
    return " · ".join(parts)


def _render_price_glitch(row: dict) -> None:
    side = str(row.get("side") or "over").upper()
    line = row.get("line")
    price = format_american(row.get("price"))
    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"#### {row.get('player', 'Player')} · {_market(row)} {line:g} {side} · {row.get('book')} {price}")
            st.caption(_context(row))
        with c2:
            st.markdown(f"**{row.get('severity', 'P1')} GLITCH**")
        p1, p2 = st.columns(2)
        p1.metric("Flagged price", price)
        p2.metric("Peer payout multiple", f"{float(row.get('profit_multiple_vs_peers') or 0):.2f}×")
        if row.get("sign_mismatch"):
            st.error("Opposite side of zero from multiple same-market peers — possible sign/price inversion.")
        else:
            deviation = float(row.get("relative_prob_deviation") or 0) * 100
            st.warning(f"Same player, market and line differ materially from peers ({deviation:.1f}% relative probability deviation).")
        st.caption("Candidate pricing error, not a guaranteed payout. Obvious-error/void risk still needs rule review before betting.")


def _render_line_gap(row: dict) -> None:
    with st.container(border=True):
        st.markdown(f"#### {row.get('player', 'Player')} · {_market(row)} · {float(row.get('line_gap') or 0):g}-point line gap")
        st.caption(_context(row))
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**LOW LINE · {row.get('low_book')} {float(row.get('low_line')):g}**")
            st.caption(f"Over {format_american(row.get('low_over_price'))} · Under {format_american(row.get('low_under_price'))}")
        with c2:
            st.markdown(f"**HIGH LINE · {row.get('high_book')} {float(row.get('high_line')):g}**")
            st.caption(f"Over {format_american(row.get('high_over_price'))} · Under {format_american(row.get('high_under_price'))}")
        st.caption("Line-discrepancy candidate. Whether it is a playable middle depends on the exact over/under prices and settlement rules.")


def _render_ladder(row: dict) -> None:
    with st.container(border=True):
        st.markdown(f"#### {row.get('player', 'Player')} · {_market(row)} · {row.get('book')}")
        st.caption(_context(row))
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Easier OVER {float(row.get('easier_line')):g}**")
            st.write(format_american(row.get("easier_over_price")))
        with c2:
            st.markdown(f"**Harder OVER {float(row.get('harder_line')):g}**")
            st.write(format_american(row.get("harder_over_price")))
        st.error(
            f"Harder threshold is priced {float(row.get('probability_inversion_points') or 0):.2f} probability points MORE likely than the easier threshold."
        )
        st.caption("Structural ladder anomaly — exactly the kind of ordering violation Glitch Radar is designed to catch.")


def _render_stale(row: dict) -> None:
    age_minutes = float(row.get("age_seconds") or 0) / 60
    peer_age = float(row.get("freshest_peer_age_seconds") or 0) / 60
    with st.container(border=True):
        st.markdown(f"#### STALE WATCH · {row.get('player', 'Player')} · {_market(row)} {row.get('line')} · {row.get('book')}")
        st.caption(_context(row))
        st.write(
            f"This price is about **{age_minutes:.1f} minutes old**, while a same-market peer is about **{peer_age:.1f} minutes old**."
        )
        peers = ", ".join(row.get("fresh_peer_books", []) or [])
        if peers:
            st.caption(f"Fresh peers: {peers}")
        st.caption("Stale does not automatically mean mispriced; it means this book deserves immediate manual verification.")


_require_owner()

st.markdown("## My Deep Prop Radar")
st.caption("NFL player-prop glitch scanner · TDs, yardage, receptions and alternate ladders · 3-hour cache")

key = _api_key()
if not key:
    st.info("The deep-prop engine is built and ready, but the full player-prop feed needs a free ParlayAPI key.")
    st.markdown(
        "ParlayAPI's permanent free plan provides **1,000 credits/month with no credit card**. "
        "One full NFL props scan costs **3 credits** and returns all books/markets in one call."
    )
    st.link_button("Get free ParlayAPI key", "https://parlay-api.com/signup")
    st.markdown("#### One-time Streamlit setup")
    st.write("In the PropWar app settings, open **Secrets** and add:")
    st.code('PARLAY_API_KEY = "pak_live_..."', language="toml")
    st.caption("Do not paste the key into chat or commit it to GitHub. Once saved, reopen this page and Deep Prop Radar activates automatically.")
    st.stop()

try:
    with st.spinner("Scanning the full current NFL player-prop board..."):
        deep = _deep_snapshot(key)
except Exception as exc:
    st.error(f"Deep prop scan failed: {exc}")
    st.caption("The 10-minute no-key Glitch Radar remains available even if the deep feed is unavailable.")
    st.stop()

coverage = deep.get("coverage", {}) or {}
price_outliers = [row for row in deep.get("price_outliers", []) or [] if row.get("actionable")]
line_gaps = deep.get("line_gaps", []) or []
ladder_violations = deep.get("ladder_violations", []) or []
stale_props = deep.get("stale_props", []) or []

m1, m2, m3, m4 = st.columns(4)
m1.metric("Prop glitches", len(price_outliers))
m2.metric("Line gaps", len(line_gaps))
m3.metric("Ladder errors", len(ladder_violations))
m4.metric("Stale watches", len(stale_props))

st.caption(
    f"{coverage.get('rows', 0):,} prop rows · {coverage.get('players', 0):,} players · "
    f"{len(coverage.get('markets', []) or []):,} market families · refreshed {local_start_label(deep.get('fetched_at'))} · "
    f"{PROP_CREDITS_PER_SCAN} free credits per deep scan"
)

if st.button("Force new deep scan (uses 3 credits)", type="primary"):
    _deep_snapshot.clear()
    st.rerun()

st.markdown("### Highest-priority deep signals")
shown = 0
for row in price_outliers:
    if shown >= 5:
        break
    _render_price_glitch(row)
    shown += 1
for row in ladder_violations:
    if shown >= 5:
        break
    _render_ladder(row)
    shown += 1
for row in line_gaps:
    if shown >= 5:
        break
    _render_line_gap(row)
    shown += 1
if shown == 0:
    st.success("No major prop-price, ladder, or material line-gap anomaly is visible at one of my books in this deep scan.")

st.divider()
price_tab, gap_tab, ladder_tab, stale_tab, coverage_tab = st.tabs(
    ["Prop Glitches", "Line Gaps", "Ladder Errors", "Stale Lines", "Coverage"]
)

with price_tab:
    st.markdown("### Exact same player / market / line price anomalies")
    st.caption("Peer books can establish context, but only anomalies at FanDuel, DraftKings, Caesars, bet365 or Hard Rock Bet are actionable here.")
    if not price_outliers:
        st.info("No actionable exact-line prop price outlier crossed the current threshold.")
    for row in price_outliers:
        _render_price_glitch(row)

with gap_tab:
    st.markdown("### Cross-book prop line discrepancies")
    st.caption("Materially different thresholds between sportsbooks I use. These are middle/line-shopping candidates, not automatic arbs.")
    if not line_gaps:
        st.info("No material line gap crossed the current market-specific thresholds.")
    for row in line_gaps:
        _render_line_gap(row)

with ladder_tab:
    st.markdown("### Impossible / inverted alternate ladders")
    st.caption("A harder OVER threshold should never be priced materially more likely than an easier OVER threshold at the same book.")
    if not ladder_violations:
        st.info("No ladder monotonicity violation is visible in the current deep scan.")
    for row in ladder_violations:
        _render_ladder(row)

with stale_tab:
    st.markdown("### Stale-line watches")
    st.caption("One of my books is at least 10 minutes old while a same-line peer is 3 minutes old or fresher.")
    if not stale_props:
        st.info("No user-book prop currently meets the stale-vs-fresh-peer trigger.")
    for row in stale_props:
        _render_stale(row)

with coverage_tab:
    st.markdown("### My sportsbook prop coverage")
    counts = coverage.get("user_book_rows", {}) or {}
    for book in USER_BOOKS:
        count = int(counts.get(book, 0) or 0)
        status = f"{count:,} rows" if count else "not visible in this scan"
        st.write(f"**{book}** — {status}")
    st.divider()
    st.markdown("#### Market families detected")
    markets = coverage.get("markets", []) or []
    st.write(", ".join(str(market).replace("_", " ") for market in markets) if markets else "None returned.")
    st.caption(
        "The full feed can include reference books for anomaly context. They are never treated as sportsbooks I can bet at. "
        "The free tier does not include Pinnacle prop lines; cross-book consensus still works from the other sources."
    )
