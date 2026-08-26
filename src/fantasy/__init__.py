"""Fantasy League HQ provider-normalization and change-detection foundation."""

from .changes import (
    FantasyChangeEvent,
    FantasySnapshot,
    UnsafeSnapshotTransition,
    derive_fantasy_change_events,
)
from .models import (
    DraftPick,
    DraftState,
    FaabTransfer,
    FantasyLeagueState,
    LeagueRules,
    LeagueTransaction,
    Manager,
    MatchupTeam,
    Roster,
    TradedPick,
    WeeklyLeagueState,
)
from .sleeper import (
    SleeperClient,
    SleeperLeagueBundle,
    normalize_sleeper_bundle,
    normalize_sleeper_draft_picks,
    normalize_sleeper_matchups,
    normalize_sleeper_transactions,
)

__all__ = [
    "DraftPick",
    "DraftState",
    "FaabTransfer",
    "FantasyChangeEvent",
    "FantasyLeagueState",
    "FantasySnapshot",
    "LeagueRules",
    "LeagueTransaction",
    "Manager",
    "MatchupTeam",
    "Roster",
    "SleeperClient",
    "SleeperLeagueBundle",
    "TradedPick",
    "UnsafeSnapshotTransition",
    "WeeklyLeagueState",
    "derive_fantasy_change_events",
    "normalize_sleeper_bundle",
    "normalize_sleeper_draft_picks",
    "normalize_sleeper_matchups",
    "normalize_sleeper_transactions",
]
