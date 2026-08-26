from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

import httpx

from .sleeper import API_BASE

CATALOG_HIT = "HIT"
CATALOG_MISS = "MISS"
CATALOG_REFRESHED = "REFRESHED"
CATALOG_FORCED_REFRESH = "FORCED_REFRESH"
CATALOG_STALE_FALLBACK = "STALE_FALLBACK"

_MAX_CLOCK_SKEW_MS = 5 * 60 * 1000


class SleeperPlayerCatalogReader(Protocol):
    def fetch_nfl_players(self) -> Mapping[str, Mapping[str, Any]]: ...


class SleeperPlayerCatalogStore(Protocol):
    def load(self) -> "SleeperPlayerCatalogSnapshot | None": ...

    def save(self, snapshot: "SleeperPlayerCatalogSnapshot") -> None: ...


@dataclass(frozen=True)
class SleeperPlayerCatalogSnapshot:
    fetched_at_ms: int
    players: Mapping[str, Mapping[str, Any]]

    def age_seconds(self, now_ms: int) -> float:
        now_ms = _valid_timestamp(now_ms, "now_ms")
        fetched_at_ms = _valid_timestamp(self.fetched_at_ms, "fetched_at_ms")
        delta_ms = now_ms - fetched_at_ms
        if delta_ms < -_MAX_CLOCK_SKEW_MS:
            raise ValueError("Sleeper player catalog timestamp is materially in the future")
        return max(0.0, delta_ms / 1000.0)


@dataclass(frozen=True)
class SleeperPlayerCatalogLoadResult:
    snapshot: SleeperPlayerCatalogSnapshot
    cache_status: str
    age_seconds: float
    refresh_error: str | None = None

    @property
    def stale(self) -> bool:
        return self.cache_status == CATALOG_STALE_FALLBACK


@dataclass
class MemorySleeperPlayerCatalogStore:
    """Test/development store; persistent D1 implementation comes later."""

    snapshot: SleeperPlayerCatalogSnapshot | None = None
    saves: int = 0

    def load(self) -> SleeperPlayerCatalogSnapshot | None:
        return self.snapshot

    def save(self, snapshot: SleeperPlayerCatalogSnapshot) -> None:
        self.snapshot = snapshot
        self.saves += 1


class SleeperPlayerCatalogClient:
    """Read-only client for Sleeper's large NFL player metadata resource."""

    def __init__(
        self,
        *,
        base_url: str = API_BASE,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        normalized_base = base_url.rstrip("/") + "/"
        self._client = client or httpx.Client(
            base_url=normalized_base,
            timeout=timeout_seconds,
            headers={"Accept": "application/json", "User-Agent": "PropWar-FantasyHQ/1.0"},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "SleeperPlayerCatalogClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def fetch_nfl_players(self) -> Mapping[str, Mapping[str, Any]]:
        response = self._client.get("players/nfl")
        response.raise_for_status()
        return normalize_sleeper_player_catalog(response.json())


def _valid_timestamp(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a non-negative integer timestamp")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a non-negative integer timestamp") from None
    if result < 0:
        raise ValueError(f"{label} must be a non-negative integer timestamp")
    return result


def _valid_positive_seconds(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be positive")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be positive") from None
    if result <= 0:
        raise ValueError(f"{label} must be positive")
    return result


def normalize_sleeper_player_catalog(payload: Any) -> Mapping[str, Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        raise ValueError("Sleeper returned a malformed NFL player catalog")

    normalized: dict[str, Mapping[str, Any]] = {}
    for raw_player_id, raw_metadata in payload.items():
        player_id = str(raw_player_id or "").strip()
        if not player_id:
            continue
        if not isinstance(raw_metadata, Mapping):
            raise ValueError(f"Sleeper player catalog metadata is malformed for {player_id}")
        normalized[player_id] = dict(raw_metadata)
    return normalized


def load_sleeper_player_catalog(
    reader: SleeperPlayerCatalogReader,
    store: SleeperPlayerCatalogStore,
    *,
    now_ms: int,
    ttl_seconds: float = 24 * 60 * 60,
    max_stale_seconds: float = 7 * 24 * 60 * 60,
    force_refresh: bool = False,
) -> SleeperPlayerCatalogLoadResult:
    """Read through one shared catalog cache with an explicit bounded stale fallback."""

    now_ms = _valid_timestamp(now_ms, "now_ms")
    ttl_seconds = _valid_positive_seconds(ttl_seconds, "ttl_seconds")
    max_stale_seconds = _valid_positive_seconds(max_stale_seconds, "max_stale_seconds")
    if max_stale_seconds < ttl_seconds:
        raise ValueError("max_stale_seconds must be greater than or equal to ttl_seconds")

    cached = store.load()
    cached_age: float | None = None
    if cached is not None:
        cached_age = cached.age_seconds(now_ms)
        if not force_refresh and cached_age <= ttl_seconds:
            return SleeperPlayerCatalogLoadResult(
                snapshot=cached,
                cache_status=CATALOG_HIT,
                age_seconds=cached_age,
            )

    try:
        players = normalize_sleeper_player_catalog(reader.fetch_nfl_players())
    except Exception as exc:
        if cached is not None and cached_age is not None and cached_age <= max_stale_seconds:
            return SleeperPlayerCatalogLoadResult(
                snapshot=cached,
                cache_status=CATALOG_STALE_FALLBACK,
                age_seconds=cached_age,
                refresh_error=f"{type(exc).__name__}: {exc}",
            )
        raise

    snapshot = SleeperPlayerCatalogSnapshot(fetched_at_ms=now_ms, players=players)
    store.save(snapshot)
    if force_refresh:
        status = CATALOG_FORCED_REFRESH
    elif cached is None:
        status = CATALOG_MISS
    else:
        status = CATALOG_REFRESHED
    return SleeperPlayerCatalogLoadResult(
        snapshot=snapshot,
        cache_status=status,
        age_seconds=0.0,
    )
