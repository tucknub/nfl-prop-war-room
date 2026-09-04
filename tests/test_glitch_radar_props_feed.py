import httpx
import pytest

from dashboard.glitch_radar_props_feed import (
    PropsFeedUnavailable,
    fetch_full_props,
    normalize_feed_row,
)


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



class _Response:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://parlay-api.com/test")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)


def test_fetch_full_props_enforces_freshness_locally_without_max_age_query(monkeypatch):
    seen = {}

    def fake_get(url, *, params, headers, timeout, follow_redirects):
        seen["params"] = params
        return _Response(
            200,
            [
                {
                    "bookmaker": "draftkings",
                    "player": "Fresh Player",
                    "market_key": "player_rec_yds",
                    "line": 50.5,
                    "over_price": -110,
                    "under_price": -110,
                    "age_seconds": 45,
                },
                {
                    "bookmaker": "fanduel",
                    "player": "Stale Player",
                    "market_key": "player_rec_yds",
                    "line": 60.5,
                    "over_price": -110,
                    "under_price": -110,
                    "age_seconds": 121,
                },
                {
                    "bookmaker": "caesars",
                    "player": "Undated Player",
                    "market_key": "player_rec_yds",
                    "line": 70.5,
                    "over_price": -110,
                    "under_price": -110,
                },
            ],
        )

    monkeypatch.setattr("dashboard.glitch_radar_props_feed.httpx.get", fake_get)

    rows = fetch_full_props("test-key", max_age_sec=120)

    assert seen["params"] == {"limit": 10000}
    assert [row["player"] for row in rows] == ["Fresh Player"]


def test_fetch_full_props_turns_provider_500_into_clean_unavailable_state(monkeypatch):
    def fake_get(url, *, params, headers, timeout, follow_redirects):
        return _Response(500, {"detail": "provider failure"})

    monkeypatch.setattr("dashboard.glitch_radar_props_feed.httpx.get", fake_get)

    with pytest.raises(PropsFeedUnavailable, match="temporarily unavailable"):
        fetch_full_props("test-key")
