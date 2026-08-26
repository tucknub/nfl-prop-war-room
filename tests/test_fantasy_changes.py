from __future__ import annotations

from dataclasses import replace

import pytest

from src.fantasy.changes import FantasySnapshot, UnsafeSnapshotTransition, derive_fantasy_change_events
from src.fantasy.models import DraftState, FantasyLeagueState, LeagueRules, LeagueTransaction, Roster


def _rules(*, pass_td: int = 6) -> LeagueRules:
    return LeagueRules(
        roster_positions=("QB", "RB", "WR", "FLEX", "BN"),
        scoring_settings={"rec": 1, "pass_td": pass_td},
        waiver_budget=100,
        playoff_teams=4,
    )


def _draft(*, status: str = "complete", start_time_ms: int = 1000) -> DraftState:
    return DraftState(
        platform_draft_id="draft-1",
        status=status,
        draft_type="snake",
        rounds=5,
        teams=2,
        start_time_ms=start_time_ms,
        draft_order={"u1": 1, "u2": 2},
        slot_counts={"QB": 1, "RB": 1, "WR": 1, "FLEX": 1, "BN": 1},
    )


def _roster(
    roster_id: str,
    players=(),
    *,
    starters=(),
    reserve=(),
    faab_used: int | None = 0,
    waiver_position: int | None = 1,
) -> Roster:
    settings = {}
    if faab_used is not None:
        settings["waiver_budget_used"] = faab_used
    if waiver_position is not None:
        settings["waiver_position"] = waiver_position
    return Roster(
        platform_roster_id=roster_id,
        platform_user_id=f"u{roster_id}",
        players=tuple(players),
        starters=tuple(starters),
        reserve=tuple(reserve),
        taxi=(),
        settings=settings,
    )


def _state(
    rosters,
    *,
    ownership_ready: bool = True,
    rules: LeagueRules | None = None,
    draft: DraftState | None = None,
    rules_ready: bool = True,
    draft_ready: bool = True,
    platform_league_id: str = "league-1",
    season: str = "2026",
) -> FantasyLeagueState:
    rosters = tuple(rosters)
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id=platform_league_id,
        name="Test League",
        season=season,
        status="in_season" if ownership_ready else "pre_draft",
        team_count=len(rosters),
        previous_platform_league_id=None,
        current_platform_user_id="u1",
        my_platform_roster_id="1",
        rules=rules or _rules(),
        draft=draft or _draft(),
        managers=(),
        rosters=rosters,
        rules_ready=rules_ready,
        draft_ready=draft_ready,
        ownership_ready=ownership_ready,
    )


def _transaction(
    transaction_id: str,
    *,
    status: str = "complete",
    adds=None,
    drops=None,
    waiver_bid: int | None = None,
) -> LeagueTransaction:
    return LeagueTransaction(
        platform_transaction_id=transaction_id,
        transaction_type="waiver",
        status=status,
        week=2,
        roster_ids=("1", "2"),
        creator_user_id="u1",
        created_at_ms=100,
        status_updated_at_ms=200,
        consenter_roster_ids=("1",),
        adds=adds or {},
        drops=drops or {},
        traded_picks=(),
        faab_transfers=(),
        waiver_bid=waiver_bid,
        metadata={},
    )


def _types(events):
    return [event.event_type for event in events]


def test_identical_snapshots_emit_no_events():
    state = _state([
        _roster("1", ["A", "B"], starters=["A"]),
        _roster("2", ["C"], starters=["C"]),
    ])
    before = FantasySnapshot(state)
    after = FantasySnapshot(state)
    assert before.fingerprint == after.fingerprint
    assert derive_fantasy_change_events(before, after) == ()


def test_first_authoritative_ownership_emits_initialization_without_player_churn():
    before = FantasySnapshot(_state([_roster("1"), _roster("2")], ownership_ready=False))
    after = FantasySnapshot(
        _state([
            _roster("1", ["A", "B"], starters=["A"]),
            _roster("2", ["C", "D"], starters=["C"]),
        ], ownership_ready=True)
    )
    events = derive_fantasy_change_events(before, after)
    assert "OWNERSHIP_INITIALIZED" in _types(events)
    assert not {"PLAYER_ADDED", "PLAYER_DROPPED", "PLAYER_BECAME_AVAILABLE"}.intersection(_types(events))
    init = next(event for event in events if event.event_type == "OWNERSHIP_INITIALIZED")
    assert init.after_value["owned_player_count"] == 4
    assert init.after_value["rosters_with_players"] == 2


def test_owned_player_transfer_emits_drop_and_add_with_transaction_link():
    before = FantasySnapshot(_state([
        _roster("1", ["A", "B"], starters=["A"]),
        _roster("2", ["C"], starters=["C"]),
    ]))
    tx = _transaction("tx-transfer", adds={"B": "2"}, drops={"B": "1"})
    after = FantasySnapshot(
        _state([
            _roster("1", ["A"], starters=["A"]),
            _roster("2", ["B", "C"], starters=["C"]),
        ]),
        transactions=(tx,),
    )
    events = [event for event in derive_fantasy_change_events(before, after) if event.platform_player_id == "B"]
    assert {event.event_type for event in events} == {"PLAYER_ADDED", "PLAYER_DROPPED"}
    assert all(event.source_transaction_ids == ("tx-transfer",) for event in events)


