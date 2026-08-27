from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.fantasy.canary as canary
from src.fantasy.changes import FantasySnapshot
from src.fantasy.models import FantasyLeagueState, LeagueRules, Manager, Roster
from src.fantasy.persistence import (
    LeagueSeasonIdentity,
    persistence_content_fingerprint,
    serialize_fantasy_snapshot,
)
from src.fantasy.canary import (
    FANTASY_SINGLE_LEAGUE_CANARY_CONFIRMATION,
    FANTASY_SINGLE_LEAGUE_CANARY_SCHEDULE_NAME,
    FANTASY_SINGLE_LEAGUE_CANARY_VERSION,
    FantasySingleLeagueCanaryConfig,
    FantasySingleLeagueCanaryError,
    FantasySingleLeagueCanaryResult,
    run_single_league_persistence_canary,
    run_single_league_persistence_canary_from_env,
)
from src.fantasy.scheduled_sync import (
    SleeperScheduledLeague,
    build_sleeper_scheduled_sync_plan,
)
from src.fantasy.sleeper_persistence import (
    SLEEPER_PERSIST_ACCEPTED,
    SLEEPER_PERSIST_EXISTING_FINAL,
    SLEEPER_PERSIST_FAILED,
    SLEEPER_PERSIST_NO_CHANGE,
)


def _identity() -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id="canary:2026",
        platform="SLEEPER",
        platform_league_id="sleeper-canary",
        season="2026",
    )


def _league(*, request_metadata=None) -> SleeperScheduledLeague:
    return SleeperScheduledLeague(
        identity=_identity(),
        league_family_id="canary-family",
        family_display_name="Canary League",
        season_display_name="Canary League 2026",
        registration_created_at_ms=1_000,
        request_metadata=request_metadata,
    )


def _state() -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="sleeper-canary",
        name="Canary League",
        season="2026",
        status="in_season",
        team_count=10,
        current_platform_user_id="me",
        my_platform_roster_id="1",
        rules=LeagueRules(
            roster_positions=("QB", "RB", "WR", "BN"),
            scoring_settings={"rec": 1},
            waiver_budget=100,
        ),
        managers=(
            Manager(
                platform_user_id="me",
                display_name="Owner",
                team_name="Canary",
                is_owner=True,
            ),
        ),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=("p1",),
                starters=("p1",),
                reserve=(),
                taxi=(),
                settings={},
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _latest_payload(
    snapshot_id: str,
    *,
    fingerprint: str | None = None,
) -> tuple[dict, str]:
    snapshot = FantasySnapshot(snapshot_id, _state(), ())
    actual_fingerprint = persistence_content_fingerprint(snapshot)
    return (
        {
            "found": True,
            "record": {
                "snapshot_id": snapshot_id,
                "league_season_id": "canary:2026",
                "content_fingerprint": (
                    actual_fingerprint if fingerprint is None else fingerprint
                ),
                "observed_at_ms": 2_000,
                "accepted_at_ms": 2_000,
                "provider_status": "HEALTHY",
                "rules_ready": True,
                "draft_ready": True,
                "ownership_ready": True,
                "normalized_state": serialize_fantasy_snapshot(snapshot),
                "source_metadata": {
                    "provider": "SLEEPER",
                    "transaction_round": 1,
                },
            },
        },
        actual_fingerprint,
    )


class ReadbackClient:
    def __init__(self, *, sync_payload, snapshot_payload) -> None:
        self.sync_payload = sync_payload
        self.snapshot_payload = snapshot_payload
        self.calls = []

    def read_sync_run(self, sync_run_id: str):
        self.calls.append(("read_sync_run", sync_run_id))
        return self.sync_payload

    def read_latest_snapshot(self, league_season_id: str):
        self.calls.append(("read_latest_snapshot", league_season_id))
        return self.snapshot_payload


