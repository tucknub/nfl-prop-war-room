from __future__ import annotations

import httpx
import pandas as pd
import pytest

from src.fantasy.catalog import (
    CATALOG_FORCED_REFRESH,
    CATALOG_HIT,
    CATALOG_MISS,
    CATALOG_REFRESHED,
    CATALOG_STALE_FALLBACK,
    MemorySleeperPlayerCatalogStore,
    SleeperPlayerCatalogClient,
    SleeperPlayerCatalogSnapshot,
    load_sleeper_player_catalog,
    normalize_sleeper_player_catalog,
)
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.service import sync_sleeper_leagues_with_catalog


class FakeCatalogReader:
    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else {"1": {"full_name": "One", "position": "RB", "team": "IND"}}
        self.error = error
        self.calls = 0

    def fetch_nfl_players(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.payload


class FakeLeagueReader:
    def __init__(self, states):
        self.states = dict(states)
        self.calls = []

    def fetch_normalized_league(self, league_id, *, current_user_id=None):
        self.calls.append((league_id, current_user_id))
        return self.states[league_id]


def _state(league_id: str) -> FantasyLeagueState:
    roster = Roster(
        platform_roster_id="1",
        platform_user_id="me",
        players=("1",),
        starters=("1",),
        reserve=(),
        taxi=(),
        settings={},
    )
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=league_id,
        name=f"League {league_id}",
        season="2026",
        status="in_season",
        team_count=1,
        previous_platform_league_id=None,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(roster_positions=("RB", "BN"), scoring_settings={"rec": 1}),
        draft=None,
        managers=(),
        rosters=(roster,),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _ffverse():
    return pd.DataFrame(
        [{"sleeper_id": "1", "gsis_id": "00-1", "yahoo_id": "101", "name": "One", "position": "RB", "team": "IND"}]
    )


def _propwar():
    return pd.DataFrame({"player_id": ["00-1"], "player_name": ["One"]})


def test_http_catalog_client_fetches_only_players_nfl_and_normalizes_rows():
    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(
            200,
            json={"1": {"full_name": "One", "position": "RB", "team": "IND"}},
        )

    http_client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.sleeper.app/v1/",
    )
    reader = SleeperPlayerCatalogClient(client=http_client)

    players = reader.fetch_nfl_players()

    assert seen == ["/v1/players/nfl"]
    assert players["1"]["full_name"] == "One"


def test_malformed_or_empty_catalog_is_rejected():
    for payload in ([], {}, {"1": None}):
        with pytest.raises(ValueError):
            normalize_sleeper_player_catalog(payload)


def test_fresh_cache_hit_skips_provider_fetch():
    now = 2_000_000
    cached = SleeperPlayerCatalogSnapshot(
        fetched_at_ms=now - 30_000,
        players={"1": {"full_name": "Cached"}},
    )
    store = MemorySleeperPlayerCatalogStore(snapshot=cached)
    reader = FakeCatalogReader(error=AssertionError("provider should not be called"))

    result = load_sleeper_player_catalog(reader, store, now_ms=now, ttl_seconds=60)

    assert result.cache_status == CATALOG_HIT
    assert result.snapshot is cached
    assert result.age_seconds == 30
    assert reader.calls == 0
    assert store.saves == 0


def test_cache_miss_fetches_and_saves_once():
    store = MemorySleeperPlayerCatalogStore()
    reader = FakeCatalogReader()

    result = load_sleeper_player_catalog(reader, store, now_ms=1_000_000, ttl_seconds=60)

    assert result.cache_status == CATALOG_MISS
    assert reader.calls == 1
    assert store.saves == 1
    assert store.snapshot is result.snapshot
    assert result.snapshot.fetched_at_ms == 1_000_000


