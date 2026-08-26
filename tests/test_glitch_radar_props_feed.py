from dashboard.glitch_radar_props_feed import normalize_feed_row


def test_current_documented_prop_schema_normalizes():
    row = normalize_feed_row(
        {
            "canonical_event_id": "evt-current",
            "commence_time": "2026-09-10T00:20:00Z",
            "home_team": "Home",
            "away_team": "Away",
            "bookmaker": "hardrock",
            "bookmaker_title": "Hard Rock",
            "player": "Example Receiver",
            "market_key": "player_rec_yds",
            "market": "Receiving Yards",
            "line": 64.5,
            "over_price": 120,
            "under_price": -145,
            "last_update": "2026-09-09T23:55:00Z",
            "age_seconds": 42,
        }
    )
    assert row["event_id"] == "evt-current"
    assert row["book"] == "Hard Rock Bet"
    assert row["player"] == "Example Receiver"
    assert row["market"] == "receiving_yards"
    assert row["market_label"] == "Receiving Yards"
    assert row["line"] == 64.5
    assert row["over_price"] == 120
    assert row["snapshot_time"] == "2026-09-09T23:55:00Z"


def test_older_response_shape_schema_still_normalizes():
    row = normalize_feed_row(
        {
            "event_id": "evt-old",
            "source": "draftkings",
            "source_title": "DraftKings",
            "player_name": "Example Runner",
            "market_key": "player_rush_yds",
            "market_label": "Rushing Yards",
            "line": 54.5,
            "over_price": -110,
            "under_price": -110,
            "snapshot_time": "2026-09-09T23:55:00Z",
            "age_seconds": 20,
        }
    )
    assert row["event_id"] == "evt-old"
    assert row["book"] == "DraftKings"
    assert row["player"] == "Example Runner"
    assert row["market"] == "rushing_yards"
