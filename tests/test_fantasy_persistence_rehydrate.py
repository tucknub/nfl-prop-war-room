from __future__ import annotations

from dataclasses import replace

import pytest

from src.fantasy.changes import FantasySnapshot
from src.fantasy.models import (
    DraftState,
    FaabTransfer,
    FantasyLeagueState,
    LeagueRules,
    LeagueTransaction,
    Manager,
    Roster,
    TradedPick,
)
from src.fantasy.persistence import (
    persistence_content_fingerprint,
    serialize_fantasy_snapshot,
)
from src.fantasy.persistence_rehydrate import (
    PersistedFantasySnapshot,
    UnsafePersistedFantasySnapshot,
    rehydrate_latest_snapshot_read,
    rehydrate_persisted_snapshot_record,
)


def _state() -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-2026",
        name="Franchise Football League",
        season="2026",
        status="in_season",
        team_count=10,
        previous_platform_league_id="league-2025",
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "BN", "IR"),
            scoring_settings={"rec": 1, "pass_td": 6},
            waiver_budget=100,
            max_keepers=1,
            playoff_teams=6,
            playoff_week_start=15,
            trade_deadline=12,
            reserve_slots=1,
            taxi_slots=0,
            position_limits={"QB": 3},
            rule_settings={"waiver_type": 2},
            raw_settings={"provider_only": "excluded"},
        ),
        draft=DraftState(
            platform_draft_id="draft-1",
            status="complete",
            draft_type="snake",
            rounds=16,
            teams=10,
            start_time_ms=1000,
            draft_order={"me": 1},
            slot_counts={"QB": 1, "RB": 2},
            position_limits={"QB": 3},
            enforce_position_limits=True,
            raw={"provider_only": "excluded"},
        ),
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Tucknub",
                team_name="My Team",
                is_owner=True,
            ),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=("player-1", "player-2"),
                starters=("player-1",),
                reserve=("player-2",),
                taxi=(),
                settings={"waiver_position": 2, "waiver_budget_used": 10},
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _transaction() -> LeagueTransaction:
    return LeagueTransaction(
        platform_transaction_id="tx-1",
        transaction_type="waiver",
        status="complete",
        week=2,
        roster_ids=("1", "2"),
        creator_user_id="me",
        created_at_ms=1100,
        status_updated_at_ms=1200,
        consenter_roster_ids=("1",),
        adds={"player-3": "1"},
        drops={"player-2": "1"},
        traded_picks=(
            TradedPick(
                season="2027",
                round=2,
                original_roster_id="1",
                previous_owner_roster_id="1",
                owner_roster_id="2",
            ),
        ),
        faab_transfers=(
            FaabTransfer(
                sender_roster_id="1",
                receiver_roster_id="2",
                amount=5,
            ),
        ),
        waiver_bid=17,
        metadata={"source": "test"},
        raw={"provider_only": "excluded"},
    )


def _snapshot() -> FantasySnapshot:
    return FantasySnapshot(
        snapshot_id="snapshot-1",
        league=_state(),
        transactions=(_transaction(),),
    )


def _record(snapshot: FantasySnapshot | None = None) -> dict:
    snapshot = snapshot or _snapshot()
    return {
        "snapshot_id": snapshot.snapshot_id,
        "league_season_id": "ffl:2026",
        "content_fingerprint": persistence_content_fingerprint(snapshot),
        "observed_at_ms": 2000,
        "accepted_at_ms": 2010,
        "provider_status": "HEALTHY",
        "rules_ready": snapshot.league.rules_ready,
        "draft_ready": snapshot.league.draft_ready,
        "ownership_ready": snapshot.league.ownership_ready,
        "normalized_state": serialize_fantasy_snapshot(snapshot),
        "source_metadata": {"trigger": "test"},
    }


def test_round_trip_rehydrates_exact_domain_snapshot_and_metadata():
    original = _snapshot()
    persisted = rehydrate_persisted_snapshot_record(_record(original))

    assert isinstance(persisted, PersistedFantasySnapshot)
    assert persisted.snapshot == original
    assert persisted.snapshot.league.rules.raw_settings == {}
    assert persisted.snapshot.league.draft is not None
    assert persisted.snapshot.league.draft.raw == {}
    assert persisted.snapshot.transactions[0].raw == {}
    assert persisted.league_season_id == "ffl:2026"
    assert persisted.provider_status == "HEALTHY"
    assert persisted.source_metadata == {"trigger": "test"}


