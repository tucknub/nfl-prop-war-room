from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import httpx
import pytest

from src.fantasy.changes import FantasySnapshot
from src.fantasy.models import (
    FantasyLeagueState,
    LeagueRules,
    LeagueTransaction,
    Manager,
    Roster,
)
from src.fantasy.persistence import (
    LeagueSeasonIdentity,
    persistence_content_fingerprint,
    serialize_fantasy_snapshot,
)
from src.fantasy.persistence_http import (
    FantasyPersistenceTransportError,
)
from src.fantasy.persistence_lifecycle import (
    PERSISTENCE_COMPLETED,
    PERSISTENCE_FAILED,
    FantasyPersistenceOutcomeUnknown,
    FantasyPersistenceStateConflict,
)
from src.fantasy.persistence_rehydrate import UnsafePersistedFantasySnapshot
from src.fantasy.persistence_protocol import (
    SYNC_FAILED,
    SYNC_NO_CHANGE,
    SYNC_START,
    SYNC_SUCCESS,
)
from src.fantasy.league_registration_protocol import LEAGUE_SEASON_UPSERT
from src.fantasy.sleeper_current import SleeperNflState
from src.fantasy.sleeper_persistence import (
    SLEEPER_PERSIST_ACCEPTED,
    SLEEPER_PERSIST_EXISTING_FINAL,
    SLEEPER_PERSIST_FAILED,
    SLEEPER_PERSIST_NO_CHANGE,
    run_sleeper_persistence_sync,
)


def _identity() -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id="ffl:2026",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
    )


def _state(
    *,
    players: tuple[str, ...] = ("p1",),
    starters: tuple[str, ...] = ("p1",),
    manager_name: str = "Owner",
    rules_ready: bool = True,
    ownership_ready: bool = True,
) -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-2026",
        name="Franchise Football League",
        season="2026",
        status="in_season" if ownership_ready else "pre_draft",
        team_count=10,
        previous_platform_league_id="league-2025",
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "BN"),
            scoring_settings={"rec": 1},
            waiver_budget=100,
        ),
        draft=None,
        managers=(
            Manager(
                platform_user_id="me",
                display_name=manager_name,
                team_name="Team",
                is_owner=True,
            ),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=players if ownership_ready else (),
                starters=starters if ownership_ready else ("0",),
                reserve=(),
                taxi=(),
                settings={"waiver_position": 1, "waiver_budget_used": 0},
            ),
        ),
        rules_ready=rules_ready,
        draft_ready=True,
        ownership_ready=ownership_ready,
    )


def _tx(
    transaction_id: str,
    week: int,
    *,
    adds: Mapping[str, str] | None = None,
    status: str = "complete",
) -> LeagueTransaction:
    return LeagueTransaction(
        platform_transaction_id=transaction_id,
        transaction_type="free_agent",
        status=status,
        week=week,
        roster_ids=("1",),
        creator_user_id="me",
        created_at_ms=week * 100,
        status_updated_at_ms=week * 100 + 1,
        consenter_roster_ids=("1",),
        adds=dict(adds or {}),
        drops={},
        traded_picks=(),
        faab_transfers=(),
        waiver_bid=None,
        metadata={},
    )


def _nfl_state(leg: int = 4) -> SleeperNflState:
    return SleeperNflState(
        season="2026",
        league_season="2026",
        season_type="regular",
        week=leg,
        leg=leg,
        display_week=leg,
        season_start_date="2026-09-10",
        previous_season="2025",
        league_create_season="2026",
    )


