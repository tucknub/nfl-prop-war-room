from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import httpx
import pytest

from src.fantasy.persistence_http import (
    FantasyPersistenceClientConfig,
    FantasyPersistenceHttpClient,
    FantasyPersistenceProtocolError,
    FantasyPersistenceRejected,
)
from src.fantasy.runtime_handshake import (
    FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID,
    FANTASY_RUNTIME_HANDSHAKE_VERSION,
    FantasyRuntimeDeploymentHandshakeError,
    FantasyRuntimeDeploymentHandshakeResult,
    run_fantasy_runtime_deployment_handshake,
    run_fantasy_runtime_deployment_handshake_from_env,
)


ENDPOINT = "https://fantasy-persistence.example/v1/fantasy/persistence"
TOKEN = "fantasy-hq-runtime-handshake-token-0123456789"


def _missing_probe_payload() -> dict:
    return {
        "ok": True,
        "protocol_version": 1,
        "kind": "READ_SYNC_RUN",
        "requested_id": FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID,
        "found": False,
        "record": None,
    }


def _http_client(handler):
    config = FantasyPersistenceClientConfig(endpoint=ENDPOINT, token=TOKEN)
    return FantasyPersistenceHttpClient(
        config,
        transport=httpx.MockTransport(handler),
    )


def test_handshake_performs_public_health_then_one_authenticated_read_and_no_write():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/health":
            assert request.method == "GET"
            assert "authorization" not in request.headers
            return httpx.Response(
                200,
                json={"ok": True, "status": "ok", "protocol_version": 1},
                headers={"content-type": "application/json"},
            )

        assert request.method == "GET"
        assert request.url.path == (
            "/v1/fantasy/read/sync-runs/"
            + FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID
        )
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        return httpx.Response(
            200,
            json=_missing_probe_payload(),
            headers={"content-type": "application/json"},
        )

    with _http_client(handler) as client:
        result = run_fantasy_runtime_deployment_handshake(client)

    assert result.ready is True
    assert result.write_enabled is False
    assert result.probe_absent is True
    assert [request.method for request in requests] == ["GET", "GET"]
    assert all(request.method != "POST" for request in requests)


def test_handshake_safe_summary_contains_no_endpoint_token_or_raw_record():
    result = FantasyRuntimeDeploymentHandshakeResult(
        handshake_version=FANTASY_RUNTIME_HANDSHAKE_VERSION,
        protocol_version=1,
        health_ready=True,
        authenticated_read_ready=True,
        probe_absent=True,
    )

    summary = result.safe_summary()
    serialized = json.dumps(summary)

    assert summary["ready"] is True
    assert summary["write_enabled"] is False
    assert TOKEN not in serialized
    assert "fantasy-persistence.example" not in serialized
    assert "record" not in summary


def test_reserved_probe_existing_fails_closed():
    class Client:
        def health(self):
            return {"ok": True, "status": "ok", "protocol_version": 1}

        def read_sync_run(self, sync_run_id: str):
            assert sync_run_id == FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID
            return {
                "ok": True,
                "protocol_version": 1,
                "kind": "READ_SYNC_RUN",
                "requested_id": sync_run_id,
                "found": True,
                "record": {"sync_run_id": sync_run_id},
            }

    with pytest.raises(
        FantasyRuntimeDeploymentHandshakeError,
        match="reserved runtime handshake probe unexpectedly exists",
    ):
        run_fantasy_runtime_deployment_handshake(Client())


def test_handshake_defense_in_depth_rejects_malformed_read_results():
    healthy = {"ok": True, "status": "ok", "protocol_version": 1}
    bad_reads = [
        {},
        {
            "ok": True,
            "protocol_version": 2,
            "kind": "READ_SYNC_RUN",
            "requested_id": FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID,
            "found": False,
            "record": None,
        },
        {
            "ok": True,
            "protocol_version": 1,
            "kind": "WRONG",
            "requested_id": FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID,
            "found": False,
            "record": None,
        },
        {
            "ok": True,
            "protocol_version": 1,
            "kind": "READ_SYNC_RUN",
            "requested_id": "wrong",
            "found": False,
            "record": None,
        },
        {
            "ok": True,
            "protocol_version": 1,
            "kind": "READ_SYNC_RUN",
            "requested_id": FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID,
            "found": "false",
            "record": None,
        },
    ]

    for bad_read in bad_reads:
        class Client:
            def health(self):
                return healthy

            def read_sync_run(self, sync_run_id: str):
                return bad_read

        with pytest.raises(FantasyRuntimeDeploymentHandshakeError):
            run_fantasy_runtime_deployment_handshake(Client())


