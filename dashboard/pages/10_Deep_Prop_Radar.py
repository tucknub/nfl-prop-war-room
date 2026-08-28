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
from glitch_radar_coverage import actionable_coverage_summary  # noqa: E402
from glitch_radar_line_shop import build_line_shop_watches  # noqa: E402
from glitch_radar_near_miss import build_near_miss_anomalies  # noqa: E402
from glitch_radar_present import event_phase_label, format_american, local_start_label  # noqa: E402
from glitch_radar_props_feed import PROP_CREDITS_PER_SCAN  # noqa: E402
from glitch_radar_props_cache import shared_prop_snapshot  # noqa: E402
from glitch_radar_stale import coverage_quality, enrich_stale_alerts  # noqa: E402

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
    line = float(row.get("line") or 0)
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


def _render_near_miss(row: dict) -> None:
    side = str(row.get("side") or "over").upper()
    line = float(row.get("line") or 0)
    price = format_american(row.get("price"))
    proximity = float(row.get("glitch_threshold_proximity_pct") or 0)
    with st.container(border=True):
        st.markdown(f"#### WATCH · {row.get('player', 'Player')} · {_market(row)} {line:g} {side} · {row.get('book')} {price}")
        st.caption(_context(row))
        c1, c2, c3 = st.columns(3)
        c1.metric("Book price", price)
        c2.metric("Probability deviation", f"{float(row.get('relative_prob_deviation_pct') or 0):.1f}%")
        c3.metric("Glitch-threshold proximity", f"{proximity:.0f}%")
        st.write(
            f"Book implied probability: **{float(row.get('book_implied_prob_pct') or 0):.2f}%** · "
            f"same-line peer median: **{float(row.get('peer_median_implied_prob_pct') or 0):.2f}%** · "
            f"payout vs peer median: **{float(row.get('payout_multiple_vs_peers') or 0):.2f}×**"
        )
        peers = ", ".join(row.get("peer_books", []) or [])
        if peers:
            st.caption(f"Comparable price peers: {peers}")
        st.caption("Near-miss diagnostic only. It is below the strict sportsbook-error threshold and is not classified as a glitch or a recommendation.")


def _render_line_shop(row: dict) -> None:
    side = str(row.get("side") or "over").upper()
    book_line = float(row.get("book_line") or 0)
    peer_line = float(row.get("peer_line") or 0)
    gap = float(row.get("line_advantage") or 0)
    price_cost = float(row.get("price_cost_points") or 0)
    with st.container(border=True):
        st.markdown(
            f"#### LINE SHOP · {row.get('player', 'Player')} · {_market(row)} · "
            f"{row.get('book')} {side} {book_line:g} {format_american(row.get('book_price'))}"
        )
        st.caption(_context(row))
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**EASIER {side} · {row.get('book')}**")
            st.write(f"{book_line:g} · {format_american(row.get('book_price'))}")
        with c2:
            st.markdown(f"**COMPARE · {row.get('peer_book')}**")
            st.write(f"{peer_line:g} · {format_american(row.get('peer_price'))}")
        p1, p2 = st.columns(2)
        p1.metric("Threshold advantage", f"{gap:g}")
        p2.metric("Price cost", f"{price_cost:+.2f} prob pts")
        if price_cost <= 0:
            st.success("Easier threshold is also no more expensive by implied probability than this peer price.")
        else:
            st.info(f"Easier threshold costs only {price_cost:.2f} implied-probability points versus this comparison price.")
        st.caption("Line-shopping signal, not an EV estimate. Verify the exact market, period and settlement rules in both books before betting.")


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
        st.error(f"Harder threshold is priced {float(row.get('probability_inversion_points') or 0):.2f} probability points MORE likely than the easier threshold.")
        st.caption("Structural ladder anomaly — exactly the kind of ordering violation Glitch Radar is designed to catch.")


def _comparison_text(label: str, comparison: dict | None) -> tuple[str, str] | None:
    if not comparison:
        return None
    stale = format_american(comparison.get("stale_price"))
    peer = format_american(comparison.get("peer_price"))
    peer_book = comparison.get("peer_book") or "fresh peer"
    gap = float(comparison.get("implied_probability_gap_points") or 0)
    status = comparison.get("status")
    if status == "stale_better":
        return "success", f"{label}: **stale book is better** — {stale} vs {peer_book} {peer} ({gap:.2f} implied-probability points cheaper)."
    if status == "peer_better":
        return "caption", f"{label}: fresh market is better — stale {stale} vs {peer_book} {peer} ({gap:.2f} implied-probability points)."
    return "caption", f"{label}: stale and best fresh comparable price are both {stale}."


