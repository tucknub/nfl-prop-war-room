from __future__ import annotations

import pytest

from src.fantasy.identity import MATCHED, PRE_GSIS, SleeperIdentityResolution
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.ownership import (
    AVAILABLE,
    BENCH,
    OWNED,
    RESERVE,
    STARTER,
    TAXI,
    UNKNOWN_IDENTITY_GAPS,
    UNKNOWN_OWNERSHIP_NOT_READY,
    UnsafeOwnershipState,
    build_multi_league_ownership_index,
)
from src.fantasy.service import MultiSleeperSyncResult
from src.fantasy.sync import FantasyIdentityAudit, SleeperSyncResult


def _resolution(sleeper_id: str, entity_id: str | None, *, status: str = MATCHED):
    return SleeperIdentityResolution(
        sleeper_id=sleeper_id,
        status=status,
        propwar_entity_id=entity_id,
        gsis_id=entity_id if status == MATCHED else None,
    )


def _state(
    league_id: str,
    rosters,
    *,
    ownership_ready: bool = True,
    current_user_id: str = "me",
    my_roster_id: str = "1",
):
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=league_id,
        name=f"League {league_id}",
        season="2026",
        status="in_season" if ownership_ready else "pre_draft",
        team_count=len(rosters),
        previous_platform_league_id=None,
        current_platform_user_id=current_user_id,
        my_platform_roster_id=my_roster_id,
        rules=LeagueRules(roster_positions=("QB", "RB", "WR", "FLEX", "BN"), scoring_settings={"rec": 1}),
        draft=None,
        managers=(),
        rosters=tuple(rosters),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def _sync(state, resolutions):
    audit = FantasyIdentityAudit(
        platform="SLEEPER",
        platform_league_id=state.platform_league_id,
        season=state.season,
        player_ids=tuple(row.sleeper_id for row in resolutions),
        resolutions=tuple(resolutions),
    )
    return SleeperSyncResult(
        league_state=state,
        identity_audit=audit,
        player_metadata_entries_used=len(resolutions),
    )


def _multi(*results):
    return MultiSleeperSyncResult(leagues=tuple(results))


def _roster(roster_id, user_id, players, *, starters=(), reserve=(), taxi=()):
    return Roster(
        platform_roster_id=str(roster_id),
        platform_user_id=user_id,
        players=tuple(players),
        starters=tuple(starters),
        reserve=tuple(reserve),
        taxi=tuple(taxi),
        settings={},
    )


def test_index_classifies_my_starter_bench_reserve_taxi_and_opponent():
    state = _state(
        "a",
        (
            _roster("1", "me", ("s1", "s2", "s3", "s4"), starters=("s1",), reserve=("s3",), taxi=("s4",)),
            _roster("2", "other", ("s5",), starters=("s5",)),
        ),
    )
    resolutions = tuple(_resolution(f"s{i}", f"00-{i}") for i in range(1, 6))

    index = build_multi_league_ownership_index(_multi(_sync(state, resolutions)))

    mine = {row.propwar_entity_id: row for rows in index.owned_by_entity.values() for row in rows}
    assert mine["00-1"].status == OWNED
    assert mine["00-1"].roster_slot == STARTER
    assert mine["00-1"].is_mine is True
    assert mine["00-2"].roster_slot == BENCH
    assert mine["00-3"].roster_slot == RESERVE
    assert mine["00-4"].roster_slot == TAXI
    assert mine["00-5"].roster_slot == STARTER
    assert mine["00-5"].is_mine is False
    assert index.entities_owned_by_me == ("00-1", "00-2", "00-3", "00-4")


def test_lookup_can_safely_mark_player_available_in_other_complete_league():
    league_a = _sync(
        _state("a", (_roster("1", "me", ("s1",), starters=("s1",)),)),
        (_resolution("s1", "00-1"),),
    )
    league_b = _sync(
        _state("b", (_roster("9", "other", ("s2",), starters=("s2",)),), my_roster_id="8"),
        (_resolution("s2", "00-2"),),
    )

    index = build_multi_league_ownership_index(_multi(league_a, league_b))
    rows = index.lookup("00-1")

    assert [row.platform_league_id for row in rows] == ["a", "b"]
    assert rows[0].status == OWNED
    assert rows[0].is_mine is True
    assert rows[1].status == AVAILABLE
    assert rows[1].safe_for_waiver_logic is True


def test_identity_gap_blocks_available_even_when_provider_ownership_is_ready():
    league = _sync(
        _state("a", (_roster("1", "me", ("rookie",)),)),
        (_resolution("rookie", None, status=PRE_GSIS),),
    )

    row = build_multi_league_ownership_index(_multi(league)).lookup("00-target")[0]

    assert row.status == UNKNOWN_IDENTITY_GAPS
    assert row.available is False
    assert row.safe_for_waiver_logic is False


def test_pre_draft_or_uninitialized_ownership_blocks_available():
    league = _sync(
        _state("a", (_roster("1", "me", (), starters=("0",)),), ownership_ready=False),
        (),
    )

    row = build_multi_league_ownership_index(_multi(league)).lookup("00-target")[0]

    assert row.status == UNKNOWN_OWNERSHIP_NOT_READY
    assert row.safe_for_waiver_logic is False


def test_duplicate_sleeper_player_on_two_rosters_fails_closed():
    state = _state(
        "a",
        (
            _roster("1", "me", ("s1",)),
            _roster("2", "other", ("s1",)),
        ),
    )
    league = _sync(state, (_resolution("s1", "00-1"),))

    with pytest.raises(UnsafeOwnershipState, match="multiple rosters"):
        build_multi_league_ownership_index(_multi(league))


def test_two_provider_ids_resolving_to_same_entity_in_one_league_fails_closed():
    state = _state(
        "a",
        (
            _roster("1", "me", ("s1",)),
            _roster("2", "other", ("s2",)),
        ),
    )
    league = _sync(
        state,
        (
            _resolution("s1", "00-1"),
            _resolution("s2", "00-1"),
        ),
    )

    with pytest.raises(UnsafeOwnershipState, match="multiple owners"):
        build_multi_league_ownership_index(_multi(league))


def test_lookup_preserves_league_order_and_rejects_blank_entity_id():
    a = _sync(
        _state("a", (_roster("1", "me", ("s1",)),)),
        (_resolution("s1", "00-1"),),
    )
    b = _sync(
        _state("b", (_roster("2", "other", ("s2",)),), my_roster_id="1"),
        (_resolution("s2", "00-2"),),
    )
    index = build_multi_league_ownership_index(_multi(b, a))

    assert [row.platform_league_id for row in index.lookup("00-9")] == ["b", "a"]
    assert [row.status for row in index.lookup("00-9")] == [AVAILABLE, AVAILABLE]
    with pytest.raises(ValueError, match="required"):
        index.lookup("")
