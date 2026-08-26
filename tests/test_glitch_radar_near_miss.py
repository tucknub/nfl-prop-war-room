from dashboard.glitch_radar_near_miss import build_near_miss_anomalies


def _row(book, *, player="A Receiver", line=50.5, over=100, under=-120, market="receiving_yards", event_id="evt1"):
    return {
        "event_id": event_id,
        "commence_time": "2026-09-10T00:20:00Z",
        "home_team": "Home",
        "away_team": "Away",
        "book": book,
        "player": player,
        "market_key": "player_reception_yds",
        "market": market,
        "market_label": "Receiving Yards O/U",
        "line": line,
        "over_price": over,
        "under_price": under,
        "age_seconds": 30,
    }


def test_near_miss_surfaces_user_book_below_true_glitch_threshold():
    rows = [
        _row("DraftKings", over=130, under=-160),
        _row("FanDuel", over=105, under=-125),
        _row("Caesars", over=100, under=-120),
        _row("Novig", over=102, under=-122),
    ]
    watches = build_near_miss_anomalies(rows)
    dk_over = [row for row in watches if row["book"] == "DraftKings" and row["side"] == "over"]
    assert dk_over
    assert 0 < dk_over[0]["glitch_threshold_proximity_pct"] < 100
    assert dk_over[0]["relative_prob_deviation_pct"] < 25
    assert dk_over[0]["payout_multiple_vs_peers"] < 1.60
    assert dk_over[0]["num_books"] == 4


def test_near_miss_excludes_true_glitch_level_price():
    rows = [
        _row("DraftKings", over=400, under=-600),
        _row("FanDuel", over=105, under=-125),
        _row("Caesars", over=100, under=-120),
        _row("Novig", over=102, under=-122),
    ]
    watches = build_near_miss_anomalies(rows)
    assert not [row for row in watches if row["book"] == "DraftKings" and row["side"] == "over"]


def test_near_miss_two_real_books_are_enough_for_diagnostic():
    rows = [
        _row("DraftKings", over=120, under=-150),
        _row("FanDuel", over=105, under=-125),
    ]
    watches = build_near_miss_anomalies(rows)
    dk_over = [row for row in watches if row["book"] == "DraftKings" and row["side"] == "over"]
    assert dk_over
    assert dk_over[0]["num_books"] == 2
    assert dk_over[0]["peer_books"] == ["FanDuel"]


def test_near_miss_surfaces_tiny_real_price_difference():
    rows = [
        _row("DraftKings", over=-109, under=-111),
        _row("FanDuel", over=-110, under=-110),
    ]
    watches = build_near_miss_anomalies(rows)
    assert [row for row in watches if row["book"] == "DraftKings" and row["side"] == "over"]


def test_near_miss_does_not_create_watch_when_prices_are_identical():
    rows = [
        _row("DraftKings", over=-110, under=-110),
        _row("FanDuel", over=-110, under=-110),
    ]
    assert build_near_miss_anomalies(rows) == []


def test_near_miss_ignores_dfs_midpoint_as_comparable_price_peer():
    rows = [
        _row("DraftKings", over=120, under=-150),
        _row("FanDuel", over=105, under=-125),
        _row("Sleeper", over=300, under=-300),
    ]
    watches = build_near_miss_anomalies(rows)
    assert watches
    assert all("Sleeper" not in row["peer_books"] for row in watches)
    assert all(row["num_books"] == 2 for row in watches)


def test_near_miss_groups_same_matchup_even_when_source_event_ids_differ():
    rows = [
        _row("DraftKings", over=120, under=-150, event_id="dk_evt"),
        _row("FanDuel", over=105, under=-125, event_id="fd_evt"),
    ]
    watches = build_near_miss_anomalies(rows)
    assert [row for row in watches if row["book"] == "DraftKings" and row["side"] == "over"]


def test_near_miss_requires_actionable_user_book():
    rows = [
        _row("BetRivers", over=130, under=-160),
        _row("Novig", over=105, under=-125),
        _row("Pinnacle", over=100, under=-120),
    ]
    watches = build_near_miss_anomalies(rows)
    assert watches == []
