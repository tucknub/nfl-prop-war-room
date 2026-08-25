from collections import defaultdict
from datetime import datetime
from .math_utils import implied_probability, american_to_decimal, median

def _group_exact(quotes):
    g = defaultdict(list)
    for q in quotes:
        g[q.identity()].append(q)
    return g

def detect_price_outliers(quotes, min_books=3, payout_ratio=1.75, prob_deviation=0.40):
    alerts = []
    for key, group in _group_exact(quotes).items():
        if len(group) < min_books:
            continue
        probs = [implied_probability(q.odds_american) for q in group]
        consensus = median(probs)
        for q in group:
            p = implied_probability(q.odds_american)
            rel_prob_dev = abs(p - consensus) / consensus if consensus else 0
            profits = [american_to_decimal(x.odds_american) - 1 for x in group if x is not q]
            peer_profit = median(profits) if profits else 0
            own_profit = american_to_decimal(q.odds_american) - 1
            ratio = own_profit / peer_profit if peer_profit > 0 else 1
            sign_mismatch = (q.odds_american > 0 and sum(x.odds_american < 0 for x in group) >= 2) or \
                            (q.odds_american < 0 and sum(x.odds_american > 0 for x in group) >= 2)
            if rel_prob_dev >= prob_deviation or ratio >= payout_ratio or sign_mismatch:
                severity = "P0" if ratio >= 3 or sign_mismatch else "P1"
                alerts.append({
                    "type": "price_outlier",
                    "severity": severity,
                    "book": q.book,
                    "quote": q,
                    "consensus_implied_prob": consensus,
                    "relative_prob_deviation": rel_prob_dev,
                    "profit_multiple_vs_peers": ratio,
                    "sign_mismatch": sign_mismatch,
                })
    return alerts

def detect_line_outliers(quotes, min_books=3, absolute_gap=None, relative_gap=0.20):
    g = defaultdict(list)
    for q in quotes:
        k = (q.event.lower(), q.market.lower(), q.participant.lower(), q.side.lower(), q.period.lower())
        if q.threshold is not None:
            g[k].append(q)
    alerts = []
    for key, group in g.items():
        if len(group) < min_books:
            continue
        med = median([q.threshold for q in group])
        for q in group:
            gap = abs(q.threshold - med)
            rel = gap / max(abs(med), 1)
            if (absolute_gap is not None and gap >= absolute_gap) or rel >= relative_gap:
                alerts.append({
                    "type": "line_outlier",
                    "severity": "P0" if rel >= 0.35 else "P1",
                    "book": q.book,
                    "quote": q,
                    "median_threshold": med,
                    "gap": gap,
                    "relative_gap": rel,
                })
    return alerts

def detect_arbitrage(quotes):
    buckets = defaultdict(lambda: defaultdict(list))
    for q in quotes:
        key = (q.event.lower(), q.market.lower(), q.participant.lower(), q.threshold, q.period.lower())
        buckets[key][q.side.lower()].append(q)

    pairs = [("over","under"), ("yes","no"), ("home","away"), ("team1","team2")]
    alerts = []
    for key, sides in buckets.items():
        for a, b in pairs:
            if a not in sides or b not in sides:
                continue
            best_a = max(sides[a], key=lambda q: american_to_decimal(q.odds_american))
            best_b = max(sides[b], key=lambda q: american_to_decimal(q.odds_american))
            idx = implied_probability(best_a.odds_american) + implied_probability(best_b.odds_american)
            if idx < 1:
                alerts.append({
                    "type": "arbitrage",
                    "severity": "P0" if idx <= 0.98 else "P1",
                    "a": best_a,
                    "b": best_b,
                    "arb_index": idx,
                    "guaranteed_roi": 1 / idx - 1,
                })
    return alerts

def detect_middles(quotes, min_window=1.0):
    g = defaultdict(list)
    for q in quotes:
        key = (q.event.lower(), q.market.lower(), q.participant.lower(), q.period.lower())
        g[key].append(q)
    alerts = []
    for key, group in g.items():
        overs = [q for q in group if q.side.lower() == "over" and q.threshold is not None]
        unders = [q for q in group if q.side.lower() == "under" and q.threshold is not None]
        for o in overs:
            for u in unders:
                width = u.threshold - o.threshold
                if width >= min_window and o.book != u.book:
                    alerts.append({
                        "type": "middle",
                        "severity": "P1" if width >= 3 else "P2",
                        "over": o,
                        "under": u,
                        "window": width,
                    })
    return alerts

def detect_ladder_violations(quotes):
    g = defaultdict(list)
    for q in quotes:
        if q.threshold is None:
            continue
        key = (q.book.lower(), q.event.lower(), q.market.lower(), q.participant.lower(), q.side.lower(), q.period.lower())
        g[key].append(q)

    alerts = []
    for key, group in g.items():
        side = key[4]
        ordered = sorted(group, key=lambda q: q.threshold)
        if side == "over":
            for easier, harder in zip(ordered, ordered[1:]):
                if american_to_decimal(harder.odds_american) < american_to_decimal(easier.odds_american):
                    alerts.append({
                        "type": "ladder_violation",
                        "severity": "P0",
                        "easier": easier,
                        "harder": harder,
                    })
        elif side == "under":
            ordered = list(reversed(ordered))
            for easier, harder in zip(ordered, ordered[1:]):
                if american_to_decimal(harder.odds_american) < american_to_decimal(easier.odds_american):
                    alerts.append({
                        "type": "ladder_violation",
                        "severity": "P0",
                        "easier": easier,
                        "harder": harder,
                    })
    return alerts

def detect_stale(quotes, min_move=0.15, min_peer_count=2):
    by_market = defaultdict(list)
    for q in quotes:
        if not q.timestamp:
            continue
        k = (q.event.lower(), q.market.lower(), q.participant.lower(), q.side.lower(), q.threshold, q.period.lower())
        by_market[k].append(q)

    alerts = []
    for key, group in by_market.items():
        times = sorted(set(q.timestamp for q in group))
        if len(times) < 2:
            continue
        t0, t1 = times[0], times[-1]
        old = {q.book: q for q in group if q.timestamp == t0}
        new = {q.book: q for q in group if q.timestamp == t1}
        common = set(old) & set(new)
        if len(common) < min_peer_count + 1:
            continue

        moves = {b: abs(implied_probability(new[b].odds_american) - implied_probability(old[b].odds_american)) for b in common}
        for b, mv in moves.items():
            others = [v for bb,v in moves.items() if bb != b]
            if len(others) < min_peer_count:
                continue
            other_med = median(others)
            if other_med >= min_move and mv <= other_med * 0.25:
                alerts.append({
                    "type": "stale_line",
                    "severity": "P1",
                    "book": b,
                    "old": old[b],
                    "new": new[b],
                    "book_move": mv,
                    "peer_median_move": other_med,
                })
    return alerts

def detect_nested_candidates(quotes):
    g = defaultdict(list)
    for q in quotes:
        if q.threshold is None:
            continue
        if q.side.lower() not in ("over", "yes"):
            continue
        key = (q.book.lower(), q.event.lower(), q.market.lower(), q.participant.lower(), q.period.lower())
        g[key].append(q)
    out = []
    for key, group in g.items():
        if len(group) >= 3:
            ordered = sorted(group, key=lambda q: q.threshold)
            out.append({
                "type": "structural_test",
                "severity": "TEST",
                "book": key[0],
                "quotes": ordered,
                "hardest": ordered[-1],
                "instruction": "Test nested thresholds together in the sportsbook builder; payout should not materially exceed the hardest leg alone."
            })
    return out
