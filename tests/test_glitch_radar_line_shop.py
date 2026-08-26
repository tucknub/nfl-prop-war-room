from dashboard.glitch_radar_line_shop import build_line_shop_watches


def _row(
    book,
    *,
    line=50.5,
    over=-110,
    under=-110,
    player="A Receiver",
    market="receiving_yards",
    market_key="player_reception_yds",
):
    return {
        "event_id": "evt1",
        "commence_time": "2026-09-10T00:20:00Z",
        "home_team": "Home",
        "away_team": "Away",
        "book": book,
        "player": player,
        "market": market,
        "market_key": market_key,
        "market_label": "Receiving Yards O/U",
        "line": line,
        "over_price": over,
        "under_price": under,
    }


def test_over_prefers_lower_line_at_similar_price():
    rows = [
        _row("DraftKings", line=64.5, over=-115),
        _row("FanDuel", line=69.5, over=-110),
    ]
    watches = build_line_shop_watches(rows)
    dk = [row for row in watches if row["book"] == "DraftKings" and row["side"] == "over"]
    assert dk
    assert dk[0]["book_line"] == 64.5
    assert dk[0]["peer_line"] == 69.5
    assert dk[0]["line_advantage"] == 5.0


def test_under_prefers_higher_line_at_similar_price():
    rows = [
        _row("Hard Rock Bet", line=74.5, under=-115),
        _row("Caesars", line=69.5, under=-110),
    ]
    watches = build_line_shop_watches(rows)
    hr = [row for row in watches if row["book"] == "Hard Rock Bet" and row["side"] == "under"]
    assert hr
    assert hr[0]["book_line"] == 74.5
    assert hr[0]["peer_line"] == 69.5


def test_rejects_easier_threshold_when_price_cost_is_too_large():
    rows = [
        _row("DraftKings", line=64.5, over=-180),
        _row("FanDuel", line=69.5, over=-110),
    ]
    watches = build_line_shop_watches(rows)
    assert not [row for row in watches if row["book"] == "DraftKings" and row["side"] == "over"]


def test_reference_book_can_establish_comparison_but_candidate_must_be_user_book():
    rows = [
        _row("DraftKings", line=64.5, over=-110),
        _row("Pinnacle", line=69.5, over=-110),
    ]
    watches = build_line_shop_watches(rows)
    assert [row for row in watches if row["book"] == "DraftKings" and row["peer_book"] == "Pinnacle"]
    assert not [row for row in watches if row["book"] == "Pinnacle"]


def test_dfs_midpoint_is_excluded():
    rows = [
        _row("DraftKings", line=64.5, over=-110),
        _row("Sleeper", line=69.5, over=100, under=100),
    ]
    assert build_line_shop_watches(rows) == []


def test_alt_and_base_rows_can_create_threshold_comparison():
    rows = [
        _row("bet365", line=59.5, over=-120, market_key="player_reception_yds_alternate"),
        _row("FanDuel", line=64.5, over=-115, market_key="player_reception_yds"),
    ]
    watches = build_line_shop_watches(rows)
    b365 = [row for row in watches if row["book"] == "bet365" and row["side"] == "over"]
    assert b365
    assert b365[0]["line_advantage"] == 5.0
