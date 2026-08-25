import re
from dataclasses import replace
from .models import Quote

STAT_ALIASES = {
    "passing yards": "passing_yards",
    "pass yards": "passing_yards",
    "passing_yards": "passing_yards",
    "rushing yards": "rushing_yards",
    "rush yards": "rushing_yards",
    "rushing_yards": "rushing_yards",
    "receiving yards": "receiving_yards",
    "rec yards": "receiving_yards",
    "receiving_yards": "receiving_yards",
    "receptions": "receptions",
    "passing touchdowns": "passing_touchdowns",
    "passing tds": "passing_touchdowns",
    "pass tds": "passing_touchdowns",
    "passing_touchdowns": "passing_touchdowns",
    "touchdowns": "touchdowns",
    "tds": "touchdowns",
    "anytime td": "touchdowns",
    "anytime touchdown": "touchdowns",
    "interceptions": "interceptions",
    "completions": "completions",
    "attempts": "attempts",
    "passing attempts": "passing_attempts",
    "rushing attempts": "rushing_attempts",
    "longest reception": "longest_reception",
    "longest rush": "longest_rush",
}

PERIOD_ALIASES = {
    "game": "game",
    "full game": "game",
    "full_game": "game",
    "1h": "1h",
    "first half": "1h",
    "1st half": "1h",
    "2h": "2h",
    "second half": "2h",
    "1q": "1q",
    "first quarter": "1q",
    "1st quarter": "1q",
    "2q": "2q",
    "3q": "3q",
    "4q": "4q",
}

def _clean(s):
    return re.sub(r"\s+", " ", (s or "").strip().lower())

def canonical_stat(market: str) -> str:
    m = _clean(market).replace("-", " ").replace("_", " ")
    return STAT_ALIASES.get(m, m.replace(" ", "_"))

def canonical_period(period: str) -> str:
    return PERIOD_ALIASES.get(_clean(period), _clean(period) or "game")

def milestone_to_ou_threshold(label: str):
    s = _clean(label)
    patterns = [
        (r"^(\d+)\+\s+receiving yards$", "receiving_yards"),
        (r"^(\d+)\+\s+rushing yards$", "rushing_yards"),
        (r"^(\d+)\+\s+passing yards$", "passing_yards"),
        (r"^(\d+)\+\s+receptions$", "receptions"),
        (r"^(\d+)\+\s+passing touchdowns?$", "passing_touchdowns"),
        (r"^(\d+)\+\s+(?:touchdowns?|tds?)$", "touchdowns"),
        (r"^(\d+)\+\s+interceptions?$", "interceptions"),
        (r"^(\d+)\+\s+completions$", "completions"),
    ]
    for pat, stat in patterns:
        m = re.match(pat, s)
        if m:
            n = int(m.group(1))
            return stat, "over", n - 0.5

    if s in ("anytime td", "anytime touchdown", "to score a touchdown", "1+ td", "1+ touchdown"):
        return "touchdowns", "over", 0.5
    return None

def normalize_nfl_quote(q: Quote) -> Quote:
    market = q.market
    side = _clean(q.side)
    threshold = q.threshold
    milestone = milestone_to_ou_threshold(market)
    if milestone:
        market, side, threshold = milestone
    else:
        market = canonical_stat(market)
    if market == "touchdowns" and side in ("yes", "anytime", "to score"):
        side = "over"
        if threshold is None:
            threshold = 0.5
    if side in ("o", "over"):
        side = "over"
    elif side in ("u", "under"):
        side = "under"
    elif side in ("y", "yes"):
        side = "yes"
    elif side in ("n", "no"):
        side = "no"
    return replace(q, market=market, side=side, threshold=threshold, period=canonical_period(q.period))

def normalize_nfl_quotes(quotes):
    return [normalize_nfl_quote(q) for q in quotes]
