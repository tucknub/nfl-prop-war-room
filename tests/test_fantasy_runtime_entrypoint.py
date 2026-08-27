from __future__ import annotations

from types import SimpleNamespace

import pytest

import src.fantasy.runtime_entrypoint as runtime
from src.fantasy.persistence import LeagueSeasonIdentity
from src.fantasy.runtime_entrypoint import (
    FantasyScheduledRuntimeGateError,
    FantasyScheduledRuntimeResult,
    build_handshake_gated_scheduled_plan,
    run_handshake_gated_scheduled_sleeper_sync,
)
from src.fantasy.runtime_handshake import (
    FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID,
    FantasyRuntimeDeploymentHandshakeError,
    FantasyRuntimeDeploymentHandshakeResult,
)
from src.fantasy.scheduled_sync import (
    SleeperScheduledLeague,
    SleeperScheduledSyncPlan,
)


def _league(index: int, *, season: str = "2026") -> SleeperScheduledLeague:
    return SleeperScheduledLeague(
        identity=LeagueSeasonIdentity(
            league_season_id=f"league-{index}:{season}",
            platform="SLEEPER",
            platform_league_id=f"sleeper-{index}",
            season=season,
        ),
        league_family_id=f"family-{index}",
        family_display_name=f"League {index}",
        season_display_name=f"League {index} {season}",
        registration_created_at_ms=1_000,
    )


class TrackingReader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_nfl_state(self):
        self.calls.append("fetch_nfl_state")
        raise AssertionError("Sleeper must not be fetched before runtime readiness")

    def fetch_normalized_league(self, league_id: str, *, current_user_id=None):
        self.calls.append("fetch_normalized_league")
        raise AssertionError("Sleeper must not be fetched before runtime readiness")

    def fetch_transactions(self, league_id: str, week: int):
        self.calls.append("fetch_transactions")
        raise AssertionError("Sleeper must not be fetched before runtime readiness")


class TrackingClient:
    def __init__(
        self,
        *,
        health_error: Exception | None = None,
        probe_payload: dict | None = None,
    ) -> None:
        self.health_error = health_error
        self.probe_payload = probe_payload
        self.calls: list[str] = []

    def health(self):
        self.calls.append("health")
        if self.health_error is not None:
            raise self.health_error
        return {"ok": True, "status": "ok", "protocol_version": 1}

    def read_sync_run(self, sync_run_id: str):
        self.calls.append(f"read_sync_run:{sync_run_id}")
        if self.probe_payload is not None:
            return self.probe_payload
        return {
            "ok": True,
            "protocol_version": 1,
            "kind": "READ_SYNC_RUN",
            "requested_id": sync_run_id,
            "found": False,
            "record": None,
        }

    def send(self, command):
        self.calls.append("send")
        raise AssertionError("persistence write must not occur before runtime readiness")

    def read_league_season(self, league_season_id: str):
        self.calls.append("read_league_season")
        raise AssertionError("lifecycle must not begin before runtime readiness")

    def read_latest_snapshot(self, league_season_id: str):
        self.calls.append("read_latest_snapshot")
        raise AssertionError("lifecycle must not begin before runtime readiness")


def _assert_no_provider_or_lifecycle_work(reader: TrackingReader, client: TrackingClient):
    assert reader.calls == []
    assert "send" not in client.calls
    assert "read_league_season" not in client.calls
    assert "read_latest_snapshot" not in client.calls


def test_plan_validation_happens_before_handshake_or_provider_io():
    reader = TrackingReader()
    client = TrackingClient()

    with pytest.raises(ValueError, match="At least one scheduled Sleeper league"):
        run_handshake_gated_scheduled_sleeper_sync(
            reader,
            client,
            (),
            scheduled_at_ms=2_000,
            current_user_id="me",
        )

    assert client.calls == []
    _assert_no_provider_or_lifecycle_work(reader, client)


def test_health_failure_prevents_sleeper_fetch_and_persistence_lifecycle():
    reader = TrackingReader()
    client = TrackingClient(health_error=RuntimeError("health down"))

    with pytest.raises(RuntimeError, match="health down"):
        run_handshake_gated_scheduled_sleeper_sync(
            reader,
            client,
            (_league(1),),
            scheduled_at_ms=2_000,
            current_user_id="me",
        )

    assert client.calls == ["health"]
    _assert_no_provider_or_lifecycle_work(reader, client)


