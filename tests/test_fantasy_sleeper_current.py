from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import httpx
import pytest

from src.fantasy.changes import FantasySnapshot
from src.fantasy.models import (
    FantasyLeagueState,
    LeagueRules,
    LeagueTransaction,
    Roster,
)
from src.fantasy.sleeper import SleeperClient
from src.fantasy.sleeper_current import (
    SleeperNflState,
    UnsafeSleeperCurrentSnapshot,
    build_current_sleeper_snapshot,
    fantasy_regular_week,
    normalize_sleeper_nfl_state,
)


def _league(
    *,
    ownership_ready: bool,
    league_id: str = "league-2026",
    season: str = "2026",
) -> FantasyLeagueState:
    players = ("p1",) if ownership_ready else ()
    starters = ("p1",) if ownership_ready else ("0",)
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=league_id,
        name="Test League",
        season=season,
        status="in_season" if ownership_ready else "pre_draft",
        team_count=10,
        previous_platform_league_id="league-2025",
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "BN"),
            scoring_settings={"rec": 1},
            waiver_budget=100,
        ),
        draft=None,
        managers=(),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=players,
                starters=starters,
                reserve=(),
                taxi=(),
                settings={},
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def _tx(
    transaction_id: str,
    week: int,
    *,
    roster: str = "1",
    created_at_ms: int | None = None,
) -> LeagueTransaction:
    return LeagueTransaction(
        platform_transaction_id=transaction_id,
        transaction_type="free_agent",
        status="complete",
        week=week,
        roster_ids=(roster,),
        creator_user_id="me",
        created_at_ms=created_at_ms if created_at_ms is not None else week * 100,
        status_updated_at_ms=week * 100 + 1,
        consenter_roster_ids=(roster,),
        adds={f"add-{transaction_id}": roster},
        drops={},
        traded_picks=(),
        faab_transfers=(),
        waiver_bid=None,
        metadata={},
    )


def _nfl_state(*, leg: int = 4, season: str = "2026") -> SleeperNflState:
    return SleeperNflState(
        season=season,
        league_season=season,
        season_type="regular",
        week=leg,
        leg=leg,
        display_week=leg,
        season_start_date="2026-09-10",
        previous_season="2025",
        league_create_season=season,
    )


@dataclass
class FakeReader:
    state: FantasyLeagueState
    transactions: Mapping[int, tuple[LeagueTransaction, ...]] = field(default_factory=dict)
    league_calls: list[str] = field(default_factory=list)
    transaction_calls: list[int] = field(default_factory=list)

    def fetch_normalized_league(
        self,
        league_id: str,
        *,
        current_user_id: str | None = None,
    ) -> FantasyLeagueState:
        self.league_calls.append(league_id)
        return self.state

    def fetch_transactions(
        self,
        league_id: str,
        week: int,
    ) -> tuple[LeagueTransaction, ...]:
        self.transaction_calls.append(week)
        return self.transactions.get(week, ())


def test_normalize_nfl_state_and_client_use_public_state_endpoint():
    payload = {
        "week": 3,
        "season_type": "regular",
        "season_start_date": "2026-09-10",
        "season": "2026",
        "previous_season": "2025",
        "leg": 3,
        "league_season": "2026",
        "league_create_season": "2026",
        "display_week": 3,
    }
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=payload)

    http = httpx.Client(
        base_url="https://api.sleeper.app/v1/",
        transport=httpx.MockTransport(handler),
    )
    client = SleeperClient(client=http)
    state = client.fetch_nfl_state()

    assert state == normalize_sleeper_nfl_state(payload)
    assert state.leg == 3
    assert seen == ["/v1/state/nfl"]


