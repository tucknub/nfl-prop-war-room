from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

import pandas as pd

from .catalog import (
    SleeperPlayerCatalogLoadResult,
    SleeperPlayerCatalogReader,
    SleeperPlayerCatalogStore,
    load_sleeper_player_catalog,
)
from .models import FantasyLeagueState
from .sync import SleeperSyncResult, build_sleeper_sync_result


class SleeperLeagueReader(Protocol):
    """Structural contract implemented by the read-only SleeperClient."""

    def fetch_normalized_league(
        self,
        league_id: str,
        *,
        current_user_id: str | None = None,
    ) -> FantasyLeagueState: ...


@dataclass(frozen=True)
class MultiSleeperSyncResult:
    """Read-only normalized state for multiple Sleeper leagues using shared references."""

    leagues: tuple[SleeperSyncResult, ...]

    @property
    def league_count(self) -> int:
        return len(self.leagues)

    @property
    def league_ids(self) -> tuple[str, ...]:
        return tuple(result.league_state.platform_league_id for result in self.leagues)

    @property
    def combined_player_ids(self) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for result in self.leagues:
            for player_id in result.identity_audit.player_ids:
                if player_id in seen:
                    continue
                seen.add(player_id)
                ordered.append(player_id)
        return tuple(ordered)

    @property
    def player_leagues(self) -> Mapping[str, tuple[str, ...]]:
        index: dict[str, list[str]] = {}
        for result in self.leagues:
            league_id = result.league_state.platform_league_id
            for player_id in result.identity_audit.player_ids:
                league_ids = index.setdefault(player_id, [])
                if league_id not in league_ids:
                    league_ids.append(league_id)
        return {player_id: tuple(league_ids) for player_id, league_ids in index.items()}

    @property
    def role_join_ready_leagues(self) -> tuple[str, ...]:
        return tuple(
            result.league_state.platform_league_id
            for result in self.leagues
            if result.role_join_ready
        )

    @property
    def leagues_needing_identity_attention(self) -> tuple[str, ...]:
        return tuple(
            result.league_state.platform_league_id
            for result in self.leagues
            if result.identity_status in {"PARTIAL", "NEEDS_REVIEW"}
        )

    @property
    def all_role_join_ready(self) -> bool:
        return bool(self.leagues) and all(result.role_join_ready for result in self.leagues)


@dataclass(frozen=True)
class CatalogBackedMultiSleeperSyncResult:
    """One shared player-catalog load plus the resulting multi-league sync."""

    sync_result: MultiSleeperSyncResult
    catalog_result: SleeperPlayerCatalogLoadResult

    @property
    def league_ids(self) -> tuple[str, ...]:
        return self.sync_result.league_ids

    @property
    def catalog_cache_status(self) -> str:
        return self.catalog_result.cache_status

    @property
    def catalog_age_seconds(self) -> float:
        return self.catalog_result.age_seconds

    @property
    def catalog_stale(self) -> bool:
        return self.catalog_result.stale


def _validated_league_ids(league_ids: Sequence[Any]) -> tuple[str, ...]:
    normalized = tuple(str(value or "").strip() for value in league_ids)
    if not normalized or any(not value for value in normalized):
        raise ValueError("At least one nonblank Sleeper league_id is required")
    if len(set(normalized)) != len(normalized):
        raise ValueError("Sleeper league_ids must be unique")
    return normalized


def sync_sleeper_league(
    reader: SleeperLeagueReader,
    league_id: str,
    *,
    current_user_id: str | None,
    ffverse_player_ids: pd.DataFrame,
    propwar_identity_crosswalk: pd.DataFrame,
    sleeper_player_map: Mapping[str, Mapping[str, Any]],
) -> SleeperSyncResult:
    """Fetch and audit one Sleeper league using caller-supplied shared references."""

    normalized_id = _validated_league_ids((league_id,))[0]
    state = reader.fetch_normalized_league(
        normalized_id,
        current_user_id=current_user_id,
    )
    return build_sleeper_sync_result(
        state,
        ffverse_player_ids=ffverse_player_ids,
        propwar_identity_crosswalk=propwar_identity_crosswalk,
        sleeper_player_map=sleeper_player_map,
    )


def sync_sleeper_leagues(
    reader: SleeperLeagueReader,
    league_ids: Sequence[Any],
    *,
    current_user_id: str | None,
    ffverse_player_ids: pd.DataFrame,
    propwar_identity_crosswalk: pd.DataFrame,
    sleeper_player_map: Mapping[str, Mapping[str, Any]],
) -> MultiSleeperSyncResult:
    """Sync multiple Sleeper leagues without reloading shared reference datasets.

    The caller owns refresh/caching policy for ffverse, PropWar identity data, and
    Sleeper's large NFL player map. This service never fetches `/players/nfl` on a
    per-league basis and never writes provider or persistence state.
    """

    normalized_ids = _validated_league_ids(league_ids)
    results = tuple(
        sync_sleeper_league(
            reader,
            league_id,
            current_user_id=current_user_id,
            ffverse_player_ids=ffverse_player_ids,
            propwar_identity_crosswalk=propwar_identity_crosswalk,
            sleeper_player_map=sleeper_player_map,
        )
        for league_id in normalized_ids
    )
    return MultiSleeperSyncResult(leagues=results)


def sync_sleeper_leagues_with_catalog(
    reader: SleeperLeagueReader,
    catalog_reader: SleeperPlayerCatalogReader,
    catalog_store: SleeperPlayerCatalogStore,
    league_ids: Sequence[Any],
    *,
    current_user_id: str | None,
    ffverse_player_ids: pd.DataFrame,
    propwar_identity_crosswalk: pd.DataFrame,
    now_ms: int,
    catalog_ttl_seconds: float = 24 * 60 * 60,
    catalog_max_stale_seconds: float = 7 * 24 * 60 * 60,
    force_catalog_refresh: bool = False,
) -> CatalogBackedMultiSleeperSyncResult:
    """Load the shared Sleeper catalog once, then sync every requested league."""

    normalized_ids = _validated_league_ids(league_ids)
    catalog_result = load_sleeper_player_catalog(
        catalog_reader,
        catalog_store,
        now_ms=now_ms,
        ttl_seconds=catalog_ttl_seconds,
        max_stale_seconds=catalog_max_stale_seconds,
        force_refresh=force_catalog_refresh,
    )
    sync_result = sync_sleeper_leagues(
        reader,
        normalized_ids,
        current_user_id=current_user_id,
        ffverse_player_ids=ffverse_player_ids,
        propwar_identity_crosswalk=propwar_identity_crosswalk,
        sleeper_player_map=catalog_result.snapshot.players,
    )
    return CatalogBackedMultiSleeperSyncResult(
        sync_result=sync_result,
        catalog_result=catalog_result,
    )
