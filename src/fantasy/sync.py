from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import pandas as pd

from .identity import (
    MATCHED,
    NEEDS_REVIEW,
    PRE_GSIS,
    TEAM_DEFENSE,
    UNRESOLVED,
    SleeperIdentityResolution,
    extract_propwar_player_ids,
    resolve_sleeper_players,
)
from .models import FantasyLeagueState


_AUDIT_STATUSES = (MATCHED, PRE_GSIS, NEEDS_REVIEW, UNRESOLVED, TEAM_DEFENSE)
_IGNORED_PLAYER_IDS = {"", "0", "none", "null", "nan"}


@dataclass(frozen=True)
class FantasyIdentityAudit:
    """Read-only identity coverage for the players observed in one fantasy league."""

    platform: str
    platform_league_id: str
    season: str
    player_ids: tuple[str, ...]
    resolutions: tuple[SleeperIdentityResolution, ...]

    def count(self, status: str) -> int:
        return sum(result.status == status for result in self.resolutions)

    @property
    def total_players(self) -> int:
        return len(self.player_ids)

    @property
    def matched_players(self) -> int:
        return self.count(MATCHED)

    @property
    def pre_gsis_players(self) -> int:
        return self.count(PRE_GSIS)

    @property
    def needs_review_players(self) -> int:
        return self.count(NEEDS_REVIEW)

    @property
    def unresolved_players(self) -> int:
        return self.count(UNRESOLVED)

    @property
    def team_defenses(self) -> int:
        return self.count(TEAM_DEFENSE)

    @property
    def unlinked_player_ids(self) -> tuple[str, ...]:
        return tuple(
            row.sleeper_id
            for row in self.resolutions
            if row.status not in {MATCHED, TEAM_DEFENSE}
        )

    @property
    def role_join_ready(self) -> bool:
        """True only when every non-defense observed player has a PropWar entity."""

        return self.total_players > 0 and not self.unlinked_player_ids

    @property
    def status(self) -> str:
        if not self.total_players:
            return "NO_PLAYERS"
        if self.needs_review_players or self.unresolved_players:
            return "NEEDS_REVIEW"
        if self.pre_gsis_players:
            return "PARTIAL"
        return "READY"

    @property
    def counts(self) -> Mapping[str, int]:
        return {status: self.count(status) for status in _AUDIT_STATUSES}


@dataclass(frozen=True)
class SleeperSyncResult:
    """Normalized Sleeper league state paired with its identity coverage audit."""

    league_state: FantasyLeagueState
    identity_audit: FantasyIdentityAudit
    player_metadata_entries_used: int

    @property
    def ownership_ready(self) -> bool:
        return self.league_state.ownership_ready

    @property
    def identity_status(self) -> str:
        return self.identity_audit.status

    @property
    def role_join_ready(self) -> bool:
        return self.identity_audit.role_join_ready


def _clean_player_id(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if text.casefold() in _IGNORED_PLAYER_IDS:
        return None
    return text


def _ordered_unique(values: Iterable[Any]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        player_id = _clean_player_id(value)
        if not player_id or player_id in seen:
            continue
        seen.add(player_id)
        ordered.append(player_id)
    return tuple(ordered)


def collect_league_player_ids(state: FantasyLeagueState) -> tuple[str, ...]:
    """Collect every actual Sleeper player ID present in normalized roster state.

    Roster `players` is authoritative when populated, but starters/reserve/taxi are
    also included defensively because provider payloads can transiently differ.
    Sleeper's pre-draft starter placeholder `0` is explicitly ignored.
    """

    values: list[str] = []
    for roster in state.rosters:
        values.extend(roster.players)
        values.extend(roster.starters)
        values.extend(roster.reserve)
        values.extend(roster.taxi)
    return _ordered_unique(values)


def build_sleeper_identity_audit(
    state: FantasyLeagueState,
    *,
    ffverse_player_ids: pd.DataFrame,
    propwar_identity_crosswalk: pd.DataFrame,
    sleeper_player_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> FantasyIdentityAudit:
    """Resolve all observed Sleeper roster IDs without writing identity state."""

    if state.platform.upper() != "SLEEPER":
        raise ValueError("Sleeper identity audit requires a SLEEPER league state")

    player_ids = collect_league_player_ids(state)
    trusted_propwar_ids = extract_propwar_player_ids(propwar_identity_crosswalk)
    resolutions = resolve_sleeper_players(
        player_ids,
        ffverse_player_ids=ffverse_player_ids,
        propwar_player_ids=trusted_propwar_ids,
        sleeper_player_map=sleeper_player_map,
    ) if player_ids else ()

    return FantasyIdentityAudit(
        platform=state.platform,
        platform_league_id=state.platform_league_id,
        season=state.season,
        player_ids=player_ids,
        resolutions=resolutions,
    )


def build_sleeper_sync_result(
    state: FantasyLeagueState,
    *,
    ffverse_player_ids: pd.DataFrame,
    propwar_identity_crosswalk: pd.DataFrame,
    sleeper_player_map: Mapping[str, Mapping[str, Any]] | None = None,
) -> SleeperSyncResult:
    """Pair normalized league state with exact identity coverage.

    This function is intentionally pure with respect to persistence. It does not
    create PropWar entities, write D1 rows, mutate provider state, or fetch the
    large Sleeper player map on its own.
    """

    audit = build_sleeper_identity_audit(
        state,
        ffverse_player_ids=ffverse_player_ids,
        propwar_identity_crosswalk=propwar_identity_crosswalk,
        sleeper_player_map=sleeper_player_map,
    )
    player_map = sleeper_player_map or {}
    metadata_entries_used = sum(player_id in player_map for player_id in audit.player_ids)
    return SleeperSyncResult(
        league_state=state,
        identity_audit=audit,
        player_metadata_entries_used=metadata_entries_used,
    )
