from dashboard.glitch_radar_props import (
    analyze_props,
    canonical_market,
    detect_ladder_violations,
    detect_line_gaps,
    detect_prop_price_outliers,
    detect_stale_props,
    normalize_prop_row,
)


def _row(book, player="A Receiver", market="player_reception_yds_alternate", line=50.5, over=100, under=-120, age=30):
    return {
        "event_id": "evt1",
        "commence_time": "2026-09-10T00:20:00Z",
        "home_team": "Home",
        "away_team": "Away",
        "source_title": book,
        "source": book.lower().replace(" ", ""),
        "player_name": player,
        "market_key": market,
        "market_label": "Receiving Yards",
        "line": line,
        "over_price": over,
        "under_price": under,
        "age_seconds": age,
    }


def test_market_aliases_normalize_nfl_prop_names():
    assert canonical_market("player_pass_yds") == "passing_yards"
    assert canonical_market("player_rush_yards_alternate") == "rushing_yards"
    assert canonical_market("player_rec_yds") == "receiving_yards"
    assert canonical_market("player_anytime_td") == "anytime_td"


def test_normalize_prop_row_canonicalizes_hard_rock():
    row = normalize_prop_row(_row("Hard Rock"))
    assert row["book"] == "Hard Rock Bet"
    assert row["market"] == "receiving_yards"
    assert row["line"] == 50.5


def test_prop_price_outlier_flags_user_book_against_same_line_peers():
    rows = [
        normalize_prop_row(_row("DraftKings", over=400, under=-600)),
        normalize_prop_row(_row("FanDuel", over=105, under=-125)),
        normalize_prop_row(_row("Caesars", over=100, under=-120)),
        normalize_prop_row(_row("BetRivers", over=110, under=-130)),
    ]
    alerts = detect_prop_price_outliers(rows)
    dk = [a for a in alerts if a["book"] == "DraftKings" and a["side"] == "over"]
    assert dk
    assert dk[0]["actionable"] is True
    assert dk[0]["severity"] in {"P0", "P1"}


def test_prop_price_outlier_ignores_near_even_sign_crossing():
    rows = [
        normalize_prop_row(_row("DraftKings", over=101, under=-121)),
        normalize_prop_row(_row("Hard Rock", over=100, under=-120)),
        normalize_prop_row(_row("Caesars", over=-105, under=-115)),
        normalize_prop_row(_row("FanDuel", over=-108, under=-112)),
    ]

    alerts = detect_prop_price_outliers(rows)

    assert not [row for row in alerts if row["side"] == "over"]


def test_prop_price_outlier_keeps_extreme_sign_mismatch():
    rows = [
        normalize_prop_row(_row("DraftKings", over=300, under=-500)),
        normalize_prop_row(_row("FanDuel", over=-180, under=150)),
        normalize_prop_row(_row("Caesars", over=-200, under=165)),
        normalize_prop_row(_row("Hard Rock", over=-190, under=160)),
    ]

    alerts = detect_prop_price_outliers(rows)
    dk = next(
        row for row in alerts
        if row["book"] == "DraftKings" and row["side"] == "over"
    )

    assert dk["sign_mismatch"] is True
    assert dk["absolute_prob_gap_points"] >= 20
    assert dk["severity"] == "P0"


def test_line_gap_requires_two_of_my_books_and_material_threshold():
    rows = [
        normalize_prop_row(_row("DraftKings", line=49.5)),
        normalize_prop_row(_row("FanDuel", line=55.5)),
        normalize_prop_row(_row("BetRivers", line=70.5)),
    ]
    alerts = detect_line_gaps(rows)
    assert len(alerts) == 1
    assert alerts[0]["low_book"] == "DraftKings"
    assert alerts[0]["high_book"] == "FanDuel"
    assert alerts[0]["line_gap"] == 6.0


def test_ladder_violation_flags_harder_over_as_more_likely():
    rows = [
        normalize_prop_row(_row("FanDuel", line=49.5, over=150)),
        normalize_prop_row(_row("FanDuel", line=59.5, over=-110)),
    ]
    alerts = detect_ladder_violations(rows)
    assert len(alerts) == 1
    assert alerts[0]["book"] == "FanDuel"
    assert alerts[0]["harder_line"] == 59.5
    assert alerts[0]["probability_inversion_points"] > 0


def test_stale_user_prop_flags_when_fresh_peer_exists():
    rows = [
        normalize_prop_row(_row("Caesars", age=900)),
        normalize_prop_row(_row("FanDuel", age=45)),
        normalize_prop_row(_row("BetRivers", age=60)),
    ]
    alerts = detect_stale_props(rows)
    assert len(alerts) == 1
    assert alerts[0]["book"] == "Caesars"
    assert "FanDuel" in alerts[0]["fresh_peer_books"]


def test_analyze_props_returns_all_detector_buckets_and_coverage():
    rows = [
        normalize_prop_row(_row("DraftKings", line=49.5, over=400, age=900)),
        normalize_prop_row(_row("FanDuel", line=49.5, over=100, age=40)),
        normalize_prop_row(_row("Caesars", line=49.5, over=105, age=50)),
        normalize_prop_row(_row("Hard Rock", line=55.5, over=125, age=60)),
    ]
    result = analyze_props(rows)
    assert result["coverage"]["rows"] == 4
    assert result["coverage"]["players"] == 1
    assert result["price_outliers"]
    assert result["line_gaps"]
    assert "ladder_violations" in result
    assert "stale_props" in result
