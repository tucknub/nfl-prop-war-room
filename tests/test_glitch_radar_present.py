from dashboard.glitch_radar_present import (
    expected_ev_pct,
    fair_american_from_probability,
    format_american,
    game_name,
    probability_edge_points,
    value_tier,
)


def test_value_example_converts_probability_to_fair_line_and_ev():
    assert fair_american_from_probability(45.13) == 122
    ev = expected_ev_pct(144, 45.13)
    assert ev is not None
    assert round(ev, 1) == 10.1


def test_probability_edge_is_probability_points_not_return_ev():
    row = {"book_implied_pct": 40.98, "fair_prob_pct": 45.13, "edge_pct": 4.146}
    assert probability_edge_points(row) == 4.146


def test_price_format_and_game_name_are_human_readable():
    assert format_american(144) == "+144"
    assert format_american(-115) == "-115"
    assert game_name({"away_team": "San Francisco 49ers", "home_team": "Las Vegas Raiders"}) == (
        "San Francisco 49ers @ Las Vegas Raiders"
    )


def test_value_tier_is_based_on_calculated_ev_not_probability_gap():
    assert value_tier(12.0) == "PREMIUM PRICE"
    assert value_tier(10.1) == "STRONG PRICE"
    assert value_tier(4.0) == "POSITIVE PRICE"
    assert value_tier(1.0) == "THIN EDGE"
    assert value_tier(-0.1) == "PASS"