def _runtime_result(
    *,
    mode: str = SLEEPER_PERSIST_ACCEPTED,
    accepted_snapshot_id: str = "snapshot-canary",
    fingerprint: str,
    run_result_present: bool = True,
):
    plan = build_sleeper_scheduled_sync_plan(
        (
            SleeperScheduledLeague(
                identity=_identity(),
                league_family_id="canary-family",
                family_display_name="Canary League",
                season_display_name="Canary League 2026",
                registration_created_at_ms=1_000,
                request_metadata={
                    "execution_mode": "CANARY",
                    "canary_version": 1,
                },
            ),
        ),
        scheduled_at_ms=2_000,
        schedule_name=FANTASY_SINGLE_LEAGUE_CANARY_SCHEDULE_NAME,
    )
    run_result = (
        None
        if not run_result_present
        else SimpleNamespace(
            mode=mode,
            accepted_snapshot_id=accepted_snapshot_id,
            current_content_fingerprint=fingerprint,
        )
    )
    outcome = SimpleNamespace(spec=plan.specs[0], result=run_result)
    return SimpleNamespace(
        ready=True,
        batch_id=plan.batch_id,
        scheduled=SimpleNamespace(
            plan=plan,
            result=SimpleNamespace(leagues=(outcome,)),
        ),
    )


def _sync_payload(sync_run_id: str, snapshot_id: str) -> dict:
    return {
        "found": True,
        "record": {
            "sync_run_id": sync_run_id,
            "league_season_id": "canary:2026",
            "status": "COMPLETED",
            "accepted_snapshot_id": snapshot_id,
        },
    }


@pytest.mark.parametrize("mode", [SLEEPER_PERSIST_ACCEPTED, SLEEPER_PERSIST_NO_CHANGE])
def test_canary_verifies_sync_and_exact_persisted_content(monkeypatch, mode):
    snapshot_payload, fingerprint = _latest_payload("snapshot-canary")
    runtime_result = _runtime_result(mode=mode, fingerprint=fingerprint)
    sync_id = runtime_result.scheduled.plan.sync_run_ids[0]
    client = ReadbackClient(
        sync_payload=_sync_payload(sync_id, "snapshot-canary"),
        snapshot_payload=snapshot_payload,
    )
    captured = {}

    def fake_runtime(reader, client_arg, leagues, **kwargs):
        captured["reader"] = reader
        captured["client"] = client_arg
        captured["leagues"] = tuple(leagues)
        captured["kwargs"] = kwargs
        return runtime_result

    monkeypatch.setattr(
        canary,
        "run_handshake_gated_scheduled_sleeper_sync",
        fake_runtime,
    )

    reader = object()
    result = run_single_league_persistence_canary(
        reader,
        client,
        _league(request_metadata={"operator": "test"}),
        canary_at_ms=2_000,
        current_user_id="me",
    )

    assert result.ready is True
    assert result.mode == mode
    assert result.readback_verified is True
    assert result.accepted_snapshot_id == "snapshot-canary"
    assert result.content_fingerprint == fingerprint
    assert captured["reader"] is reader
    assert captured["client"] is client
    assert len(captured["leagues"]) == 1
    assert captured["leagues"][0].request_metadata == {
        "operator": "test",
        "execution_mode": "CANARY",
        "canary_version": FANTASY_SINGLE_LEAGUE_CANARY_VERSION,
    }
    assert captured["kwargs"] == {
        "scheduled_at_ms": 2_000,
        "current_user_id": "me",
        "schedule_name": FANTASY_SINGLE_LEAGUE_CANARY_SCHEDULE_NAME,
    }
    assert client.calls == [
        ("read_sync_run", sync_id),
        ("read_latest_snapshot", "canary:2026"),
    ]


