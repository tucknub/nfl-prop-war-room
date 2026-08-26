from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .models import DraftPick, FantasyLeagueState, WeeklyLeagueState


class UnsafeLeagueHistory(ValueError):
    """Raised when Sleeper renewal/history links contradict the accepted chain."""


class SleeperHistoryReader(Protocol):
    def fetch_normalized_league(
        self,
        league_id: str,
        *,
        current_user_id: str | None = None,
    ) -> FantasyLeagueState: ...

    def fetch_weekly_state(self, league_id: str, week: int) -> WeeklyLeagueState: ...

    def fetch_draft_picks(self, draft_id: str) -> tuple[DraftPick, ...]: ...


@dataclass(frozen=True)
class SleeperLeagueHistoryChain:
    """Current-to-oldest Sleeper renewal chain with season-specific rules preserved."""

    seasons: tuple[FantasyLeagueState, ...]
    truncated: bool = False
    next_previous_league_id: str | None = None

    @property
    def current(self) -> FantasyLeagueState:
        if not self.seasons:
            raise UnsafeLeagueHistory("Sleeper history chain is empty")
        return self.seasons[0]

    @property
    def league_ids(self) -> tuple[str, ...]:
        return tuple(state.platform_league_id for state in self.seasons)

    @property
    def season_labels(self) -> tuple[str, ...]:
        return tuple(state.season for state in self.seasons)

    @property
    def rules_fingerprints(self) -> Mapping[str, str]:
        return {state.season: state.rules_fingerprint for state in self.seasons}

    @property
    def manager_ids_by_season(self) -> Mapping[str, tuple[str, ...]]:
        return {
            state.season: tuple(manager.platform_user_id for manager in state.managers)
            for state in self.seasons
        }

    @property
    def stable_manager_ids(self) -> tuple[str, ...]:
        if not self.seasons:
            return ()
        first = [manager.platform_user_id for manager in self.seasons[0].managers]
        shared = set(first)
        for state in self.seasons[1:]:
            shared.intersection_update(manager.platform_user_id for manager in state.managers)
        return tuple(user_id for user_id in first if user_id in shared)


@dataclass(frozen=True)
class CompletedSleeperSeasonBackfill:
    league_state: FantasyLeagueState
    weekly_states: tuple[WeeklyLeagueState, ...]
    draft_picks: tuple[DraftPick, ...]

    @property
    def weeks_requested(self) -> tuple[int, ...]:
        return tuple(state.week for state in self.weekly_states)

    @property
    def matchup_weeks_with_rows(self) -> tuple[int, ...]:
        return tuple(state.week for state in self.weekly_states if state.matchups)

    @property
    def transaction_weeks_with_rows(self) -> tuple[int, ...]:
        return tuple(state.week for state in self.weekly_states if state.transactions)

    @property
    def matchup_row_count(self) -> int:
        return sum(len(state.matchups) for state in self.weekly_states)

    @property
    def transaction_count(self) -> int:
        return sum(len(state.transactions) for state in self.weekly_states)

    @property
    def draft_pick_count(self) -> int:
        return len(self.draft_picks)


@dataclass(frozen=True)
class SleeperHistoryBackfill:
    chain: SleeperLeagueHistoryChain
    completed_seasons: tuple[CompletedSleeperSeasonBackfill, ...]

    @property
    def completed_season_labels(self) -> tuple[str, ...]:
        return tuple(row.league_state.season for row in self.completed_seasons)

    @property
    def total_transactions(self) -> int:
        return sum(row.transaction_count for row in self.completed_seasons)

    @property
    def total_draft_picks(self) -> int:
        return sum(row.draft_pick_count for row in self.completed_seasons)