def test_fantasy_regular_week_ignores_preseason_display_week():
    preseason = SleeperNflState(
        season="2026",
        league_season="2026",
        season_type="pre",
        week=3,
        leg=0,
        display_week=3,
        season_start_date="2026-09-10",
        previous_season="2025",
        league_create_season="2026",
    )
    regular = SleeperNflState(
        season="2026",
        league_season="2026",
        season_type="regular",
        week=99,
        leg=1,
        display_week=99,
        season_start_date="2026-09-10",
        previous_season="2025",
        league_create_season="2026",
    )

    assert fantasy_regular_week(preseason) == 0
    assert fantasy_regular_week(regular) == 1


def test_pre_draft_snapshot_fetches_no_transaction_rounds():
    reader = FakeReader(_league(ownership_ready=False))
    result = build_current_sleeper_snapshot(
        reader,
        "league-2026",
        snapshot_id="snap-pre",
        current_user_id="me",
        nfl_state=_nfl_state(),
    )

    assert result.snapshot.league.ownership_ready is False
    assert result.snapshot.transactions == ()
    assert result.transaction_rounds == ()
    assert result.current_transaction_round is None
    assert result.source_metadata["transaction_round"] is None
    assert reader.transaction_calls == []


def test_initial_ownership_ready_baseline_fetches_only_current_leg():
    reader = FakeReader(
        _league(ownership_ready=True),
        {4: (_tx("tx-4", 4),)},
    )
    result = build_current_sleeper_snapshot(
        reader,
        "league-2026",
        snapshot_id="snap-first",
        current_user_id="me",
        nfl_state=_nfl_state(leg=4),
    )

    assert result.transaction_rounds == (4,)
    assert tuple(tx.platform_transaction_id for tx in result.snapshot.transactions) == ("tx-4",)
    assert reader.transaction_calls == [4]


def test_first_ownership_initialization_after_pre_draft_starts_at_current_leg():
    previous = FantasySnapshot("snap-pre", _league(ownership_ready=False))
    reader = FakeReader(_league(ownership_ready=True))

    result = build_current_sleeper_snapshot(
        reader,
        "league-2026",
        snapshot_id="snap-drafted",
        current_user_id="me",
        nfl_state=_nfl_state(leg=2),
        previous_snapshot=previous,
    )

    assert result.transaction_rounds == (2,)
    assert reader.transaction_calls == [2]


def test_explicit_prior_round_catches_up_with_one_round_overlap():
    previous = FantasySnapshot(
        "snap-old",
        _league(ownership_ready=True),
        transactions=(_tx("old-2", 2),),
    )
    duplicate = _tx("same", 3)
    reader = FakeReader(
        _league(ownership_ready=True),
        {
            2: (_tx("old-2", 2),),
            3: (duplicate,),
            4: (duplicate, _tx("new-4", 4)),
        },
    )

    result = build_current_sleeper_snapshot(
        reader,
        "league-2026",
        snapshot_id="snap-new",
        current_user_id="me",
        nfl_state=_nfl_state(leg=4),
        previous_snapshot=previous,
        previous_transaction_round=2,
    )

    assert result.transaction_rounds == (2, 3, 4)
    assert reader.transaction_calls == [2, 3, 4]
    assert tuple(tx.platform_transaction_id for tx in result.snapshot.transactions) == (
        "old-2",
        "same",
        "new-4",
    )
    assert result.source_metadata["transaction_round"] == 4
    assert result.source_metadata["transaction_rounds_fetched"] == [2, 3, 4]


def test_prior_round_can_be_inferred_from_existing_transaction_week():
    previous = FantasySnapshot(
        "snap-old",
        _league(ownership_ready=True),
        transactions=(_tx("tx-3", 3),),
    )
    reader = FakeReader(_league(ownership_ready=True))

    result = build_current_sleeper_snapshot(
        reader,
        "league-2026",
        snapshot_id="snap-new",
        current_user_id="me",
        nfl_state=_nfl_state(leg=4),
        previous_snapshot=previous,
    )

    assert result.transaction_rounds == (3, 4)
    assert reader.transaction_calls == [3, 4]