def test_stale_cache_refreshes_and_force_refresh_bypasses_fresh_hit():
    cached = SleeperPlayerCatalogSnapshot(
        fetched_at_ms=1_000_000,
        players={"1": {"full_name": "Old"}},
    )
    store = MemorySleeperPlayerCatalogStore(snapshot=cached)
    reader = FakeCatalogReader(payload={"1": {"full_name": "New"}})

    refreshed = load_sleeper_player_catalog(
        reader,
        store,
        now_ms=1_120_000,
        ttl_seconds=60,
    )
    forced = load_sleeper_player_catalog(
        reader,
        store,
        now_ms=1_121_000,
        ttl_seconds=60,
        force_refresh=True,
    )

    assert refreshed.cache_status == CATALOG_REFRESHED
    assert refreshed.snapshot.players["1"]["full_name"] == "New"
    assert forced.cache_status == CATALOG_FORCED_REFRESH
    assert reader.calls == 2
    assert store.saves == 2


def test_recent_stale_cache_is_explicit_fallback_when_provider_fails():
    cached = SleeperPlayerCatalogSnapshot(
        fetched_at_ms=1_000_000,
        players={"1": {"full_name": "Cached"}},
    )
    store = MemorySleeperPlayerCatalogStore(snapshot=cached)
    reader = FakeCatalogReader(error=httpx.ConnectError("temporary outage"))

    result = load_sleeper_player_catalog(
        reader,
        store,
        now_ms=1_120_000,
        ttl_seconds=60,
        max_stale_seconds=300,
    )

    assert result.cache_status == CATALOG_STALE_FALLBACK
    assert result.stale is True
    assert result.snapshot is cached
    assert "ConnectError" in result.refresh_error
    assert store.saves == 0


def test_too_old_cache_does_not_hide_provider_failure():
    cached = SleeperPlayerCatalogSnapshot(
        fetched_at_ms=1_000_000,
        players={"1": {"full_name": "Ancient"}},
    )
    store = MemorySleeperPlayerCatalogStore(snapshot=cached)
    reader = FakeCatalogReader(error=RuntimeError("provider unavailable"))

    with pytest.raises(RuntimeError, match="provider unavailable"):
        load_sleeper_player_catalog(
            reader,
            store,
            now_ms=2_000_000,
            ttl_seconds=60,
            max_stale_seconds=300,
        )


def test_materially_future_cache_timestamp_fails_closed():
    store = MemorySleeperPlayerCatalogStore(
        snapshot=SleeperPlayerCatalogSnapshot(
            fetched_at_ms=2_000_000,
            players={"1": {"full_name": "Future"}},
        )
    )

    with pytest.raises(ValueError, match="future"):
        load_sleeper_player_catalog(
            FakeCatalogReader(),
            store,
            now_ms=1_000_000,
            ttl_seconds=60,
        )


def test_two_leagues_share_one_catalog_load_and_next_sync_hits_cache():
    league_reader = FakeLeagueReader({"a": _state("a"), "b": _state("b")})
    catalog_reader = FakeCatalogReader(
        payload={
            "1": {
                "full_name": "One",
                "position": "RB",
                "team": "IND",
                "yahoo_id": "101",
            }
        }
    )
    store = MemorySleeperPlayerCatalogStore()

    first = sync_sleeper_leagues_with_catalog(
        league_reader,
        catalog_reader,
        store,
        ("a", "b"),
        current_user_id="me",
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar(),
        now_ms=1_000_000,
        catalog_ttl_seconds=60,
    )
    second = sync_sleeper_leagues_with_catalog(
        league_reader,
        catalog_reader,
        store,
        ("a", "b"),
        current_user_id="me",
        ffverse_player_ids=_ffverse(),
        propwar_identity_crosswalk=_propwar(),
        now_ms=1_030_000,
        catalog_ttl_seconds=60,
    )

    assert first.catalog_cache_status == CATALOG_MISS
    assert second.catalog_cache_status == CATALOG_HIT
    assert first.sync_result.league_ids == ("a", "b")
    assert first.sync_result.all_role_join_ready is True
    assert catalog_reader.calls == 1
    assert league_reader.calls == [("a", "me"), ("b", "me"), ("a", "me"), ("b", "me")]