def test_canary_fingerprint_mismatch_fails_without_retry(monkeypatch):
    snapshot_payload, actual_fingerprint = _latest_payload("snapshot-canary")
    expected_fingerprint = "f" * 64
    assert expected_fingerprint != actual_fingerprint
    runtime_result = _runtime_result(fingerprint=expected_fingerprint)
    sync_id = runtime_result.scheduled.plan.sync_run_ids[0]
    client = ReadbackClient(
        sync_payload=_sync_payload(sync_id, "snapshot-canary"),
        snapshot_payload=snapshot_payload,
    )
    monkeypatch.setattr(
        canary,
        "run_handshake_gated_scheduled_sleeper_sync",
        lambda *args, **kwargs: runtime_result,
    )

    with pytest.raises(FantasySingleLeagueCanaryError) as captured:
        run_single_league_persistence_canary(
            object(),
            client,
            _league(),
            canary_at_ms=2_000,
            current_user_id="me",
        )

    assert captured.value.stage == "SNAPSHOT_READBACK"
    assert captured.value.write_may_have_committed is True
    assert client.calls == [
        ("read_sync_run", sync_id),
        ("read_latest_snapshot", "canary:2026"),
    ]


def test_canary_sync_readback_mismatch_stops_before_snapshot_read(monkeypatch):
    snapshot_payload, fingerprint = _latest_payload("snapshot-canary")
    runtime_result = _runtime_result(fingerprint=fingerprint)
    sync_id = runtime_result.scheduled.plan.sync_run_ids[0]
    client = ReadbackClient(
        sync_payload={
            "found": True,
            "record": {
                "sync_run_id": sync_id,
                "league_season_id": "canary:2026",
                "status": "STARTED",
                "accepted_snapshot_id": None,
            },
        },
        snapshot_payload=snapshot_payload,
    )
    monkeypatch.setattr(
        canary,
        "run_handshake_gated_scheduled_sleeper_sync",
        lambda *args, **kwargs: runtime_result,
    )

    with pytest.raises(FantasySingleLeagueCanaryError) as captured:
        run_single_league_persistence_canary(
            object(),
            client,
            _league(),
            canary_at_ms=2_000,
            current_user_id="me",
        )

    assert captured.value.stage == "SYNC_READBACK"
    assert captured.value.write_may_have_committed is True
    assert client.calls == [("read_sync_run", sync_id)]


@pytest.mark.parametrize(
    ("mode", "stage", "may_have_committed"),
    [
        (SLEEPER_PERSIST_EXISTING_FINAL, "CANARY_SLOT", False),
        (SLEEPER_PERSIST_FAILED, "PERSISTENCE_RESULT", True),
    ],
)
def test_canary_rejects_nonfresh_or_failed_persistence_result(
    monkeypatch,
    mode,
    stage,
    may_have_committed,
):
    snapshot_payload, fingerprint = _latest_payload("snapshot-canary")
    runtime_result = _runtime_result(mode=mode, fingerprint=fingerprint)
    client = ReadbackClient(
        sync_payload={},
        snapshot_payload=snapshot_payload,
    )
    monkeypatch.setattr(
        canary,
        "run_handshake_gated_scheduled_sleeper_sync",
        lambda *args, **kwargs: runtime_result,
    )

    with pytest.raises(FantasySingleLeagueCanaryError) as captured:
        run_single_league_persistence_canary(
            object(),
            client,
            _league(),
            canary_at_ms=2_000,
            current_user_id="me",
        )

    assert captured.value.stage == stage
    assert captured.value.write_may_have_committed is may_have_committed
    assert client.calls == []


def test_canary_rejects_unresolved_multi_league_outcome(monkeypatch):
    snapshot_payload, fingerprint = _latest_payload("snapshot-canary")
    runtime_result = _runtime_result(
        fingerprint=fingerprint,
        run_result_present=False,
    )
    client = ReadbackClient(sync_payload={}, snapshot_payload=snapshot_payload)
    monkeypatch.setattr(
        canary,
        "run_handshake_gated_scheduled_sleeper_sync",
        lambda *args, **kwargs: runtime_result,
    )

    with pytest.raises(FantasySingleLeagueCanaryError) as captured:
        run_single_league_persistence_canary(
            object(),
            client,
            _league(),
            canary_at_ms=2_000,
            current_user_id="me",
        )

    assert captured.value.stage == "PERSISTENCE_RESULT"
    assert captured.value.write_may_have_committed is True
    assert client.calls == []


