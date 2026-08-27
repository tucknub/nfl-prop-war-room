from __future__ import annotations

from datetime import datetime, timezone

from dashboard.glitch_radar_history import (
    AGING,
    DISAPPEARED,
    FRESH,
    IMPROVED,
    REAPPEARED,
    STALE,
    build_market_observations,
    empty_market_history,
    freshness_status,
    history_for_key,
    recent_history_changes,
    update_market_history,
)
from dashboard.glitch_radar_history_private import PrivateMarketHistoryStore


def _alert(price: int = 120) -> dict:
    return {
        "quote": {
            "book": "DraftKings",
            "event": "BUF @ BAL",
            "market": "moneyline",
            "participant": "",
            "side": "away",
            "threshold": None,
            "odds_american": price,
        }
    }


def test_market_history_preserves_opening_price_and_recent_change_timeline():
    state = empty_market_history()
    first = build_market_observations((_alert(120),), ())
    state = update_market_history(
        state,
        first,
        fetched_at="2026-08-27T22:00:00+00:00",
    )
    key = next(iter(first))

    initial = history_for_key(state, key)
    assert initial is not None
    assert initial["opening_price"] == 120
    assert initial["previous_price"] is None
    assert initial["current_price"] == 120
    assert recent_history_changes(state) == ()

    improved = build_market_observations((_alert(145),), ())
    state = update_market_history(
        state,
        improved,
        fetched_at="2026-08-27T22:10:00+00:00",
    )
    row = history_for_key(state, key)

    assert row is not None
    assert row["status"] == IMPROVED
    assert row["opening_price"] == 120
    assert row["previous_price"] == 120
    assert row["current_price"] == 145

    changes = recent_history_changes(state)
    assert changes[0]["status"] == IMPROVED
    assert changes[0]["opening_price"] == 120
    assert changes[0]["previous_price"] == 120
    assert changes[0]["current_price"] == 145


def test_disappearance_and_reappearance_survive_more_than_one_scan():
    observations = build_market_observations((_alert(120),), ())
    key = next(iter(observations))
    state = update_market_history(
        empty_market_history(),
        observations,
        fetched_at="2026-08-27T22:00:00+00:00",
    )
    state = update_market_history(
        state,
        {},
        fetched_at="2026-08-27T22:10:00+00:00",
    )

    assert state["disappeared"][0]["status"] == DISAPPEARED
    assert recent_history_changes(state)[0]["status"] == DISAPPEARED

    returned = build_market_observations((_alert(130),), ())
    state = update_market_history(
        state,
        returned,
        fetched_at="2026-08-27T22:20:00+00:00",
    )
    row = history_for_key(state, key)

    assert row is not None
    assert row["status"] == REAPPEARED
    assert row["opening_price"] == 120
    assert row["previous_price"] == 120
    assert row["current_price"] == 130
    statuses = [change["status"] for change in recent_history_changes(state)]
    assert statuses[:2] == [REAPPEARED, DISAPPEARED]


def test_same_snapshot_timestamp_does_not_create_fake_history_event():
    observations = build_market_observations((_alert(120),), ())
    state = update_market_history(
        empty_market_history(),
        observations,
        fetched_at="2026-08-27T22:00:00+00:00",
    )
    unchanged = update_market_history(
        state,
        build_market_observations((_alert(180),), ()),
        fetched_at="2026-08-27T22:00:00+00:00",
    )

    assert unchanged == state


def test_freshness_status_has_explicit_age_bands():
    now = datetime(2026, 8, 27, 22, 30, tzinfo=timezone.utc)

    assert freshness_status(
        "2026-08-27T22:20:00+00:00",
        now=now,
    ) == FRESH
    assert freshness_status(
        "2026-08-27T22:10:00+00:00",
        now=now,
    ) == AGING
    assert freshness_status(
        "2026-08-27T21:50:00+00:00",
        now=now,
    ) == STALE


class _Response:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_private_history_store_creates_file_once_and_skips_duplicate_scan(
    monkeypatch,
):
    from dashboard import glitch_radar_history_private as private

    monkeypatch.setattr(
        private.state_store,
        "assert_private_repository",
        lambda config: None,
    )

    get_calls = []
    put_calls = []

    def fake_get(*args, **kwargs):
        get_calls.append((args, kwargs))
        return _Response(404, {})

    def fake_put(*args, **kwargs):
        put_calls.append((args, kwargs))
        return _Response(
            201,
            {"content": {"sha": "created-sha"}},
        )

    monkeypatch.setattr(private.httpx, "get", fake_get)
    monkeypatch.setattr(private.httpx, "put", fake_put)

    store = PrivateMarketHistoryStore(
        {
            "token": "secret",
            "repo": "owner/private-state",
            "branch": "main",
            "path": "glitch/market_history.json",
        }
    )
    observations = build_market_observations((_alert(120),), ())

    first = store.update(
        observations,
        fetched_at="2026-08-27T22:00:00+00:00",
    )
    duplicate = store.update(
        observations,
        fetched_at="2026-08-27T22:00:00+00:00",
    )

    assert first == duplicate
    assert len(get_calls) == 1
    assert len(put_calls) == 1
    assert "Authorization" in put_calls[0][1]["headers"]
    assert "secret" not in str(first)


def test_history_config_reuses_private_state_repo_with_separate_path():
    from dashboard.glitch_radar_history_private import (
        DEFAULT_HISTORY_PATH,
        history_config_from_secrets,
    )

    secrets = {
        "MARGIN_GITHUB_TOKEN": "token",
        "MARGIN_GITHUB_REPO": "owner/private-state",
        "MARGIN_GITHUB_BRANCH": "main",
        "MARGIN_STATE_PATH": "margin/live_state_2026.json",
        "PROPWAR_OWNER_EMAIL": "owner@example.com",
        "auth": {
            "redirect_uri": "https://example.com/oauth2callback",
            "cookie_secret": "cookie",
            "client_id": "client",
            "client_secret": "secret",
            "server_metadata_url": "https://example.com/.well-known/openid-configuration",
        },
    }

    config = history_config_from_secrets(secrets)

    assert config is not None
    assert config["repo"] == "owner/private-state"
    assert config["path"] == DEFAULT_HISTORY_PATH
    assert config["path"] != secrets["MARGIN_STATE_PATH"]


def test_glitch_radar_page_exposes_durable_history_and_fallback_contract():
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "dashboard"
        / "pages"
        / "09_Glitch_Radar.py"
    ).read_text(encoding="utf-8")

    assert "Private durable history" in source
    assert "In-memory fallback" in source
    assert "Recent movement history" in source
    assert "What moved now" in source
    assert "Opening" in source
    assert "Previous" in source
    assert "Freshness" in source
    assert "resets this in-memory history" not in source