def _render_stale(row: dict) -> None:
    age_minutes = float(row.get("age_seconds") or 0) / 60
    peer_age = float(row.get("freshest_peer_age_seconds") or 0) / 60
    freshest_book = row.get("freshest_peer_book") or "Fresh peer"
    with st.container(border=True):
        st.markdown(f"#### STALE WATCH · {row.get('player', 'Player')} · {_market(row)} {row.get('line')} · {row.get('book')}")
        st.caption(_context(row))
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{row.get('book')} · {age_minutes:.1f}m old**")
            st.write(f"Over {format_american(row.get('over_price'))} · Under {format_american(row.get('under_price'))}")
        with c2:
            st.markdown(f"**{freshest_book} · {peer_age:.1f}m old**")
            st.write(f"Over {format_american(row.get('freshest_peer_over_price'))} · Under {format_american(row.get('freshest_peer_under_price'))}")
        for label, comparison in (("OVER", row.get("over_comparison")), ("UNDER", row.get("under_comparison"))):
            rendered = _comparison_text(label, comparison)
            if not rendered:
                continue
            kind, text = rendered
            st.success(text) if kind == "success" else st.caption(text)
        peers = ", ".join(row.get("fresh_peer_books", []) or [])
        if peers:
            st.caption(f"Fresh comparable sportsbook/exchange peers: {peers}")
        dfs_peers = ", ".join(row.get("dfs_fresh_peer_books", []) or [])
        if dfs_peers:
            st.caption(f"Fresh DFS movement context only: {dfs_peers}")
        st.caption("Stale means verify immediately, not bet automatically. DFS midpoint pricing is excluded from the actionable price comparison.")


_require_owner()

st.markdown("## Market Research")
st.caption("Advanced supporting diagnostics behind Markets · player props, line gaps, alternate ladders, stale prices, and near misses · 3-hour cache")

key = _api_key()
if not key:
    st.info("The deep-prop engine is built and ready, but the full player-prop feed needs a free ParlayAPI key.")
    st.markdown("ParlayAPI's permanent free plan provides **1,000 credits/month with no credit card**. One full NFL props scan costs **3 credits** and returns all books/markets in one call.")
    st.link_button("Get free ParlayAPI key", "https://parlay-api.com/signup")
    st.markdown("#### One-time Streamlit setup")
    st.write("In the PropWar app settings, open **Secrets** and add:")
    st.code('PARLAY_API_KEY = "pak_live_..."', language="toml")
    st.caption("Do not paste the key into chat or commit it to GitHub. Once saved, reopen this page and Deep Prop Radar activates automatically.")
    st.stop()

try:
    with st.spinner("Scanning the full current NFL player-prop board..."):
        deep = shared_prop_snapshot(key)
except Exception as exc:
    st.error(f"Deep prop scan failed: {exc}")
    st.caption("The 10-minute no-key Glitch Radar remains available even if the deep feed is unavailable.")
    st.stop()

coverage = deep.get("coverage", {}) or {}
rows = deep.get("rows", []) or []
quality = coverage_quality(rows)
coverage_truth = actionable_coverage_summary(rows)
price_outliers = [row for row in deep.get("price_outliers", []) or [] if row.get("actionable")]
near_misses = build_near_miss_anomalies(rows)
line_shop = build_line_shop_watches(rows)
line_gaps = deep.get("line_gaps", []) or []
ladder_violations = deep.get("ladder_violations", []) or []
stale_props = enrich_stale_alerts(deep.get("stale_props", []) or [], rows)

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Prop glitches", len(price_outliers))
m2.metric("Line-shop watches", len(line_shop))
m3.metric("Line gaps", len(line_gaps))
m4.metric("Ladder errors", len(ladder_violations))
m5.metric("Stale price watches", len(stale_props))

st.caption(
    f"{coverage.get('rows', 0):,} prop rows · {quality.get('cross_book_players', 0):,} cross-book player identities · "
    f"{len(coverage.get('markets', []) or []):,} market families · {len(near_misses):,} same-line diagnostics · "
    f"{len(line_shop):,} line-shop watches · refreshed {local_start_label(deep.get('fetched_at'))} · "
    f"{PROP_CREDITS_PER_SCAN} free credits per deep scan"
)