def _required_id(value: Any, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ValueError(f"{label} is required")
    return result


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a positive integer") from None
    if result < 1:
        raise ValueError(f"{label} must be a positive integer")
    return result


def _validated_weeks(weeks: Sequence[Any]) -> tuple[int, ...]:
    normalized = tuple(_positive_int(value, "week") for value in weeks)
    if not normalized:
        raise ValueError("At least one historical week is required")
    if len(set(normalized)) != len(normalized):
        raise ValueError("Historical weeks must be unique")
    return normalized


def _season_int(value: str) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def walk_sleeper_league_history(
    reader: SleeperHistoryReader,
    current_league_id: str,
    *,
    current_user_id: str | None,
    max_seasons: int = 10,
) -> SleeperLeagueHistoryChain:
    """Walk Sleeper `previous_league_id` without inheriting any prior rules."""

    league_id = _required_id(current_league_id, "current_league_id")
    max_seasons = _positive_int(max_seasons, "max_seasons")
    seen: set[str] = set()
    states: list[FantasyLeagueState] = []
    next_id: str | None = league_id

    while next_id is not None and len(states) < max_seasons:
        if next_id in seen:
            raise UnsafeLeagueHistory(f"Sleeper league history contains a cycle at {next_id}")
        seen.add(next_id)

        state = reader.fetch_normalized_league(next_id, current_user_id=current_user_id)
        if state.platform.upper() != "SLEEPER":
            raise UnsafeLeagueHistory("Sleeper history reader returned a non-SLEEPER league")
        if state.platform_league_id != next_id:
            raise UnsafeLeagueHistory(
                f"Sleeper history reader returned league {state.platform_league_id} for requested {next_id}"
            )

        if states:
            newer = _season_int(states[-1].season)
            older = _season_int(state.season)
            if newer is not None and older is not None and older >= newer:
                raise UnsafeLeagueHistory(
                    f"Sleeper previous league season {state.season} is not older than {states[-1].season}"
                )

        states.append(state)
        previous = str(state.previous_platform_league_id or "").strip()
        next_id = previous or None

    return SleeperLeagueHistoryChain(
        seasons=tuple(states),
        truncated=next_id is not None,
        next_previous_league_id=next_id,
    )


def backfill_completed_sleeper_season(
    reader: SleeperHistoryReader,
    state: FantasyLeagueState,
    *,
    weeks: Sequence[Any] = tuple(range(1, 19)),
) -> CompletedSleeperSeasonBackfill:
    """Fetch point-in-time provider history for one completed Sleeper season."""

    if state.platform.upper() != "SLEEPER":
        raise ValueError("Sleeper historical backfill requires a SLEEPER league")
    if state.status.strip().casefold() not in {"complete", "completed"}:
        raise ValueError("Historical weekly backfill requires a completed Sleeper season")

    normalized_weeks = _validated_weeks(weeks)
    weekly_rows: list[WeeklyLeagueState] = []
    for week in normalized_weeks:
        weekly = reader.fetch_weekly_state(state.platform_league_id, week)
        if weekly.platform.upper() != "SLEEPER":
            raise UnsafeLeagueHistory("Historical weekly reader returned a non-SLEEPER state")
        if weekly.platform_league_id != state.platform_league_id:
            raise UnsafeLeagueHistory("Historical weekly state belongs to a different league")
        if weekly.week != week:
            raise UnsafeLeagueHistory(
                f"Historical weekly reader returned Week {weekly.week} for requested Week {week}"
            )
        weekly_rows.append(weekly)

    draft_picks: tuple[DraftPick, ...] = ()
    if state.draft is not None and state.draft.platform_draft_id:
        draft_picks = tuple(reader.fetch_draft_picks(state.draft.platform_draft_id))
        if any(row.platform_draft_id != state.draft.platform_draft_id for row in draft_picks):
            raise UnsafeLeagueHistory("Historical draft picks belong to a different draft")

    return CompletedSleeperSeasonBackfill(
        league_state=state,
        weekly_states=tuple(weekly_rows),
        draft_picks=draft_picks,
    )


def backfill_sleeper_league_history(
    reader: SleeperHistoryReader,
    current_league_id: str,
    *,
    current_user_id: str | None,
    max_seasons: int = 10,
    weeks: Sequence[Any] = tuple(range(1, 19)),
) -> SleeperHistoryBackfill:
    """Walk a renewal chain and backfill only completed seasons in that chain."""

    chain = walk_sleeper_league_history(
        reader,
        current_league_id,
        current_user_id=current_user_id,
        max_seasons=max_seasons,
    )
    completed = tuple(
        backfill_completed_sleeper_season(reader, state, weeks=weeks)
        for state in chain.seasons
        if state.status.strip().casefold() in {"complete", "completed"}
    )
    return SleeperHistoryBackfill(chain=chain, completed_seasons=completed)
