from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .live_ownership import LiveCrossLeaguePlayer, my_players_available_elsewhere
from .models import FantasyLeagueState
from .roster_health import (
    NEEDS_ATTENTION,
    PRE_DRAFT,
    READY,
    WATCH,
    RosterHealthIssue,
    RosterHealthSummary,
    analyze_roster_health,
)


_STATUS_ORDER = {
    NEEDS_ATTENTION: 0,
    WATCH: 1,
    READY: 2,
    PRE_DRAFT: 3,
}


@dataclass(frozen=True)
class FantasyLeagueActionSummary:
    platform_league_id: str
    league_name: str
    health: RosterHealthSummary

    @property
    def status(self) -> str:
        return self.health.status

    @property
    def drafted(self) -> bool:
        return self.health.status != PRE_DRAFT

    @property
    def needs_attention(self) -> bool:
        return self.health.status == NEEDS_ATTENTION

    @property
    def watch(self) -> bool:
        return self.health.status == WATCH

    @property
    def top_issues(self) -> tuple[RosterHealthIssue, ...]:
        return self.health.issues[:3]


@dataclass(frozen=True)
class FantasyActionCenter:
    leagues: tuple[FantasyLeagueActionSummary, ...]
    cross_league_opportunities: tuple[LiveCrossLeaguePlayer, ...]

    @property
    def league_count(self) -> int:
        return len(self.leagues)

    @property
    def drafted_count(self) -> int:
        return sum(1 for row in self.leagues if row.drafted)

    @property
    def pre_draft_count(self) -> int:
        return sum(1 for row in self.leagues if row.status == PRE_DRAFT)

    @property
    def ready_count(self) -> int:
        return sum(1 for row in self.leagues if row.status == READY)

    @property
    def watch_count(self) -> int:
        return sum(1 for row in self.leagues if row.status == WATCH)

    @property
    def needs_attention_count(self) -> int:
        return sum(1 for row in self.leagues if row.status == NEEDS_ATTENTION)

    @property
    def opportunity_count(self) -> int:
        return len(self.cross_league_opportunities)

    @property
    def action_leagues(self) -> tuple[FantasyLeagueActionSummary, ...]:
        return tuple(
            row
            for row in self.leagues
            if row.status in {NEEDS_ATTENTION, WATCH}
        )


def build_fantasy_action_center(
    leagues: Iterable[FantasyLeagueState],
    player_catalog: Mapping[str, Mapping[str, Any]],
) -> FantasyActionCenter:
    league_rows = tuple(leagues)
    summaries = [
        FantasyLeagueActionSummary(
            platform_league_id=league.platform_league_id,
            league_name=league.name or league.platform_league_id,
            health=analyze_roster_health(league, player_catalog),
        )
        for league in league_rows
    ]
    summaries.sort(
        key=lambda row: (
            _STATUS_ORDER.get(row.status, 99),
            row.league_name.casefold(),
            row.platform_league_id,
        )
    )
    return FantasyActionCenter(
        leagues=tuple(summaries),
        cross_league_opportunities=my_players_available_elsewhere(league_rows),
    )
