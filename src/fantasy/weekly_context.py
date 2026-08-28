from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Sequence

from .models import LeagueTransaction, MatchupTeam
from .sleeper import SleeperClient


@dataclass(frozen=True)
class LeagueWeeklyContext:
    league_id: str
    matchups: tuple[MatchupTeam, ...]
    transactions: tuple[LeagueTransaction, ...]
    errors: tuple[str, ...]


def fetch_league_weekly_contexts(
    league_ids: Sequence[str],
    *,
    current_week: int,
    transaction_weeks: Sequence[int],
    max_workers: int = 3,
) -> tuple[LeagueWeeklyContext, ...]:
    """Fetch independent league weekly context concurrently, with bounded fan-out."""

    if isinstance(max_workers, bool) or not isinstance(max_workers, int):
        raise ValueError("max_workers must be a positive integer")
    if max_workers < 1 or max_workers > 8:
        raise ValueError("max_workers must be between 1 and 8")

    normalized_ids = tuple(
        str(league_id or "").strip()
        for league_id in league_ids
        if str(league_id or "").strip()
    )
    weeks = tuple(
        int(week)
        for week in transaction_weeks
        if not isinstance(week, bool) and int(week) >= 1
    )
    if not normalized_ids:
        return ()

    def fetch_one(league_id: str) -> LeagueWeeklyContext:
        matchups: tuple[MatchupTeam, ...] = ()
        transactions: list[LeagueTransaction] = []
        errors: list[str] = []

        with SleeperClient() as client:
            if current_week >= 1:
                try:
                    matchups = client.fetch_matchups(league_id, current_week)
                except Exception as exc:
                    errors.append(f"matchup: {exc}")

                for week in weeks:
                    try:
                        transactions.extend(
                            client.fetch_transactions(league_id, week)
                        )
                    except Exception as exc:
                        errors.append(f"Week {week} transactions: {exc}")

        return LeagueWeeklyContext(
            league_id=league_id,
            matchups=tuple(matchups),
            transactions=tuple(transactions),
            errors=tuple(errors),
        )

    if len(normalized_ids) == 1 or max_workers == 1:
        return tuple(fetch_one(league_id) for league_id in normalized_ids)

    worker_count = min(max_workers, len(normalized_ids))
    with ThreadPoolExecutor(
        max_workers=worker_count,
        thread_name_prefix="sleeper-weekly",
    ) as executor:
        return tuple(executor.map(fetch_one, normalized_ids))


__all__ = [
    "LeagueWeeklyContext",
    "fetch_league_weekly_contexts",
]
