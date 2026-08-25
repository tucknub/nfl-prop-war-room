from dashboard.glitch_radar_enrich import enrich_ev_markets


def test_enrich_ev_moneyline_from_live_quote():
    ev = [
        {
            "away_team": "San Francisco 49ers",
            "home_team": "Las Vegas Raiders",
            "side": "San Francisco 49ers",
            "book": "DraftKings",
            "price": 144,
        }
    ]
    quotes = [
        {
            "event": "San Francisco 49ers @ Las Vegas Raiders",
            "book": "DraftKings",
            "market": "moneyline",
            "side": "away",
            "participant": "",
            "threshold": None,
            "odds_american": 144,
        }
    ]
    result = enrich_ev_markets(ev, quotes)
    assert result[0]["market"] == "moneyline"
    assert result[0]["threshold"] is None


def test_enrich_does_not_force_generic_over_under_to_moneyline():
    ev = [
        {
            "away_team": "A",
            "home_team": "B",
            "side": "Over",
            "book": "DraftKings",
            "price": -110,
        }
    ]
    result = enrich_ev_markets(ev, [])
    assert "market" not in result[0]