def test_reserved_probe_collision_prevents_sleeper_fetch_and_writes():
    reader = TrackingReader()
    client = TrackingClient(
        probe_payload={
            "ok": True,
            "protocol_version": 1,
            "kind": "READ_SYNC_RUN",
            "requested_id": FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID,
            "found": True,
            "record": {
                "sync_run_id": FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID,
            },
        }
    )

    with pytest.raises(
        FantasyRuntimeDeploymentHandshakeError,
        match="reserved runtime handshake probe unexpectedly exists",
    ):
        run_handshake_gated_scheduled_sleeper_sync(
            reader,
            client,
            (_league(1),),
            scheduled_at_ms=2_000,
            current_user_id="me",
        )

    assert client.calls == [
        "health",
        f"read_sync_run:{FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID}",
    ]
    _assert_no_provider_or_lifecycle_work(reader, client)


def test_malformed_authenticated_read_prevents_sleeper_fetch_and_writes():
    reader = TrackingReader()
    client = TrackingClient(
        probe_payload={
            "ok": True,
            "protocol_version": 1,
            "kind": "READ_SYNC_RUN",
            "requested_id": FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID,
            "found": "false",
            "record": None,
        }
    )

    with pytest.raises(FantasyRuntimeDeploymentHandshakeError):
        run_handshake_gated_scheduled_sleeper_sync(
            reader,
            client,
            (_league(1),),
            scheduled_at_ms=2_000,
            current_user_id="me",
        )

    _assert_no_provider_or_lifecycle_work(reader, client)


def test_ready_handshake_executes_exact_frozen_plan_after_gate(monkeypatch):
    reader = object()
    client = object()
    leagues = (_league(2), _league(1))
    order: list[str] = []
    captured = {}
    handshake = FantasyRuntimeDeploymentHandshakeResult(
        handshake_version=1,
        protocol_version=1,
        health_ready=True,
        authenticated_read_ready=True,
        probe_absent=True,
    )
    scheduled_result = SimpleNamespace(
        batch_id="batch-1",
        accepted_count=1,
        no_change_count=1,
        provider_failed_count=0,
        persistence_error_count=0,
        recovery_required_count=0,
    )

    def fake_handshake(client_arg):
        order.append("handshake")
        assert client_arg is client
        return handshake

    def fake_execute(reader_arg, client_arg, plan, *, current_user_id):
        order.append("execute")
        captured["plan"] = plan
        assert reader_arg is reader
        assert client_arg is client
        assert current_user_id == "me"
        return scheduled_result

    monkeypatch.setattr(
        runtime,
        "run_fantasy_runtime_deployment_handshake",
        fake_handshake,
    )
    monkeypatch.setattr(
        runtime,
        "run_sleeper_scheduled_sync_plan",
        fake_execute,
    )

    result = run_handshake_gated_scheduled_sleeper_sync(
        reader,
        client,
        leagues,
        scheduled_at_ms=2_000,
        current_user_id="me",
        schedule_name="hourly",
    )

    expected_plan = build_handshake_gated_scheduled_plan(
        leagues,
        scheduled_at_ms=2_000,
        schedule_name="hourly",
    )

    assert order == ["handshake", "execute"]
    assert captured["plan"] == expected_plan
    assert isinstance(captured["plan"], SleeperScheduledSyncPlan)
    assert result.handshake is handshake
    assert result.scheduled is scheduled_result
    assert result.ready is True
    assert result.batch_id == "batch-1"
    assert result.accepted_count == 1
    assert result.no_change_count == 1


def test_defensive_not_ready_gate_never_executes_scheduled_plan(monkeypatch):
    executed = False

    monkeypatch.setattr(
        runtime,
        "run_fantasy_runtime_deployment_handshake",
        lambda client: SimpleNamespace(ready=False),
    )

    def fake_execute(*args, **kwargs):
        nonlocal executed
        executed = True
        raise AssertionError("scheduled plan must not execute")

    monkeypatch.setattr(runtime, "run_sleeper_scheduled_sync_plan", fake_execute)

    with pytest.raises(FantasyScheduledRuntimeGateError, match="did not reach READY"):
        run_handshake_gated_scheduled_sleeper_sync(
            object(),
            object(),
            (_league(1),),
            scheduled_at_ms=2_000,
            current_user_id="me",
        )

    assert executed is False


def test_runtime_result_rejects_non_ready_handshake():
    with pytest.raises(ValueError, match="ready handshake"):
        FantasyScheduledRuntimeResult(
            handshake=SimpleNamespace(ready=False),
            scheduled=SimpleNamespace(),
        )


def test_public_package_exports_handshake_gated_runtime_contract():
    import src.fantasy as fantasy

    assert fantasy.FantasyScheduledRuntimeGateError is FantasyScheduledRuntimeGateError
    assert fantasy.FantasyScheduledRuntimeResult is FantasyScheduledRuntimeResult
    assert (
        fantasy.build_handshake_gated_scheduled_plan
        is build_handshake_gated_scheduled_plan
    )
    assert (
        fantasy.run_handshake_gated_scheduled_sleeper_sync
        is run_handshake_gated_scheduled_sleeper_sync
    )