def test_real_http_client_protocol_and_auth_failures_propagate_typed():
    def wrong_protocol(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True, "status": "ok", "protocol_version": 2},
            headers={"content-type": "application/json"},
        )

    with _http_client(wrong_protocol) as client:
        with pytest.raises(FantasyPersistenceProtocolError):
            run_fantasy_runtime_deployment_handshake(client)

    def unauthorized(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={"ok": True, "status": "ok", "protocol_version": 1},
                headers={"content-type": "application/json"},
            )
        return httpx.Response(
            401,
            json={
                "ok": False,
                "error": {"code": "UNAUTHORIZED", "message": "private detail"},
            },
            headers={"content-type": "application/json"},
        )

    with _http_client(unauthorized) as client:
        with pytest.raises(FantasyPersistenceRejected) as captured:
            run_fantasy_runtime_deployment_handshake(client)
    assert captured.value.status_code == 401
    assert captured.value.code == "UNAUTHORIZED"
    assert TOKEN not in str(captured.value)


def test_from_env_uses_existing_strict_transport_configuration(monkeypatch):
    monkeypatch.setenv("FANTASY_PERSISTENCE_URL", ENDPOINT)
    monkeypatch.setenv("FANTASY_PERSISTENCE_TOKEN", TOKEN)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/health":
            return httpx.Response(
                200,
                json={"ok": True, "status": "ok", "protocol_version": 1},
                headers={"content-type": "application/json"},
            )
        return httpx.Response(
            200,
            json=_missing_probe_payload(),
            headers={"content-type": "application/json"},
        )

    result = run_fantasy_runtime_deployment_handshake_from_env(
        transport=httpx.MockTransport(handler),
    )

    assert result.ready is True
    assert seen == [
        "/health",
        (
            "/v1/fantasy/read/sync-runs/"
            + FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID
        ),
    ]


def test_result_cannot_be_constructed_as_write_enabled_or_unready():
    bad_kwargs = [
        {"health_ready": False},
        {"authenticated_read_ready": False},
        {"probe_absent": False},
        {"write_enabled": True},
        {"handshake_version": 2},
        {"protocol_version": 2},
    ]

    base = {
        "handshake_version": 1,
        "protocol_version": 1,
        "health_ready": True,
        "authenticated_read_ready": True,
        "probe_absent": True,
        "write_enabled": False,
    }
    for mutation in bad_kwargs:
        with pytest.raises(ValueError):
            FantasyRuntimeDeploymentHandshakeResult(**(base | mutation))


def test_public_package_exports_runtime_handshake_contract():
    import src.fantasy as fantasy

    assert fantasy.FANTASY_RUNTIME_HANDSHAKE_VERSION == FANTASY_RUNTIME_HANDSHAKE_VERSION
    assert (
        fantasy.FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID
        == FANTASY_RUNTIME_HANDSHAKE_PROBE_SYNC_RUN_ID
    )
    assert (
        fantasy.FantasyRuntimeDeploymentHandshakeResult
        is FantasyRuntimeDeploymentHandshakeResult
    )
    assert (
        fantasy.run_fantasy_runtime_deployment_handshake
        is run_fantasy_runtime_deployment_handshake
    )
    assert (
        fantasy.run_fantasy_runtime_deployment_handshake_from_env
        is run_fantasy_runtime_deployment_handshake_from_env
    )


def _load_handshake_script_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "check_fantasy_hq_runtime_handshake.py"
    )
    spec = importlib.util.spec_from_file_location("fantasy_handshake_script_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_operator_command_prints_only_sanitized_success_summary(monkeypatch, capsys):
    module = _load_handshake_script_module()
    result = FantasyRuntimeDeploymentHandshakeResult(
        handshake_version=1,
        protocol_version=1,
        health_ready=True,
        authenticated_read_ready=True,
        probe_absent=True,
    )
    monkeypatch.setattr(
        module,
        "run_fantasy_runtime_deployment_handshake_from_env",
        lambda: result,
    )

    assert module.main() == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload == result.safe_summary()
    assert captured.err == ""
    assert TOKEN not in captured.out
    assert ENDPOINT not in captured.out


def test_operator_command_failure_never_prints_exception_message_or_secret(
    monkeypatch,
    capsys,
):
    module = _load_handshake_script_module()
    private_message = f"Worker rejected secret={TOKEN} endpoint={ENDPOINT}"

    def fail():
        raise RuntimeError(private_message)

    monkeypatch.setattr(
        module,
        "run_fantasy_runtime_deployment_handshake_from_env",
        fail,
    )

    assert module.main() == 1
    captured = capsys.readouterr()
    payload = json.loads(captured.err)

    assert payload == {"ready": False, "error_type": "RuntimeError"}
    assert captured.out == ""
    assert private_message not in captured.err
    assert TOKEN not in captured.err
    assert ENDPOINT not in captured.err
