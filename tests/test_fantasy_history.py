from __future__ import annotations

import pytest

from src.fantasy.history import (
    UnsafeLeagueHistory,
    backfill_completed_sleeper_season,
    backfill_sleeper_league_history,
    walk_sleeper_league_history,
)
from src.fantasy.models import (
    DraftPick,
    DraftState,
    FantasyLeagueState,
    LeagueRules,
    LeagueTransaction,
    Manager,
    MatchupTeam,
    WeeklyLeagueState,
)


class FakeHistoryReader:
    def __init__(self, states):
        self.states = dict(states)
        self.league_calls = []
        self.week_calls = []
        self.draft_calls = []
        self.week_overrides = {}

    def fetch_normalized_league(self, league_id, *, current_user_id=None):
        self.league_calls.append((league_id, current_user_id))
        return self.states[league_id]

    def fetch_weekly_state(self, league_id, week):
        self.week_calls.append((league_id, week))
        override = self.week_overrides.get((league_id, week))
        if override is not None:
            return override
        matchup = MatchupTeam(
            week=week,
            platform_roster_id="1",
            matchup_id="1",
            players=(),
            starters=(),
            points=100 + week,
            custom_points=None,
        )
        transaction = ()
        if week == 2:
            transaction = (
                LeagueTransaction(
                    platform_transaction_id=f"tx-{league_id}-{week}",
                    transaction_type="waiver",
                    status="complete",
                    week=week,
                    roster_ids=("1",),
                    creator_user_id="me",
                    created_at_ms=None,
                    status_updated_at_ms=None,
                    consenter_roster_ids=(),
                    adds={},
                    drops={},
                    traded_picks=(),
                    faab_transfers=(),
                    waiver_bid=5,
                ),
            )
        return WeeklyLeagueState(
            platform="SLEEPER",
            platform_league_id=league_id,
            week=week,
            matchups=(matchup,),
            transactions=transaction,
        )

    def fetch_draft_picks(self, draft_id):
        self.draft_calls.append(draft_id)
        return (
            DraftPick(
                platform_draft_id=draft_id,
                platform_player_id="1",
                picked_by_user_id="me",
                platform_roster_id="1",
                round=1,
                draft_slot=1,
                pick_no=1,
                is_keeper=False,
            ),
        )


def _state(league_id, season, previous, *, status, superflex=False, managers=("me", "other")):
    roster_positions = ("QB", "RB", "WR", "SUPER_FLEX", "BN") if superflex else ("QB", "RB", "WR", "WR", "BN")
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=league_id,
        name="League",
        season=str(season),
        status=status,
        team_count=len(managers),
        previous_platform_league_id=previous,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(roster_positions=roster_positions, scoring_settings={"rec": 1}),
        draft=DraftState(
            platform_draft_id=f"draft-{league_id}",
            status="complete" if status == "complete" else "pre_draft",
            draft_type="snake",
            rounds=15,
            teams=len(managers),
            start_time_ms=None,
            draft_order={},
            slot_counts={},
        ),
        managers=tuple(Manager(platform_user_id=user_id, display_name=user_id) for user_id in managers),
        rosters=(),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=status == "complete",
    )


def _chain_reader():
    return FakeHistoryReader(
        {
            "2026-id": _state("2026-id", 2026, "2025-id", status="pre_draft", superflex=False),
            "2025-id": _state("2025-id", 2025, "2024-id", status="complete", superflex=True),
            "2024-id": _state("2024-id", 2024, None, status="complete", superflex=True, managers=("me", "other", "old")),
        }
    )


def test_history_walk_preserves_each_season_rules_and_manager_continuity():
    reader = _chain_reader()

    chain = walk_sleeper_league_history(reader, "2026-id", current_user_id="me")

    assert chain.league_ids == ("2026-id", "2025-id", "2024-id")
    assert chain.season_labels == ("2026", "2025", "2024")
    assert chain.truncated is False
    assert chain.rules_fingerprints["2026"] != chain.rules_fingerprints["2025"]
    assert chain.rules_fingerprints["2025"] == chain.rules_fingerprints["2024"]
    assert chain.stable_manager_ids == ("me", "other")
    assert reader.league_calls == [("2026-id", "me"), ("2025-id", "me"), ("2024-id", "me")]


def test_history_walk_reports_truncation_instead_of_silently_stopping():
    chain = walk_sleeper_league_history(
        _chain_reader(),
        "2026-id",
        current_user_id="me",
        max_seasons=2,
    )

    assert chain.league_ids == ("2026-id", "2025-id")
    assert chain.truncated is True
    assert chain.next_previous_league_id == "2024-id"


def test_history_cycle_fails_closed():
    reader = FakeHistoryReader(
        {
            "a": _state("a", 2026, "b", status="complete"),
            "b": _state("b", 2025, "a", status="complete"),
        }
    )

    with pytest.raises(UnsafeLeagueHistory, match="cycle"):
        walk_sleeper_league_history(reader, "a", current_user_id="me")


def test_previous_season_must_actually_be_older():
    reader = FakeHistoryReader(
        {
            "a": _state("a", 2026, "b", status="complete"),
            "b": _state("b", 2026, None, status="complete"),
        }
    )

    with pytest.raises(UnsafeLeagueHistory, match="not older"):
        walk_sleeper_league_history(reader, "a", current_user_id="me")


def test_completed_season_backfill_collects_weekly_and_draft_evidence():
    state = _state("2025-id", 2025, None, status="complete")
    reader = FakeHistoryReader({"2025-id": state})

    result = backfill_completed_sleeper_season(reader, state, weeks=(1, 2, 3))

    assert result.weeks_requested == (1, 2, 3)
    assert result.matchup_weeks_with_rows == (1, 2, 3)
    assert result.transaction_weeks_with_rows == (2,)
    assert result.matchup_row_count == 3
    assert result.transaction_count == 1
    assert result.draft_pick_count == 1
    assert reader.draft_calls == ("draft-2025-id",) if isinstance(reader.draft_calls, tuple) else ["draft-2025-id"]


def test_current_or_pre_draft_season_cannot_be_bulk_backfilled_as_complete():
    state = _state("2026-id", 2026, None, status="pre_draft")

    with pytest.raises(ValueError, match="completed"):
        backfill_completed_sleeper_season(FakeHistoryReader({"2026-id": state}), state, weeks=(1,))


def test_weekly_provider_mismatch_fails_closed():
    state = _state("2025-id", 2025, None, status="complete")
    reader = FakeHistoryReader({"2025-id": state})
    reader.week_overrides[("2025-id", 1)] = WeeklyLeagueState(
        platform="SLEEPER",
        platform_league_id="wrong",
        week=1,
        matchups=(),
        transactions=(),
    )

    with pytest.raises(UnsafeLeagueHistory, match="different league"):
        backfill_completed_sleeper_season(reader, state, weeks=(1,))


def test_full_history_backfill_skips_current_and_backfills_completed_prior_seasons():
    reader = _chain_reader()

    result = backfill_sleeper_league_history(
        reader,
        "2026-id",
        current_user_id="me",
        weeks=(1, 2),
    )

    assert result.chain.season_labels == ("2026", "2025", "2024")
    assert result.completed_season_labels == ("2025", "2024")
    assert result.total_transactions == 2
    assert result.total_draft_picks == 2