def test_quiet_prior_snapshot_requires_persisted_round_metadata():
    previous = FantasySnapshot("snap-old", _league(ownership_ready=True))
    reader = FakeReader(_league(ownership_ready=True))

    with pytest.raises(
        UnsafeSleeperCurrentSnapshot,
        match="previous_transaction_round is required",
    ):
        build_current_sleeper_snapshot(
            reader,
            "league-2026",
            snapshot_id="snap-new",
            current_user_id="me",
            nfl_state=_nfl_state(leg=4),
            previous_snapshot=previous,
        )

    assert reader.transaction_calls == []


def test_season_and_previous_identity_mismatches_fail_before_transaction_fetch():
    reader = FakeReader(_league(ownership_ready=True))
    with pytest.raises(UnsafeSleeperCurrentSnapshot, match="league season"):
        build_current_sleeper_snapshot(
            reader,
            "league-2026",
            snapshot_id="snap-new",
            current_user_id="me",
            nfl_state=_nfl_state(season="2027"),
        )
    assert reader.transaction_calls == []

    foreign = FantasySnapshot(
        "snap-foreign",
        _league(ownership_ready=True, league_id="different"),
    )
    with pytest.raises(UnsafeSleeperCurrentSnapshot, match="different league or season"):
        build_current_sleeper_snapshot(
            reader,
            "league-2026",
            snapshot_id="snap-new",
            current_user_id="me",
            nfl_state=_nfl_state(),
            previous_snapshot=foreign,
            previous_transaction_round=3,
        )
    assert reader.transaction_calls == []


def test_invalid_or_regressed_transaction_round_fails_closed():
    reader = FakeReader(_league(ownership_ready=True))
    previous = FantasySnapshot(
        "snap-old",
        _league(ownership_ready=True),
        transactions=(_tx("tx-5", 5),),
    )

    with pytest.raises(UnsafeSleeperCurrentSnapshot, match="cannot exceed"):
        build_current_sleeper_snapshot(
            reader,
            "league-2026",
            snapshot_id="snap-new",
            current_user_id="me",
            nfl_state=_nfl_state(leg=4),
            previous_snapshot=previous,
            previous_transaction_round=5,
        )

    with pytest.raises(UnsafeSleeperCurrentSnapshot, match="leg 1-18"):
        build_current_sleeper_snapshot(
            reader,
            "league-2026",
            snapshot_id="snap-new",
            current_user_id="me",
            nfl_state=_nfl_state(leg=0),
        )


def test_conflicting_duplicate_transaction_rows_fail_closed():
    previous = FantasySnapshot(
        "snap-old",
        _league(ownership_ready=True),
        transactions=(_tx("old", 2),),
    )
    reader = FakeReader(
        _league(ownership_ready=True),
        {
            2: (_tx("same", 2, roster="1"),),
            3: (_tx("same", 3, roster="2"),),
        },
    )

    with pytest.raises(
        UnsafeSleeperCurrentSnapshot,
        match="conflicting rows",
    ):
        build_current_sleeper_snapshot(
            reader,
            "league-2026",
            snapshot_id="snap-new",
            current_user_id="me",
            nfl_state=_nfl_state(leg=3),
            previous_snapshot=previous,
            previous_transaction_round=2,
        )


def test_malformed_nfl_state_fails_closed():
    with pytest.raises(UnsafeSleeperCurrentSnapshot):
        normalize_sleeper_nfl_state([])
    with pytest.raises(UnsafeSleeperCurrentSnapshot, match="non-negative integer"):
        normalize_sleeper_nfl_state(
            {
                "season": "2026",
                "league_season": "2026",
                "season_type": "regular",
                "week": "4",
                "leg": 4,
            }
        )


def test_public_package_exports_current_snapshot_contract():
    import src.fantasy as fantasy

    assert fantasy.SleeperNflState is SleeperNflState
    assert fantasy.UnsafeSleeperCurrentSnapshot is UnsafeSleeperCurrentSnapshot
    assert fantasy.build_current_sleeper_snapshot is build_current_sleeper_snapshot