def test_canary_reserved_metadata_fails_before_runtime_execution(monkeypatch):
    called = False

    def fake_runtime(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("runtime must not execute")

    monkeypatch.setattr(
        canary,
        "run_handshake_gated_scheduled_sleeper_sync",
        fake_runtime,
    )

    with pytest.raises(ValueError, match="cannot predefine"):
        run_single_league_persistence_canary(
            object(),
            object(),
            _league(request_metadata={"execution_mode": "OTHER"}),
            canary_at_ms=2_000,
            current_user_id="me",
        )

    assert called is False


def test_canary_safe_summary_is_bounded_and_contains_verification_identity():
    snapshot_payload, fingerprint = _latest_payload("snapshot-canary")
    runtime_result = _runtime_result(fingerprint=fingerprint)
    result = FantasySingleLeagueCanaryResult(
        runtime=runtime_result,
        sync_run_id="sync-canary",
        accepted_snapshot_id="snapshot-canary",
        content_fingerprint=fingerprint,
        mode=SLEEPER_PERSIST_ACCEPTED,
    )

    assert result.safe_summary() == {
        "ready": True,
        "canary_version": 1,
        "mode": "ACCEPTED",
        "readback_verified": True,
        "batch_id": runtime_result.batch_id,
        "sync_run_id": "sync-canary",
        "accepted_snapshot_id": "snapshot-canary",
        "content_fingerprint": fingerprint,
    }


def test_public_package_exports_canary_contract():
    import src.fantasy as fantasy

    assert (
        fantasy.FANTASY_SINGLE_LEAGUE_CANARY_VERSION
        == FANTASY_SINGLE_LEAGUE_CANARY_VERSION
    )
    assert fantasy.FantasySingleLeagueCanaryError is FantasySingleLeagueCanaryError
    assert fantasy.FantasySingleLeagueCanaryResult is FantasySingleLeagueCanaryResult
    assert (
        fantasy.run_single_league_persistence_canary
        is run_single_league_persistence_canary
    )


def _canary_env() -> dict[str, str]:
    return {
        "FANTASY_CANARY_CONFIRM": FANTASY_SINGLE_LEAGUE_CANARY_CONFIRMATION,
        "FANTASY_CANARY_LEAGUE_SEASON_ID": "canary:2026",
        "FANTASY_CANARY_PLATFORM_LEAGUE_ID": "sleeper-canary",
        "FANTASY_CANARY_SEASON": "2026",
        "FANTASY_CANARY_LEAGUE_FAMILY_ID": "canary-family",
        "FANTASY_CANARY_FAMILY_DISPLAY_NAME": "Canary League",
        "FANTASY_CANARY_SEASON_DISPLAY_NAME": "Canary League 2026",
        "FANTASY_CANARY_REGISTRATION_CREATED_AT_MS": "1000",
        "FANTASY_CANARY_AT_MS": "2000",
        "FANTASY_CANARY_CURRENT_USER_ID": "me",
        "FANTASY_PERSISTENCE_URL": "https://fantasy.example/v1/fantasy/persistence",
        "FANTASY_PERSISTENCE_TOKEN": "x" * 40,
    }


def test_canary_env_config_requires_explicit_real_write_confirmation():
    env = _canary_env()
    env["FANTASY_CANARY_CONFIRM"] = "NO"

    with pytest.raises(ValueError, match="explicitly authorize"):
        FantasySingleLeagueCanaryConfig.from_env(env)


def test_canary_env_config_builds_exact_one_league_identity():
    config = FantasySingleLeagueCanaryConfig.from_env(_canary_env())

    assert config.league.identity == _identity()
    assert config.league.request_metadata == {"operator_entrypoint": "ENV_CANARY"}
    assert config.canary_at_ms == 2_000
    assert config.current_user_id == "me"


def test_canary_env_runner_validates_all_config_before_opening_network_clients(
    monkeypatch,
):
    env = _canary_env()
    env["FANTASY_CANARY_AT_MS"] = "999"
    sleeper_opened = False
    persistence_opened = False

    class SleeperShouldNotOpen:
        def __init__(self):
            nonlocal sleeper_opened
            sleeper_opened = True

    class PersistenceShouldNotOpen:
        def __init__(self, config):
            nonlocal persistence_opened
            persistence_opened = True

    monkeypatch.setattr(canary, "SleeperClient", SleeperShouldNotOpen)
    monkeypatch.setattr(
        canary,
        "FantasyPersistenceHttpClient",
        PersistenceShouldNotOpen,
    )

    with pytest.raises(ValueError, match="cannot follow"):
        run_single_league_persistence_canary_from_env(environ=env)

    assert sleeper_opened is False
    assert persistence_opened is False


def test_canary_env_runner_uses_explicit_clients_and_one_canary_call(monkeypatch):
    env = _canary_env()
    reader = object()
    client = object()
    captured = {}
    sentinel = SimpleNamespace(safe_summary=lambda: {"ready": True})

    class SleeperContext:
        def __enter__(self):
            return reader

        def __exit__(self, exc_type, exc, tb):
            return None

    class PersistenceContext:
        def __init__(self, config):
            captured["endpoint"] = config.endpoint
            captured["token"] = config.token

        def __enter__(self):
            return client

        def __exit__(self, exc_type, exc, tb):
            return None

    def fake_canary(reader_arg, client_arg, league, **kwargs):
        captured["reader"] = reader_arg
        captured["client"] = client_arg
        captured["league"] = league
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(canary, "SleeperClient", SleeperContext)
    monkeypatch.setattr(canary, "FantasyPersistenceHttpClient", PersistenceContext)
    monkeypatch.setattr(canary, "run_single_league_persistence_canary", fake_canary)

    result = run_single_league_persistence_canary_from_env(environ=env)

    assert result is sentinel
    assert captured["reader"] is reader
    assert captured["client"] is client
    assert captured["league"].identity == _identity()
    assert captured["kwargs"] == {
        "canary_at_ms": 2_000,
        "current_user_id": "me",
    }
    assert captured["endpoint"] == env["FANTASY_PERSISTENCE_URL"]
    assert captured["token"] == env["FANTASY_PERSISTENCE_TOKEN"]


def _load_canary_script_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "run_fantasy_hq_single_league_canary.py"
    )
    spec = importlib.util.spec_from_file_location("fantasy_canary_script_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_canary_operator_command_failure_is_sanitized(monkeypatch, capsys):
    module = _load_canary_script_module()
    private = "secret token and endpoint details"

    def fail():
        raise FantasySingleLeagueCanaryError(
            private,
            stage="SNAPSHOT_READBACK",
            write_may_have_committed=True,
        )

    monkeypatch.setattr(
        module,
        "run_single_league_persistence_canary_from_env",
        fail,
    )

    assert module.main() == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert payload == {
        "ready": False,
        "error_type": "FantasySingleLeagueCanaryError",
        "stage": "SNAPSHOT_READBACK",
        "write_may_have_committed": True,
    }
    assert private not in captured.err
    assert captured.out == ""


def test_canary_operator_command_success_prints_only_safe_summary(monkeypatch, capsys):
    module = _load_canary_script_module()
    summary = {
        "ready": True,
        "canary_version": 1,
        "mode": "ACCEPTED",
        "readback_verified": True,
        "batch_id": "batch",
        "sync_run_id": "sync",
        "accepted_snapshot_id": "snapshot",
        "content_fingerprint": "f" * 64,
    }
    monkeypatch.setattr(
        module,
        "run_single_league_persistence_canary_from_env",
        lambda: SimpleNamespace(safe_summary=lambda: summary),
    )

    assert module.main() == 0
    captured = capsys.readouterr()

    assert json.loads(captured.out) == summary
    assert captured.err == ""