def _latest_record(
    *,
    snapshot_id: str = "snapshot-old",
    state: FantasyLeagueState | None = None,
    transactions: tuple[LeagueTransaction, ...] = (),
    provider_status: str = "HEALTHY",
    source_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = FantasySnapshot(
        snapshot_id,
        state or _state(),
        transactions,
    )
    return {
        "snapshot_id": snapshot.snapshot_id,
        "league_season_id": "ffl:2026",
        "content_fingerprint": persistence_content_fingerprint(snapshot),
        "observed_at_ms": 100,
        "accepted_at_ms": 110,
        "provider_status": provider_status,
        "rules_ready": snapshot.league.rules_ready,
        "draft_ready": snapshot.league.draft_ready,
        "ownership_ready": snapshot.league.ownership_ready,
        "normalized_state": serialize_fantasy_snapshot(snapshot),
        "source_metadata": dict(source_metadata or {}),
    }


def _found(record: Mapping[str, Any] | None) -> dict[str, Any]:
    return {"found": record is not None, "record": record}


@dataclass
class FakeReader:
    state: FantasyLeagueState
    transactions: Mapping[int, tuple[LeagueTransaction, ...]] = field(default_factory=dict)
    state_error: Exception | None = None
    league_calls: int = 0
    transaction_calls: list[int] = field(default_factory=list)

    def fetch_normalized_league(
        self,
        league_id: str,
        *,
        current_user_id: str | None = None,
    ) -> FantasyLeagueState:
        self.league_calls += 1
        if self.state_error is not None:
            raise self.state_error
        return self.state

    def fetch_transactions(
        self,
        league_id: str,
        week: int,
    ) -> tuple[LeagueTransaction, ...]:
        self.transaction_calls.append(week)
        return self.transactions.get(week, ())


@dataclass
class FakeTransport:
    identity: LeagueSeasonIdentity = field(default_factory=_identity)
    league_record: Mapping[str, Any] | None = None
    sync_record: dict[str, Any] | None = None
    latest_payload: Mapping[str, Any] = field(
        default_factory=lambda: _found(None)
    )
    read_latest_error: Exception | None = None
    send_errors: dict[str, list[Exception]] = field(default_factory=dict)
    sends: list[Mapping[str, Any]] = field(default_factory=list)
    read_latest_calls: int = 0

    def read_league_season(self, league_season_id: str) -> Mapping[str, Any]:
        return _found(self.league_record)

    def read_sync_run(self, sync_run_id: str) -> Mapping[str, Any]:
        return _found(self.sync_record)

    def read_latest_snapshot(self, league_season_id: str) -> Mapping[str, Any]:
        self.read_latest_calls += 1
        if self.read_latest_error is not None:
            raise self.read_latest_error
        return self.latest_payload

    def send(self, command: Mapping[str, Any]) -> Mapping[str, Any]:
        self.sends.append(dict(command))
        kind = str(command["kind"])
        errors = self.send_errors.get(kind)
        if errors:
            raise errors.pop(0)

        if kind == LEAGUE_SEASON_UPSERT:
            identity = command["identity"]
            self.league_record = {
                "league_season_id": identity["league_season_id"],
                "league_family_id": command["league_family_id"],
                "platform": identity["platform"],
                "platform_league_id": identity["platform_league_id"],
                "season": identity["season"],
                "display_name": command["season_display_name"],
                "created_at_ms": command["created_at_ms"],
                "metadata": {},
            }
        elif kind == SYNC_START:
            identity = command["identity"]
            self.sync_record = {
                "sync_run_id": command["sync_run_id"],
                "league_season_id": identity["league_season_id"],
                "platform": identity["platform"],
                "platform_league_id": identity["platform_league_id"],
                "season": identity["season"],
                "started_at_ms": command["started_at_ms"],
                "completed_at_ms": None,
                "status": "STARTED",
                "accepted_snapshot_id": None,
                "error_code": None,
            }
        elif kind == SYNC_SUCCESS:
            assert self.sync_record is not None
            self.sync_record.update(
                completed_at_ms=command["completed_at_ms"],
                status="COMPLETED",
                accepted_snapshot_id=command["snapshot"]["snapshot_id"],
                error_code=None,
            )
        elif kind == SYNC_NO_CHANGE:
            assert self.sync_record is not None
            self.sync_record.update(
                completed_at_ms=command["completed_at_ms"],
                status="COMPLETED",
                accepted_snapshot_id=command["accepted_snapshot_id"],
                error_code=None,
            )
        elif kind == SYNC_FAILED:
            assert self.sync_record is not None
            self.sync_record.update(
                completed_at_ms=command["completed_at_ms"],
                status="FAILED",
                accepted_snapshot_id=None,
                error_code=command["error_code"],
            )
        return {"ok": True}


def _existing_league_record() -> dict[str, Any]:
    identity = _identity()
    return {
        "league_season_id": identity.league_season_id,
        "league_family_id": "ffl",
        "platform": identity.platform,
        "platform_league_id": identity.platform_league_id,
        "season": identity.season,
        "display_name": "FFL 2026",
        "created_at_ms": 1,
        "metadata": {},
    }


def _started_sync_record() -> dict[str, Any]:
    identity = _identity()
    return {
        "sync_run_id": "sync-1",
        "league_season_id": identity.league_season_id,
        "platform": identity.platform,
        "platform_league_id": identity.platform_league_id,
        "season": identity.season,
        "started_at_ms": 10,
        "completed_at_ms": None,
        "status": "STARTED",
        "accepted_snapshot_id": None,
        "error_code": None,
    }


def _run(
    reader: FakeReader,
    transport: FakeTransport,
    *,
    nfl_state: SleeperNflState | None = None,
    snapshot_id: str = "snapshot-new",
):
    return run_sleeper_persistence_sync(
        reader,
        transport,
        _identity(),
        league_family_id="ffl",
        family_display_name="Franchise Football League",
        season_display_name="FFL 2026",
        registration_created_at_ms=1,
        sync_run_id="sync-1",
        snapshot_id=snapshot_id,
        current_user_id="me",
        nfl_state=nfl_state or _nfl_state(),
        started_at_ms=10,
        observed_at_ms=200,
        accepted_at_ms=210,
        completed_at_ms=230,
        derived_at_ms=220,
        family_metadata={"source": "test"},
        season_metadata={"status": "in_season"},
        request_metadata={"trigger": "test"},
    )


def _kinds(transport: FakeTransport) -> list[str]:
    return [str(command["kind"]) for command in transport.sends]


def test_initial_baseline_registers_starts_reads_provider_and_accepts_snapshot():
    tx = _tx("tx-4", 4)
    reader = FakeReader(_state(), {4: (tx,)})
    transport = FakeTransport()

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_ACCEPTED
    assert result.previous_snapshot_id is None
    assert result.current_snapshot_id == "snapshot-new"
    assert result.events == ()
    assert result.transaction_rounds == (4,)
    assert result.accepted_snapshot_id == "snapshot-new"
    assert _kinds(transport) == [
        LEAGUE_SEASON_UPSERT,
        SYNC_START,
        SYNC_SUCCESS,
    ]
    success = transport.sends[-1]
    assert success["expected_previous_snapshot_id"] is None
    assert success["events"] == []
    assert success["snapshot"]["source_metadata_json"]
    assert reader.transaction_calls == [4]


def test_identical_full_state_uses_no_change_and_reuses_previous_snapshot():
    tx = _tx("tx-4", 4)
    previous = _latest_record(
        transactions=(tx,),
        source_metadata={"provider": "SLEEPER", "transaction_round": 4},
    )
    reader = FakeReader(_state(), {4: (tx,)})
    transport = FakeTransport(latest_payload=_found(previous))

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_NO_CHANGE
    assert result.previous_snapshot_id == "snapshot-old"
    assert result.current_snapshot_id == "snapshot-new"
    assert result.accepted_snapshot_id == "snapshot-old"
    assert result.events == ()
    assert _kinds(transport)[-1] == SYNC_NO_CHANGE
    assert SYNC_SUCCESS not in _kinds(transport)


def test_changed_roster_and_transaction_derive_events_and_accept_new_snapshot():
    old_tx = _tx("tx-3", 3)
    previous = _latest_record(
        state=_state(players=("p1",), starters=("p1",)),
        transactions=(old_tx,),
        source_metadata={"provider": "SLEEPER", "transaction_round": 3},
    )
    new_tx = _tx("tx-4", 4, adds={"p2": "1"})
    reader = FakeReader(
        _state(players=("p1", "p2"), starters=("p1",)),
        {3: (old_tx,), 4: (new_tx,)},
    )
    transport = FakeTransport(latest_payload=_found(previous))

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_ACCEPTED
    event_types = {event.event_type for event in result.events}
    assert "PLAYER_ADDED" in event_types
    assert "TRANSACTION_COMPLETED" in event_types
    assert result.transaction_rounds == (3, 4)
    success = transport.sends[-1]
    assert success["kind"] == SYNC_SUCCESS
    assert success["expected_previous_snapshot_id"] == "snapshot-old"
    assert all(
        event["before_snapshot_id"] == "snapshot-old"
        for event in success["events"]
    )



def test_current_provider_row_replaces_prior_pending_transaction_and_emits_completion():
    pending = _tx("tx-4", 4, adds={"p2": "1"}, status="pending")
    completed = _tx("tx-4", 4, adds={"p2": "1"}, status="complete")
    previous = _latest_record(
        state=_state(players=("p1",), starters=("p1",)),
        transactions=(pending,),
        source_metadata={"provider": "SLEEPER", "transaction_round": 4},
    )
    reader = FakeReader(
        _state(players=("p1", "p2"), starters=("p1",)),
        {4: (completed,)},
    )
    transport = FakeTransport(latest_payload=_found(previous))

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_ACCEPTED
    assert {event.event_type for event in result.events} >= {
        "PLAYER_ADDED",
        "TRANSACTION_COMPLETED",
    }
    assert transport.sends[-1]["kind"] == SYNC_SUCCESS


def test_full_metadata_change_persists_new_snapshot_even_with_zero_change_events():
    previous = _latest_record(
        state=_state(manager_name="Old Name"),
        source_metadata={"provider": "SLEEPER", "transaction_round": 4},
    )
    reader = FakeReader(_state(manager_name="New Name"))
    transport = FakeTransport(latest_payload=_found(previous))

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_ACCEPTED
    assert result.events == ()
    assert _kinds(transport)[-1] == SYNC_SUCCESS



def test_quiet_week_preserves_older_transaction_history_and_can_no_change():
    tx2 = _tx("tx-2", 2)
    tx3 = _tx("tx-3", 3)
    previous = _latest_record(
        transactions=(tx2, tx3),
        source_metadata={"provider": "SLEEPER", "transaction_round": 3},
    )
    reader = FakeReader(
        _state(),
        {
            3: (tx3,),
            4: (),
        },
    )
    transport = FakeTransport(latest_payload=_found(previous))

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_NO_CHANGE
    assert result.transaction_rounds == (3, 4)
    assert _kinds(transport)[-1] == SYNC_NO_CHANGE


def test_quiet_ownership_ready_prior_without_round_metadata_is_state_conflict():
    previous = _latest_record(
        transactions=(),
        source_metadata={"provider": "SLEEPER"},
    )
    reader = FakeReader(_state())
    transport = FakeTransport(latest_payload=_found(previous))

    with pytest.raises(
        FantasyPersistenceStateConflict,
        match="transaction_round metadata is required",
    ):
        _run(reader, transport)

    assert reader.league_calls == 0
    assert transport.sync_record is not None
    assert transport.sync_record["status"] == "STARTED"
    assert SYNC_FAILED not in _kinds(transport)


def test_provider_http_failure_after_started_sync_is_recorded_safely():
    request = httpx.Request("GET", "https://api.sleeper.app/v1/league/test")
    reader = FakeReader(
        _state(),
        state_error=httpx.ConnectError("private provider detail", request=request),
    )
    transport = FakeTransport()

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_FAILED
    assert result.error_code == "SLEEPER_PROVIDER_ERROR"
    assert result.outcome.state == PERSISTENCE_FAILED
    failure = transport.sends[-1]
    assert failure["kind"] == SYNC_FAILED
    assert failure["error_summary"] == "ConnectError"
    assert "private provider detail" not in failure["error_summary"]


def test_unsafe_current_provider_state_is_recorded_failed():
    reader = FakeReader(_state())
    transport = FakeTransport()

    result = _run(reader, transport, nfl_state=_nfl_state(leg=0))

    assert result.mode == SLEEPER_PERSIST_FAILED
    assert result.error_code == "SLEEPER_STATE_UNSAFE"
    assert transport.sends[-1]["kind"] == SYNC_FAILED


def test_unsafe_snapshot_transition_is_recorded_failed_not_accepted():
    previous = _latest_record(
        state=_state(rules_ready=True),
        source_metadata={"provider": "SLEEPER", "transaction_round": 4},
    )
    reader = FakeReader(_state(rules_ready=False))
    transport = FakeTransport(latest_payload=_found(previous))

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_FAILED
    assert result.error_code == "SNAPSHOT_TRANSITION_UNSAFE"
    assert SYNC_SUCCESS not in _kinds(transport)
    assert transport.sends[-1]["kind"] == SYNC_FAILED


def test_latest_snapshot_transport_failure_propagates_and_leaves_started_sync():
    reader = FakeReader(_state())
    transport = FakeTransport(
        read_latest_error=FantasyPersistenceTransportError("private read failure")
    )

    with pytest.raises(FantasyPersistenceTransportError):
        _run(reader, transport)

    assert reader.league_calls == 0
    assert transport.sync_record is not None
    assert transport.sync_record["status"] == "STARTED"
    assert SYNC_FAILED not in _kinds(transport)


def test_corrupt_persisted_snapshot_propagates_before_provider_fetch():
    corrupt = _latest_record()
    corrupt["content_fingerprint"] = "0" * 64
    reader = FakeReader(_state())
    transport = FakeTransport(latest_payload=_found(corrupt))

    with pytest.raises(UnsafePersistedFantasySnapshot):
        _run(reader, transport)

    assert reader.league_calls == 0
    assert transport.sync_record is not None
    assert transport.sync_record["status"] == "STARTED"
    assert SYNC_FAILED not in _kinds(transport)


def test_existing_final_sync_returns_without_latest_or_provider_work():
    transport = FakeTransport(
        league_record=_existing_league_record(),
        sync_record={
            **_started_sync_record(),
            "completed_at_ms": 20,
            "status": "COMPLETED",
            "accepted_snapshot_id": "snapshot-existing",
        },
    )
    reader = FakeReader(_state())

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_EXISTING_FINAL
    assert result.outcome.state == PERSISTENCE_COMPLETED
    assert result.accepted_snapshot_id == "snapshot-existing"
    assert transport.read_latest_calls == 0
    assert reader.league_calls == 0
    assert transport.sends == []


def test_invalid_persisted_transaction_round_is_state_conflict_not_provider_failure():
    previous = _latest_record(
        source_metadata={"provider": "SLEEPER", "transaction_round": "4"}
    )
    reader = FakeReader(_state())
    transport = FakeTransport(latest_payload=_found(previous))

    with pytest.raises(
        FantasyPersistenceStateConflict,
        match="transaction_round",
    ):
        _run(reader, transport)

    assert reader.league_calls == 0
    assert transport.sync_record is not None
    assert transport.sync_record["status"] == "STARTED"
    assert SYNC_FAILED not in _kinds(transport)


def test_provider_status_change_forces_new_snapshot_even_if_content_matches():
    previous = _latest_record(
        provider_status="STALE",
        source_metadata={"provider": "SLEEPER", "transaction_round": 4},
    )
    reader = FakeReader(_state())
    transport = FakeTransport(latest_payload=_found(previous))

    result = _run(reader, transport)

    assert result.mode == SLEEPER_PERSIST_ACCEPTED
    assert result.events == ()
    assert _kinds(transport)[-1] == SYNC_SUCCESS


def test_ambiguous_success_outcome_propagates_and_is_not_rewritten_as_failed():
    previous = _latest_record(
        state=_state(manager_name="Old"),
        source_metadata={"provider": "SLEEPER", "transaction_round": 4},
    )
    reader = FakeReader(_state(manager_name="New"))
    transport = FakeTransport(
        latest_payload=_found(previous),
        send_errors={
            SYNC_SUCCESS: [
                FantasyPersistenceTransportError("connection reset")
            ]
        },
    )

    with pytest.raises(FantasyPersistenceOutcomeUnknown):
        _run(reader, transport)

    assert transport.sync_record is not None
    assert transport.sync_record["status"] == "STARTED"
    assert _kinds(transport).count(SYNC_SUCCESS) == 1
    assert SYNC_FAILED not in _kinds(transport)


def test_runner_rejects_non_sleeper_identity_before_any_io():
    identity = LeagueSeasonIdentity(
        league_season_id="yahoo:2026",
        platform="YAHOO",
        platform_league_id="league",
        season="2026",
    )
    reader = FakeReader(_state())
    transport = FakeTransport()

    with pytest.raises(
        FantasyPersistenceStateConflict,
        match="platform=SLEEPER",
    ):
        run_sleeper_persistence_sync(
            reader,
            transport,
            identity,
            league_family_id="league",
            family_display_name="League",
            season_display_name="League 2026",
            registration_created_at_ms=1,
            sync_run_id="sync",
            snapshot_id="snapshot",
            current_user_id="me",
            nfl_state=_nfl_state(),
            started_at_ms=10,
            observed_at_ms=20,
            accepted_at_ms=21,
            completed_at_ms=23,
            derived_at_ms=22,
        )

    assert transport.sends == []
    assert reader.league_calls == 0


def test_public_package_exports_runner_contract():
    import src.fantasy as fantasy

    assert fantasy.SLEEPER_PERSIST_ACCEPTED == SLEEPER_PERSIST_ACCEPTED
    assert fantasy.SLEEPER_PERSIST_NO_CHANGE == SLEEPER_PERSIST_NO_CHANGE
    assert fantasy.SLEEPER_PERSIST_FAILED == SLEEPER_PERSIST_FAILED
    assert (
        fantasy.SLEEPER_PERSIST_EXISTING_FINAL
        == SLEEPER_PERSIST_EXISTING_FINAL
    )
    assert fantasy.run_sleeper_persistence_sync is run_sleeper_persistence_sync
