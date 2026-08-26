from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

import pandas as pd

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