def test_latest_read_found_false_returns_none():
    assert rehydrate_latest_snapshot_read({"found": False, "record": None}) is None


def test_latest_read_found_true_rehydrates_record():
    result = rehydrate_latest_snapshot_read(
        {"found": True, "record": _record()}
    )
    assert result is not None
    assert result.snapshot.snapshot_id == "snapshot-1"


def test_content_fingerprint_tampering_is_rejected():
    row = _record()
    row["normalized_state"]["league"]["name"] = "Tampered"

    with pytest.raises(
        UnsafePersistedFantasySnapshot,
        match="content_fingerprint",
    ):
        rehydrate_persisted_snapshot_record(row)


def test_rules_fingerprint_tampering_is_rejected_even_if_outer_hash_is_recomputed():
    original = _snapshot()
    row = _record(original)
    row["normalized_state"]["league"]["rules"]["waiver_budget"] = 999

    tampered_state = replace(
        original.league,
        rules=replace(original.league.rules, waiver_budget=999),
    )
    tampered_snapshot = FantasySnapshot(
        original.snapshot_id,
        tampered_state,
        original.transactions,
    )
    row["content_fingerprint"] = persistence_content_fingerprint(tampered_snapshot)

    with pytest.raises(
        UnsafePersistedFantasySnapshot,
        match="rules_fingerprint",
    ):
        rehydrate_persisted_snapshot_record(row)


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("rules_ready", False),
        ("draft_ready", False),
        ("ownership_ready", False),
    ],
)
def test_readiness_column_mismatch_is_rejected(column, value):
    row = _record()
    row[column] = value
    with pytest.raises(
        UnsafePersistedFantasySnapshot,
        match="disagrees",
    ):
        rehydrate_persisted_snapshot_record(row)


def test_unknown_or_missing_persisted_fields_fail_closed():
    extra = _record()
    extra["unexpected"] = True
    with pytest.raises(UnsafePersistedFantasySnapshot, match="unsupported shape"):
        rehydrate_persisted_snapshot_record(extra)

    missing = _record()
    del missing["provider_status"]
    with pytest.raises(UnsafePersistedFantasySnapshot, match="unsupported shape"):
        rehydrate_persisted_snapshot_record(missing)


def test_nested_shape_and_types_fail_closed():
    bad_managers = _record()
    bad_managers["normalized_state"]["league"]["managers"] = "not-an-array"
    with pytest.raises(UnsafePersistedFantasySnapshot, match="must be an array"):
        rehydrate_persisted_snapshot_record(bad_managers)

    bad_bool = _record()
    bad_bool["normalized_state"]["league"]["rules_ready"] = 1
    with pytest.raises(UnsafePersistedFantasySnapshot, match="must be boolean"):
        rehydrate_persisted_snapshot_record(bad_bool)

    bad_mapping = _record()
    bad_mapping["normalized_state"]["transactions"][0]["adds"] = []
    with pytest.raises(UnsafePersistedFantasySnapshot, match="must be an object"):
        rehydrate_persisted_snapshot_record(bad_mapping)


def test_timestamps_and_latest_read_envelope_fail_closed():
    row = _record()
    row["accepted_at_ms"] = row["observed_at_ms"] - 1
    with pytest.raises(UnsafePersistedFantasySnapshot, match="cannot precede"):
        rehydrate_persisted_snapshot_record(row)

    with pytest.raises(UnsafePersistedFantasySnapshot, match="record=null"):
        rehydrate_latest_snapshot_read({"found": False, "record": {}})

    with pytest.raises(UnsafePersistedFantasySnapshot, match="found must be boolean"):
        rehydrate_latest_snapshot_read({"found": "false", "record": None})


def test_public_package_exports_rehydration_contract():
    import src.fantasy as fantasy

    assert fantasy.PersistedFantasySnapshot is PersistedFantasySnapshot
    assert fantasy.UnsafePersistedFantasySnapshot is UnsafePersistedFantasySnapshot
    assert fantasy.rehydrate_latest_snapshot_read is rehydrate_latest_snapshot_read
    assert (
        fantasy.rehydrate_persisted_snapshot_record
        is rehydrate_persisted_snapshot_record
    )
