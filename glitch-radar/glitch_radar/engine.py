from .detectors import (
    detect_price_outliers, detect_line_outliers, detect_arbitrage,
    detect_middles, detect_ladder_violations, detect_stale,
    detect_nested_candidates
)

class RadarEngine:
    def scan(self, quotes):
        alerts = []
        alerts += detect_price_outliers(quotes)
        alerts += detect_line_outliers(quotes)
        alerts += detect_arbitrage(quotes)
        alerts += detect_middles(quotes)
        alerts += detect_ladder_violations(quotes)
        alerts += detect_stale(quotes)
        alerts += detect_nested_candidates(quotes)
        rank = {"P0":0, "P1":1, "P2":2, "P3":3, "TEST":4}
        return sorted(alerts, key=lambda a: rank.get(a.get("severity","P3"), 9))
