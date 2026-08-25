from dashboard.glitch_radar_grouping import group_ev_wagers, market_label


def test_group_ev_wagers_keeps_best_price_and_alternates_separate():
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
    wager = grouped[0]
    assert wager["book"] == "DraftKings"
    assert wager["price"] == 144
    assert wager["selection"] == "San Francisco 49ers"
    assert wager["display_market"] == "ML"
    assert wager["side"] == "San Francisco 49ers ML"
    assert "alt" not in wager["side"].lower()
    assert wager["alternate_books"][0]["book"] == "Caesars"
    assert wager["alternate_books"][0]["price"] == 142


def test_market_label_moneyline():
    assert market_label({"market": "moneyline"}) == "ML"