if coverage_truth.get("coverage_limited"):
    visible = ", ".join(coverage_truth.get("visible_user_books", []) or []) or "none"
    missing = ", ".join(coverage_truth.get("missing_user_books", []) or []) or "none"
    dominant_book = coverage_truth.get("dominant_user_book") or "No book"
    dominant_share = float(coverage_truth.get("dominant_user_book_share") or 0) * 100
    st.warning(
        f"COVERAGE LIMITED — only {int(coverage_truth.get('visible_user_book_count') or 0)}/5 configured books returned prop rows. "
        "Zero signal counts below mean no signal was found in the returned data; they are not evidence that all five sportsbooks are aligned."
    )
    st.caption(
        f"Visible: {visible}. Missing: {missing}. {dominant_book} supplies {dominant_share:.1f}% of the returned rows from my configured books."
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
    if coverage_truth.get("coverage_limited"):
        st.warning("No major signal was classified in the returned rows, but actionable cross-book coverage is too limited to treat this scan as an all-clear across my five sportsbooks.")
    else:
        st.success("No major prop-price, ladder, or material line-gap anomaly is visible at one of my books in this deep scan.")

if line_shop:
    st.markdown("### Best line-shopping edges")
    st.caption("Easier thresholds at roughly comparable juice. These are line-shopping opportunities, not sportsbook-error alerts.")
    for row in line_shop[:5]:
        _render_line_shop(row)
elif near_misses:
    st.markdown("### Closest same-line pricing discrepancies")
    for row in near_misses[:5]:
        _render_near_miss(row)

st.divider()
price_tab, shop_tab, watch_tab, gap_tab, ladder_tab, stale_tab, coverage_tab = st.tabs(
    ["Prop Glitches", "Line Shopping", "Near Misses", "Line Gaps", "Ladder Errors", "Stale Lines", "Coverage"]
)

with price_tab:
    st.markdown("### Exact same player / market / line price anomalies")
    st.caption("Peer books can establish context, but only anomalies at FanDuel, DraftKings, Caesars, bet365 or Hard Rock Bet are actionable here.")
    if not price_outliers:
        st.info("No actionable exact-line prop price outlier was found in the returned coverage.")
    for row in price_outliers:
        _render_price_glitch(row)

with shop_tab:
    st.markdown("### Cross-book line shopping")
    st.caption("Same event/player/market, different thresholds. An easier OVER line or higher UNDER line is shown only when its price is within 3 implied-probability points of the comparison price. DFS pick'em pricing is excluded.")
    if not line_shop:
        st.info("No easier-threshold line-shopping opportunity was found in the returned coverage.")
    for row in line_shop:
        _render_line_shop(row)

with watch_tab:
    st.markdown("### Near-miss same-line anomalies")
    st.caption("Largest exact event/player/market/line price differences below the true glitch threshold. DFS pick'em midpoint pricing is excluded from these comparisons.")
    if not near_misses:
        st.info("No non-identical exact same-line sportsbook price comparison is available in the returned coverage.")
    for row in near_misses:
        _render_near_miss(row)

with gap_tab:
    st.markdown("### Cross-book prop line discrepancies")
    st.caption("Materially different thresholds between sportsbooks I use. These are middle/line-shopping candidates, not automatic arbs.")
    if not line_gaps:
        st.info("No material line gap was found in the returned coverage.")
    for row in line_gaps:
        _render_line_gap(row)

with ladder_tab:
    st.markdown("### Impossible / inverted alternate ladders")
    st.caption("A harder OVER threshold should never be priced materially more likely than an easier OVER threshold at the same book.")
    if not ladder_violations:
        st.info("No ladder monotonicity violation is visible in the returned coverage.")
    for row in ladder_violations:
        _render_ladder(row)

with stale_tab:
    st.markdown("### Stale-line price watches")
    st.caption("One of my books is at least 10 minutes old while an exact same-line sportsbook/exchange peer is 3 minutes old or fresher. DFS-only freshness is context, not an actionable price comparison.")
    if not stale_props:
        st.info("No user-book prop in the returned coverage has both a stale price and a fresh comparable sportsbook/exchange price peer.")
    for row in stale_props:
        _render_stale(row)

with coverage_tab:
    st.markdown("### My sportsbook prop coverage")
    c1, c2, c3 = st.columns(3)
    c1.metric("Configured books visible", f"{int(coverage_truth.get('visible_user_book_count') or 0)}/5")
    c2.metric("My-book rows", f"{int(coverage_truth.get('user_book_total_rows') or 0):,}")
    c3.metric("Dominant book share", f"{float(coverage_truth.get('dominant_user_book_share') or 0) * 100:.1f}%")

    counts = coverage_truth.get("user_counts", {}) or {}
    for book in USER_BOOKS:
        count = int(counts.get(book, 0) or 0)
        status = f"{count:,} rows" if count else "not visible in this scan"
        st.write(f"**{book}** — {status}")

    st.divider()
    st.markdown("#### All feed sources in this scan")
    st.caption("Raw normalized row counts show exactly which sources make up the deep snapshot. A configured book missing here is absent from the returned feed, not hidden by the dashboard.")
    source_counts = coverage_truth.get("source_counts", {}) or {}
    if source_counts:
        for book, count in source_counts.items():
            tag = " · MY BOOK" if book in USER_BOOKS else ""
            st.write(f"**{book}** — {int(count):,} rows{tag}")
    else:
        st.write("No source rows returned.")

    st.divider()
    st.markdown("#### Player identity audit")
    q1, q2, q3 = st.columns(3)
    q1.metric("Cross-book players", f"{quality.get('cross_book_players', 0):,}")
    q2.metric("Cross-book player-games", f"{quality.get('cross_book_player_events', 0):,}")
    q3.metric("Raw player labels", f"{quality.get('raw_player_labels', 0):,}")
    st.caption("Cross-book player identities are the useful headline for comparison work. Raw player labels remain a feed-quality diagnostic.")

    st.divider()
    st.markdown("#### Market families detected")
    markets = coverage.get("markets", []) or []
    st.write(", ".join(str(market).replace("_", " ") for market in markets) if markets else "None returned.")
    st.caption("Reference books may establish comparison context, but only the configured five sportsbooks are treated as actionable books.")
