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
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    @property
    def ready(self) -> bool:
        return bool(self.platform_draft_id and self.rounds and self.teams)


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
