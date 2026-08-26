from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any, Mapping

NON_STARTER_SLOTS = {"BN", "IR", "TAXI"}


@dataclass(frozen=True)
class LeagueRules:
    roster_positions: tuple[str, ...]
    scoring_settings: Mapping[str, Any]
    waiver_budget: int | None = None
    max_keepers: int | None = None
    playoff_teams: int | None = None
    playoff_week_start: int | None = None
    trade_deadline: int | None = None
    reserve_slots: int = 0
    taxi_slots: int = 0
    position_limits: Mapping[str, int] = field(default_factory=dict)
    rule_settings: Mapping[str, Any] = field(default_factory=dict)
    raw_settings: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def starter_positions(self) -> tuple[str, ...]:
        return tuple(slot for slot in self.roster_positions if slot not in NON_STARTER_SLOTS)

    @property
    def rules_fingerprint(self) -> str:
        payload = {
            "roster_positions": list(self.roster_positions),
            "scoring_settings": dict(sorted(self.scoring_settings.items())),
            "waiver_budget": self.waiver_budget,
            "max_keepers": self.max_keepers,
            "playoff_teams": self.playoff_teams,
            "playoff_week_start": self.playoff_week_start,
            "trade_deadline": self.trade_deadline,
            "reserve_slots": self.reserve_slots,
            "taxi_slots": self.taxi_slots,
            "position_limits": dict(sorted(self.position_limits.items())),
            "rule_settings": dict(sorted(self.rule_settings.items())),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DraftState:
    platform_draft_id: str
    status: str
    draft_type: str | None
    rounds: int | None
    teams: int | None
    start_time_ms: int | None
    draft_order: Mapping[str, int]
    slot_counts: Mapping[str, int]
    position_limits: Mapping[str, int] = field(default_factory=dict)
    enforce_position_limits: bool = False
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def ready(self) -> bool:
        return bool(self.platform_draft_id and self.rounds and self.teams)


@dataclass(frozen=True)
class DraftPick:
    platform_draft_id: str
    platform_player_id: str
    picked_by_user_id: str | None
    platform_roster_id: str | None
    round: int | None
    draft_slot: int | None
    pick_no: int | None
    is_keeper: bool | None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class Manager:
    platform_user_id: str
    display_name: str
    team_name: str | None = None
    is_owner: bool = False


@dataclass(frozen=True)
class Roster:
    platform_roster_id: str
    platform_user_id: str | None
    players: tuple[str, ...]
    starters: tuple[str, ...]
    reserve: tuple[str, ...]
    taxi: tuple[str, ...]
    settings: Mapping[str, Any] = field(default_factory=dict)

    @property
    def has_players(self) -> bool:
        return bool(self.players)


@dataclass(frozen=True)
class MatchupTeam:
    week: int
    platform_roster_id: str
    matchup_id: str | None
    players: tuple[str, ...]
    starters: tuple[str, ...]
    points: int | float | None
    custom_points: int | float | None
    players_points: Mapping[str, Any] = field(default_factory=dict)
    starters_points: tuple[Any, ...] = ()
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class TradedPick:
    season: str
    round: int | None
    original_roster_id: str | None
    previous_owner_roster_id: str | None
    owner_roster_id: str | None


@dataclass(frozen=True)
class FaabTransfer:
    sender_roster_id: str | None
    receiver_roster_id: str | None
    amount: int | float | None


@dataclass(frozen=True)
class LeagueTransaction:
    platform_transaction_id: str
    transaction_type: str
    status: str
    week: int | None
    roster_ids: tuple[str, ...]
    creator_user_id: str | None
    created_at_ms: int | None
    status_updated_at_ms: int | None
    consenter_roster_ids: tuple[str, ...]
    adds: Mapping[str, str]
    drops: Mapping[str, str]
    traded_picks: tuple[TradedPick, ...]
    faab_transfers: tuple[FaabTransfer, ...]
    waiver_bid: int | float | None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True)
class WeeklyLeagueState:
    platform: str
    platform_league_id: str
    week: int
    matchups: tuple[MatchupTeam, ...]
    transactions: tuple[LeagueTransaction, ...]


@dataclass(frozen=True)
class FantasyLeagueState:
    platform: str
    platform_league_id: str
    name: str
    season: str
    status: str
    team_count: int
    previous_platform_league_id: str | None
    current_platform_user_id: str | None
    my_platform_roster_id: str | None
    rules: LeagueRules
    draft: DraftState | None
    managers: tuple[Manager, ...]
    rosters: tuple[Roster, ...]
    rules_ready: bool
    draft_ready: bool
    ownership_ready: bool

    @property
    def rules_fingerprint(self) -> str:
        return self.rules.rules_fingerprint
