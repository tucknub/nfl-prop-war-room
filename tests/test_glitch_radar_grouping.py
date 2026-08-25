from dashboard.glitch_radar_grouping import group_ev_wagers, market_label


def test_group_ev_wagers_keeps_best_price_and_alternates():
    rows = [
        {
            "away_team": "San Francisco 49ers",
            "home_team": "Las Vegas Raiders",
            "side": "San Francisco 49ers",
            "market": "moneyline",
            "book": "DraftKings",
            "price": 144,
            "fair_prob_pct": 45.13,
        },
        {
            "away_team": "San Francisco 49ers",
            "home_team": "Las Vegas Raiders",
            "side": "San Francisco 49ers",
            "market": "moneyline",
            "book": "Caesars",
            "price": 142,
            "fair_prob_pct": 45.13,
        },
    ]
    grouped = group_ev_wagers(rows)
    assert len(grouped) == 1
    assert grouped[0]["book"] == "DraftKings"
    assert grouped[0]["price"] == 144
    assert grouped[0]["alternate_books"][0]["book"] == "Caesars"


def test_market_label_moneyline():
    assert market_label({"market": "moneyline"}) == "ML"
