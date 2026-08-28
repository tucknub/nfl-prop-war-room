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
            "commence_time": "2026-08-29T00:00:00.000Z",
        }
    ]
    result = enrich_ev_markets(ev, quotes)
    assert result[0]["market"] == "moneyline"
    assert result[0]["threshold"] is None
    assert result[0]["commence_time"] == "2026-08-29T00:00:00.000Z"


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


def test_enrich_ev_keeps_existing_market_but_still_attaches_event_time():
    ev = [
        {
            "away_team": "Arizona Cardinals",
            "home_team": "Green Bay Packers",
            "side": "Arizona Cardinals",
            "book": "FanDuel",
            "price": 450,
            "market": "moneyline",
        }
    ]
    quotes = [
        {
            "event": "Arizona Cardinals @ Green Bay Packers",
            "book": "FanDuel",
            "market": "moneyline",
            "side": "away",
            "participant": "",
            "threshold": None,
            "odds_american": 450,
            "commence_time": "2026-08-29T00:00:00.000Z",
        }
    ]

    result = enrich_ev_markets(ev, quotes)

    assert result[0]["market"] == "moneyline"
    assert result[0]["commence_time"] == "2026-08-29T00:00:00.000Z"
