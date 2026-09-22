from datetime import datetime, timedelta, timezone

import dashboard.glitch_radar_live as live
from dashboard.glitch_radar_live import (
    Quote,
    detect_price_outliers,
    filter_pregame_opportunities,
    is_pregame,
)


def _moneyline_quotes(commence_time: str) -> list[Quote]:
    common = {
        "event": "Washington Commanders @ Baltimore Ravens",
        "market": "moneyline",
        "side": "away",
        "commence_time": commence_time,
    }
    return [
        Quote(book="FanDuel", odds_american=4000, **common),
        Quote(book="DraftKings", odds_american=158, **common),
        Quote(book="Hard Rock Bet", odds_american=135, **common),
    ]


def test_pregame_outlier_still_surfaces_before_kickoff():
    now = datetime(2026, 8, 29, 0, 30, tzinfo=timezone.utc)
    commence = (now + timedelta(hours=1)).isoformat()

    alerts = detect_price_outliers(_moneyline_quotes(commence), now=now)

    assert any(
        alert["quote"]["book"] == "FanDuel"
        and alert["quote"]["odds_american"] == 4000
        for alert in alerts
    )


def test_started_event_cannot_generate_glitch_alert():
    now = datetime(2026, 8, 29, 1, 30, tzinfo=timezone.utc)
    commence = (now - timedelta(minutes=30)).isoformat()

    alerts = detect_price_outliers(_moneyline_quotes(commence), now=now)

    assert alerts == []


def test_started_opportunities_are_removed_but_future_and_unknown_are_kept():
    now = datetime(2026, 8, 29, 1, 30, tzinfo=timezone.utc)
    rows = [
        {"id": "live", "commence_time": (now - timedelta(minutes=1)).isoformat()},
        {"id": "future", "commence_time": (now + timedelta(minutes=1)).isoformat()},
        {"id": "nested-live", "event": {"commence_time": (now - timedelta(hours=1)).isoformat()}},
        {"id": "unknown"},
    ]

    kept = filter_pregame_opportunities(rows, now=now)

    assert [row["id"] for row in kept] == ["future", "unknown"]


def test_kickoff_boundary_fails_closed_for_actionable_market():
    now = datetime(2026, 8, 29, 1, 30, tzinfo=timezone.utc)

    assert is_pregame(now.isoformat(), now=now) is False


def test_snapshot_marks_core_odds_failure_instead_of_zero_signal(monkeypatch):
    def fake_get(path, params=None):
        if path.endswith("/odds"):
            raise RuntimeError("provider down")
        if path.startswith("/live/api/"):
            return {}
        return {"opportunities": []}

    monkeypatch.setattr(live, "_get", fake_get)
    snapshot = live.build_snapshot()

    assert snapshot["feed_status"]["odds"] == "ERROR"
    assert snapshot["quotes"] == []
    assert any(error.startswith("odds:") for error in snapshot["errors"])


def test_snapshot_marks_empty_odds_payload_as_empty(monkeypatch):
    def fake_get(path, params=None):
        if path.endswith("/odds"):
            return {"events": []}
        if path.startswith("/live/api/"):
            return {}
        return {"opportunities": []}

    monkeypatch.setattr(live, "_get", fake_get)
    snapshot = live.build_snapshot()

    assert snapshot["feed_status"]["odds"] == "EMPTY"
    assert snapshot["errors"] == []
