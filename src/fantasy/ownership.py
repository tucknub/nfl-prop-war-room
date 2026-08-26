from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .identity import MATCHED
from .service import MultiSleeperSyncResult
from .sync import SleeperSyncResult

OWNED = "OWNED"
AVAILABLE = "AVAILABLE"
UNKNOWN_OWNERSHIP_NOT_READY = "UNKNOWN_OWNERSHIP_NOT_READY"
UNKNOWN_IDENTITY_GAPS = "UNKNOWN_IDENTITY_GAPS"

STARTER = "STARTER"
BENCH = "BENCH"
RESERVE = "RESERVE"
TAXI = "TAXI"
OTHER = "OTHER"


class UnsafeOwnershipState(ValueError):
    """Raised when normalized provider ownership contradicts itself."""


@dataclass(frozen=True)
class LeagueOwnership:
    platform: str
    platform_league_id: str
    propwar_entity_id: str
    status: str
    sleeper_player_id: str | None = None
    platform_roster_id: str | None = None
    platform_user_id: str | None = None
    roster_slot: str | None = None
    is_mine: bool = False
    reason_codes: tuple[str, ...] = ()

    @property
    def owned(self) -> bool:
        return self.status == OWNED

    @property
    def available(self) -> bool:
        return self.status == AVAILABLE

    @property
    def safe_for_waiver_logic(self) -> bool:
        return self.status in {OWNED, AVAILABLE}


@dataclass(frozen=True)
class MultiLeagueOwnershipIndex:
    """Provider-neutral canonical-player ownership across accepted Sleeper leagues."""

    sync_result: MultiSleeperSyncResult
    owned_by_entity: Mapping[str, tuple[LeagueOwnership, ...]]

    @property
    def league_ids(self) -> tuple[str, ...]:
        return self.sync_result.league_ids

    @property
    def entities_owned_by_me(self) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for league in self.sync_result.leagues:
            league_id = league.league_state.platform_league_id
            for entity_id, rows in self.owned_by_entity.items():
                if entity_id in seen:
                    continue
                if any(row.platform_league_id == league_id and row.is_mine for row in rows):
                    seen.add(entity_id)
                    ordered.append(entity_id)
        return tuple(ordered)

    def lookup(self, propwar_entity_id: str) -> tuple[LeagueOwnership, ...]:
        """Return one safe ownership/availability state for every synced league.

        `AVAILABLE` is emitted only when provider ownership is initialized and the
        league has complete canonical identity coverage. Otherwise absence from
        observed rosters remains unknown rather than becoming a false free agent.
        """

        entity_id = str(propwar_entity_id or "").strip()
        if not entity_id:
            raise ValueError("propwar_entity_id is required")

        owned_rows = {
            row.platform_league_id: row
            for row in self.owned_by_entity.get(entity_id, ())
        }
        results: list[LeagueOwnership] = []
        for league in self.sync_result.leagues:
            state = league.league_state
            league_id = state.platform_league_id
            owned = owned_rows.get(league_id)
            if owned is not None:
                results.append(owned)
                continue

            if not league.ownership_ready:
                results.append(
                    LeagueOwnership(
                        platform=state.platform,
                        platform_league_id=league_id,
                        propwar_entity_id=entity_id,
                        status=UNKNOWN_OWNERSHIP_NOT_READY,
                        reason_codes=("PROVIDER_OWNERSHIP_NOT_READY",),
                    )
                )
                continue

            if not league.role_join_ready:
                results.append(
                    LeagueOwnership(
                        platform=state.platform,
                        platform_league_id=league_id,
                        propwar_entity_id=entity_id,
                        status=UNKNOWN_IDENTITY_GAPS,
                        reason_codes=("LEAGUE_IDENTITY_COVERAGE_INCOMPLETE",),
                    )
                )
                continue

            results.append(
                LeagueOwnership(
                    platform=state.platform,
                    platform_league_id=league_id,
                    propwar_entity_id=entity_id,
                    status=AVAILABLE,
                    reason_codes=("COMPLETE_OWNERSHIP_AND_IDENTITY_ABSENCE",),
                )
            )
        return tuple(results)


def _roster_slot(roster, sleeper_player_id: str) -> str:
    if sleeper_player_id in roster.reserve:
        return RESERVE
    if sleeper_player_id in roster.taxi:
        return TAXI
    if sleeper_player_id in roster.starters:
        return STARTER
    if sleeper_player_id in roster.players:
        return BENCH
    return OTHER


def _resolution_map(league: SleeperSyncResult):
    return {row.sleeper_id: row for row in league.identity_audit.resolutions}


def _league_owned_rows(league: SleeperSyncResult) -> tuple[LeagueOwnership, ...]:
    state = league.league_state
    resolutions = _resolution_map(league)
    seen_provider_owners: dict[str, str] = {}
    rows: list[LeagueOwnership] = []

    for roster in state.rosters:
        roster_player_ids = tuple(
            dict.fromkeys((*roster.players, *roster.starters, *roster.reserve, *roster.taxi))
        )
        for sleeper_id in roster_player_ids:
            sleeper_id = str(sleeper_id or "").strip()
            if not sleeper_id or sleeper_id == "0":
                continue

            previous_roster = seen_provider_owners.get(sleeper_id)
            if previous_roster is not None and previous_roster != roster.platform_roster_id:
                raise UnsafeOwnershipState(
                    f"Sleeper player {sleeper_id} appears on multiple rosters in league "
                    f"{state.platform_league_id}: {previous_roster}, {roster.platform_roster_id}"
                )
            seen_provider_owners[sleeper_id] = roster.platform_roster_id

            resolution = resolutions.get(sleeper_id)
            if resolution is None or resolution.status != MATCHED or not resolution.propwar_entity_id:
                continue

            is_mine = bool(
                (state.current_platform_user_id and roster.platform_user_id == state.current_platform_user_id)
                or (
                    state.my_platform_roster_id
                    and roster.platform_roster_id == state.my_platform_roster_id
                )
            )
            rows.append(
                LeagueOwnership(
                    platform=state.platform,
                    platform_league_id=state.platform_league_id,
                    propwar_entity_id=resolution.propwar_entity_id,
                    status=OWNED,
                    sleeper_player_id=sleeper_id,
                    platform_roster_id=roster.platform_roster_id,
                    platform_user_id=roster.platform_user_id,
                    roster_slot=_roster_slot(roster, sleeper_id),
                    is_mine=is_mine,
                    reason_codes=("EXACT_CANONICAL_ROSTER_OWNERSHIP",),
                )
            )
    return tuple(rows)


def build_multi_league_ownership_index(
    sync_result: MultiSleeperSyncResult,
) -> MultiLeagueOwnershipIndex:
    """Build canonical ownership rows without making availability assumptions."""

    by_entity: dict[str, list[LeagueOwnership]] = {}
    for league in sync_result.leagues:
        for row in _league_owned_rows(league):
            current = by_entity.setdefault(row.propwar_entity_id, [])
            if any(existing.platform_league_id == row.platform_league_id for existing in current):
                raise UnsafeOwnershipState(
                    f"PropWar entity {row.propwar_entity_id} resolves to multiple owners in "
                    f"league {row.platform_league_id}"
                )
            current.append(row)

    return MultiLeagueOwnershipIndex(
        sync_result=sync_result,
        owned_by_entity={entity_id: tuple(rows) for entity_id, rows in by_entity.items()},
    )
