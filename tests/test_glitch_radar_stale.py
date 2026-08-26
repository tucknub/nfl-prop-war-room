from dashboard.glitch_radar_stale import coverage_quality, enrich_stale_alerts


def _row(book, *, player="A Receiver", age=30, over=-110, under=-110, event="evt1"):
    return {
        "event_id": event,
        "commence_time": "2026-09-10T00:20:00Z",
        "home_team": "Home",
        "away_team": "Away",
        "book": book,
        "player": player,
        "market_key": "player_receptions",
        "market": "receptions",
        "market_label": "Receptions O/U",
        "line": 5.5,
        "over_price": over,
        "under_price": under,
        "age_seconds": age,
    }


def _alert(book="DraftKings", *, age=900, over=-110, under=-110):
    row = _row(book, age=age, over=over, under=under)
    return {
        "book": row["book"],
        "commence_time": row["commence_time"],
        "home_team": row["home_team"],
        "away_team": row["away_team"],
        "player": row["player"],
        "market": row["market"],
        "market_label": row["market_label"],
        "line": row["line"],
        "over_price": row["over_price"],
        "under_price": row["under_price"],
        "age_seconds": row["age_seconds"],
    }


def test_stale_alert_enriches_with_fresh_sportsbook_price_and_marks_better_side():
    alert = _alert(over=-110, under=-120)
    rows = [
        _row("DraftKings", age=900, over=-110, under=-120),
        _row("Novig", age=45, over=-125, under=-105),
        _row("BetRivers", age=60, over=-120, under=-110),
    ]
    enriched = enrich_stale_alerts([alert], rows)
    assert len(enriched) == 1
    item = enriched[0]
    assert item["freshest_peer_book"] == "Novig"
    assert item["over_comparison"]["status"] == "stale_better"
    assert item["over_comparison"]["peer_book"] == "BetRivers"
    assert item["under_comparison"]["status"] == "peer_better"


def test_dfs_only_freshness_does_not_create_actionable_stale_price_watch():
    alert = _alert()
    rows = [
        _row("DraftKings", age=900),
        _row("Sleeper", age=20, over=100, under=100),
        _row("PrizePicks", age=25, over=100, under=100),
    ]
    assert enrich_stale_alerts([alert], rows) == []


def test_dfs_peer_is_retained_only_as_secondary_context_when_price_peer_exists():
    alert = _alert()
    rows = [
        _row("DraftKings", age=900),
        _row("Novig", age=40, over=-115, under=-105),
        _row("Sleeper", age=10, over=100, under=100),
    ]
    item = enrich_stale_alerts([alert], rows)[0]
    assert item["fresh_peer_books"] == ["Novig"]
    assert item["dfs_fresh_peer_books"] == ["Sleeper"]
    assert item["freshest_peer_book"] == "Novig"


def test_coverage_quality_uses_cross_book_player_identity_and_ignores_non_player_markets():
    rows = [
        _row("DraftKings", player="A Receiver"),
        _row("FanDuel", player="A Receiver"),
        _row("Caesars", player="Solo Player"),
        {**_row("DraftKings", player="Not A Player"), "market_key": "team_total"},
    ]
    quality = coverage_quality(rows)
    assert quality["raw_player_labels"] == 2
    assert quality["cross_book_players"] == 1
    assert quality["player_event_identities"] == 2
    assert quality["cross_book_player_events"] == 1