def test_unowned_and_newly_owned_players_have_distinct_events():
    before = FantasySnapshot(_state([
        _roster("1", ["A", "B"], starters=["A"]),
        _roster("2", ["C"], starters=["C"]),
    ]))
    after = FantasySnapshot(_state([
        _roster("1", ["A", "D"], starters=["A"]),
        _roster("2", ["C"], starters=["C"]),
    ]))
    events = derive_fantasy_change_events(before, after)
    b_events = {event.event_type for event in events if event.platform_player_id == "B"}
    d_events = {event.event_type for event in events if event.platform_player_id == "D"}
    assert b_events == {"PLAYER_DROPPED", "PLAYER_BECAME_AVAILABLE"}
    assert d_events == {"PLAYER_ADDED"}


def test_starter_reserve_faab_and_waiver_priority_changes_are_explicit():
    before = FantasySnapshot(_state([
        _roster("1", ["A", "B"], starters=["A"], reserve=["B"], faab_used=10, waiver_position=2),
        _roster("2", ["C"], starters=["C"], faab_used=0, waiver_position=1),
    ]))
    after = FantasySnapshot(_state([
        _roster("1", ["A", "B"], starters=["B"], reserve=[], faab_used=25, waiver_position=1),
        _roster("2", ["C"], starters=["C"], faab_used=0, waiver_position=2),
    ]))
    events = derive_fantasy_change_events(before, after)
    assert {event.platform_player_id for event in events if event.event_type == "STARTER_CHANGED"} == {"A", "B"}
    assert {event.platform_player_id for event in events if event.event_type == "IR_CHANGED"} == {"B"}
    assert any(event.event_type == "FAAB_CHANGED" and event.platform_roster_id == "1" for event in events)
    assert {event.platform_roster_id for event in events if event.event_type == "WAIVER_PRIORITY_CHANGED"} == {"1", "2"}


def test_missing_faab_value_does_not_invent_change():
    before = FantasySnapshot(_state([
        _roster("1", ["A"], starters=["A"], faab_used=None),
        _roster("2", ["C"], starters=["C"]),
    ]))
    after = FantasySnapshot(_state([
        _roster("1", ["A"], starters=["A"], faab_used=12),
        _roster("2", ["C"], starters=["C"]),
    ]))
    assert "FAAB_CHANGED" not in _types(derive_fantasy_change_events(before, after))


def test_rule_and_draft_state_changes_are_detected_without_strategy_inference():
    before_state = _state([
        _roster("1", ["A"], starters=["A"]),
        _roster("2", ["C"], starters=["C"]),
    ])
    after_state = replace(before_state, rules=_rules(pass_td=4), draft=_draft(start_time_ms=2000))
    events = derive_fantasy_change_events(FantasySnapshot(before_state), FantasySnapshot(after_state))
    assert "LEAGUE_RULE_CHANGED" in _types(events)
    assert "DRAFT_STATE_CHANGED" in _types(events)


def test_pending_transaction_becoming_complete_emits_completion_once():
    state = _state([
        _roster("1", ["A"], starters=["A"]),
        _roster("2", ["C"], starters=["C"]),
    ])
    pending = _transaction("tx-1", status="pending", waiver_bid=11)
    complete = _transaction("tx-1", status="complete", waiver_bid=11)
    events = derive_fantasy_change_events(
        FantasySnapshot(state, transactions=(pending,)),
        FantasySnapshot(state, transactions=(complete,)),
    )
    completed = [event for event in events if event.event_type == "TRANSACTION_COMPLETED"]
    assert len(completed) == 1
    assert completed[0].source_transaction_ids == ("tx-1",)
    assert derive_fantasy_change_events(
        FantasySnapshot(state, transactions=(complete,)),
        FantasySnapshot(state, transactions=(complete,)),
    ) == ()


def test_event_fingerprints_are_deterministic():
    before = FantasySnapshot(_state([
        _roster("1", ["A", "B"], starters=["A"]),
        _roster("2", ["C"], starters=["C"]),
    ]))
    after = FantasySnapshot(_state([
        _roster("1", ["A"], starters=["A"]),
        _roster("2", ["B", "C"], starters=["C"]),
    ]))
    first = derive_fantasy_change_events(before, after)
    second = derive_fantasy_change_events(before, after)
    assert [event.event_fingerprint for event in first] == [event.event_fingerprint for event in second]
    assert len({event.event_fingerprint for event in first}) == len(first)


def test_readiness_regression_fails_closed():
    ready = _state([
        _roster("1", ["A"], starters=["A"]),
        _roster("2", ["C"], starters=["C"]),
    ])
    degraded = replace(ready, ownership_ready=False, status="pre_draft")
    with pytest.raises(UnsafeSnapshotTransition, match="ownership readiness regressed"):
        derive_fantasy_change_events(FantasySnapshot(ready), FantasySnapshot(degraded))


def test_duplicate_player_ownership_fails_closed():
    invalid = _state([
        _roster("1", ["A"], starters=["A"]),
        _roster("2", ["A", "C"], starters=["C"]),
    ])
    with pytest.raises(UnsafeSnapshotTransition, match="multiple rosters"):
        derive_fantasy_change_events(FantasySnapshot(invalid), FantasySnapshot(invalid))


def test_cross_league_diff_is_rejected():
    base = _state([
        _roster("1", ["A"], starters=["A"]),
        _roster("2", ["C"], starters=["C"]),
    ])
    other = replace(base, platform_league_id="league-2")
    with pytest.raises(UnsafeSnapshotTransition, match="same platform league and season"):
        derive_fantasy_change_events(FantasySnapshot(base), FantasySnapshot(other))
