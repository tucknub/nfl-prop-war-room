from .math_utils import boosted_american, implied_probability, american_to_decimal, expected_value_from_fair_prob

def evaluate_profit_boost(odds_american, fair_prob, boost_pct, stake=1.0):
    boosted = boosted_american(odds_american, boost_pct)
    ev_pct = expected_value_from_fair_prob(boosted, fair_prob)
    return {
        "original_odds": odds_american,
        "boosted_odds": boosted,
        "fair_prob": fair_prob,
        "ev_pct": ev_pct,
        "expected_profit_dollars": stake * ev_pct,
    }

def evaluate_bonus_bet(odds_american, fair_prob, bonus_amount=1.0):
    d = american_to_decimal(odds_american)
    expected_cash = fair_prob * (d - 1) * bonus_amount
    return {
        "odds": odds_american,
        "fair_prob": fair_prob,
        "expected_cash": expected_cash,
        "conversion_rate": expected_cash / bonus_amount if bonus_amount else 0,
    }

def promo_arb(boosted_odds_a, opposing_odds_b):
    idx = implied_probability(boosted_odds_a) + implied_probability(opposing_odds_b)
    return {
        "arb_index": idx,
        "is_arb": idx < 1,
        "guaranteed_roi": (1 / idx - 1) if idx < 1 else 0,
    }
