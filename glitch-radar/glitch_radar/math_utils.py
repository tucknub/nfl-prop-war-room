from math import isfinite

def american_to_decimal(odds: int) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be 0")
    return 1 + (odds / 100 if odds > 0 else 100 / abs(odds))

def decimal_to_american(decimal: float) -> int:
    if decimal <= 1:
        raise ValueError("Decimal odds must be > 1")
    if decimal >= 2:
        return round((decimal - 1) * 100)
    return round(-100 / (decimal - 1))

def implied_probability(odds: int) -> float:
    return 1 / american_to_decimal(odds)

def boosted_decimal(odds: int, boost_pct: float) -> float:
    d = american_to_decimal(odds)
    return 1 + (d - 1) * (1 + boost_pct)

def boosted_american(odds: int, boost_pct: float) -> int:
    return decimal_to_american(boosted_decimal(odds, boost_pct))

def expected_value_from_fair_prob(offer_odds: int, fair_prob: float) -> float:
    return fair_prob * american_to_decimal(offer_odds) - 1

def no_vig_two_way(odds_a: int, odds_b: int):
    pa = implied_probability(odds_a)
    pb = implied_probability(odds_b)
    total = pa + pb
    return pa / total, pb / total

def median(xs):
    vals = sorted(xs)
    n = len(vals)
    if not n:
        raise ValueError("median requires data")
    m = n // 2
    return vals[m] if n % 2 else (vals[m-1] + vals[m]) / 2
