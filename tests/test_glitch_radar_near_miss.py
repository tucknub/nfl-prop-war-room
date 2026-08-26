from dashboard.glitch_radar_near_miss import build_near_miss_anomalies


def _row(book, *, player="A Receiver", line=50.5, over=100, under=-120, market="receiving_yards"):
    return {
        "event_id": "evt1",
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


def test_near_miss_excludes_true_glitch_level_price():
    rows = [
        _row("DraftKings", over=400, under=-600),
        _row("FanDuel", over=105, under=-125),
        _row("Caesars", over=100, under=-120),
        _row("Novig", over=102, under=-122),
    ]
    watches = build_near_miss_anomalies(rows)
    assert not [row for row in watches if row["book"] == "DraftKings" and row["side"] == "over"]


def test_near_miss_ignores_dfs_midpoint_as_comparable_price_peer():
    rows = [
        _row("DraftKings", over=130, under=-160),
        _row("FanDuel", over=105, under=-125),
        _row("Sleeper", over=100, under=100),
    ]
    watches = build_near_miss_anomalies(rows)
    assert watches == []


def test_near_miss_requires_actionable_user_book():
    rows = [
        _row("BetRivers", over=130, under=-160),
        _row("Novig", over=105, under=-125),
        _row("Pinnacle", over=100, under=-120),
    ]
    watches = build_near_miss_anomalies(rows)
    assert watches == []
