from __future__ import annotations

import json

import httpx
import pytest

from src.fantasy.persistence_http import (
    MAX_COMMAND_BODY_BYTES,
    FantasyPersistenceClientConfig,
    FantasyPersistenceHttpClient,
    FantasyPersistenceProtocolError,
    FantasyPersistenceRejected,
    FantasyPersistenceTransportError,
    UnsafeFantasyPersistenceTransport,
)


ENDPOINT = "https://fantasy-persistence.example/v1/fantasy/persistence"
TOKEN = "fantasy-hq-transport-test-token-0123456789"


def _sync_start_command() -> dict:
    return {
        "protocol_version": 1,
        "kind": "SYNC_START",
        "identity": {
            "league_season_id": "ffl:2026",
            "platform": "SLEEPER",
            "platform_league_id": "league-2026",
            "season": "2026",
        },
        "sync_run_id": "sync-1",
        "started_at_ms": 1787760000000,
        "request_metadata_json": "{}",
    }


def _registration_command() -> dict:
    return {
        "protocol_version": 1,
        "kind": "LEAGUE_SEASON_UPSERT",
        "identity": {
            "league_season_id": "ffl:2026",
            "platform": "SLEEPER",
            "platform_league_id": "league-2026",
            "season": "2026",
        },
        "league_family_id": "ffl",
        "family_display_name": "Franchise Football League",
        "season_display_name": "Franchise Football League 2026",
        "created_at_ms": 1787760000000,
        "family_metadata_json": "{}",
        "season_metadata_json": "{}",
    }


def _client(handler, **config_overrides):
    config = FantasyPersistenceClientConfig(
        endpoint=config_overrides.pop("endpoint", ENDPOINT),
        token=config_overrides.pop("token", TOKEN),
        **config_overrides,
    )
    return FantasyPersistenceHttpClient(
        config,
        transport=httpx.MockTransport(handler),
    )


def _success_payload(command: dict) -> dict:
    payload = {
        "ok": True,
        "protocol_version": 1,
        "kind": command["kind"],
        "results": [{"statement_index": 0, "changes": 1}],
    }
    if command["kind"] == "LEAGUE_SEASON_UPSERT":
        payload["league_season_id"] = command["identity"]["league_season_id"]
    else:
        payload["sync_run_id"] = command["sync_run_id"]
    return payload


def test_send_posts_exactly_once_with_bearer_json_and_no_redirect_retry():
    command = _sync_start_command()
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "POST"
        assert str(request.url) == ENDPOINT
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert request.headers["content-type"] == "application/json"
        assert request.headers["accept"] == "application/json"
        assert request.headers["user-agent"] == "propwar-fantasy-hq-persistence/1"
        assert json.loads(request.content.decode("utf-8")) == command
        return httpx.Response(
            200,
            json=_success_payload(command),
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        payload = client.send(command)

    assert payload["ok"] is True
    assert payload["sync_run_id"] == "sync-1"
    assert len(seen) == 1


def test_registration_response_must_match_requested_league_season_id():
    command = _registration_command()

    def handler(request: httpx.Request) -> httpx.Response:
        payload = _success_payload(command)
        payload["league_season_id"] = "wrong:2026"
        return httpx.Response(
            200,
            json=payload,
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        with pytest.raises(
            FantasyPersistenceProtocolError,
            match="identifier does not match request",
        ):
            client.send(command)


def test_sync_response_must_match_requested_kind_and_sync_run_id():
    command = _sync_start_command()

    for mutation in ("kind", "sync_run_id"):
        def handler(request: httpx.Request, mutation=mutation) -> httpx.Response:
            payload = _success_payload(command)
            if mutation == "kind":
                payload["kind"] = "SYNC_FAILED"
            else:
                payload["sync_run_id"] = "wrong-run"
            return httpx.Response(
                200,
                json=payload,
                headers={"content-type": "application/json"},
            )

        with _client(handler) as client:
            with pytest.raises(FantasyPersistenceProtocolError):
                client.send(command)


def test_worker_rejection_is_typed_and_exception_text_does_not_echo_worker_message():
    secret_message = "internal detail that should not be in exception text"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json={
                "ok": False,
                "error": {"code": "UNAUTHORIZED", "message": secret_message},
            },
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        with pytest.raises(FantasyPersistenceRejected) as captured:
            client.send(_sync_start_command())

    error = captured.value
    assert error.status_code == 401
    assert error.code == "UNAUTHORIZED"
    assert error.worker_message == secret_message
    assert secret_message not in str(error)
    assert TOKEN not in str(error)


def test_redirect_is_not_followed_and_only_one_write_request_is_made():
    command = _sync_start_command()
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(
            307,
            json={
                "ok": False,
                "error": {"code": "REDIRECT", "message": "do not follow"},
            },
            headers={
                "content-type": "application/json",
                "location": "https://other.example/v1/fantasy/persistence",
            },
        )

    with _client(handler) as client:
        with pytest.raises(FantasyPersistenceRejected) as captured:
            client.send(command)

    assert captured.value.status_code == 307
    assert count == 1


def test_network_failure_is_not_retried_or_allowed_to_leak_token():
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        raise httpx.ConnectError("network down", request=request)

    with _client(handler) as client:
        with pytest.raises(FantasyPersistenceTransportError) as captured:
            client.send(_sync_start_command())

    assert count == 1
    assert TOKEN not in str(captured.value)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://fantasy-persistence.example/v1/fantasy/persistence",
        "https://fantasy-persistence.example/wrong",
        "https://user:pass@fantasy-persistence.example/v1/fantasy/persistence",
        "https://fantasy-persistence.example/v1/fantasy/persistence?q=1",
        "https://fantasy-persistence.example/v1/fantasy/persistence#fragment",
    ],
)
def test_config_rejects_unsafe_or_noncanonical_endpoints(endpoint):
    with pytest.raises(UnsafeFantasyPersistenceTransport):
        FantasyPersistenceClientConfig(endpoint=endpoint, token=TOKEN)


def test_config_rejects_weak_or_whitespace_tokens():
    for token in ("short", "x" * 31, ("x" * 32) + " ", ("x" * 16) + "\n" + ("y" * 16)):
        with pytest.raises(UnsafeFantasyPersistenceTransport):
            FantasyPersistenceClientConfig(endpoint=ENDPOINT, token=token)


def test_from_env_requires_both_values_and_never_embeds_secret_defaults(monkeypatch):
    monkeypatch.delenv("FANTASY_PERSISTENCE_URL", raising=False)
    monkeypatch.delenv("FANTASY_PERSISTENCE_TOKEN", raising=False)
    with pytest.raises(UnsafeFantasyPersistenceTransport, match="FANTASY_PERSISTENCE_URL"):
        FantasyPersistenceClientConfig.from_env()

    monkeypatch.setenv("FANTASY_PERSISTENCE_URL", ENDPOINT)
    with pytest.raises(UnsafeFantasyPersistenceTransport, match="FANTASY_PERSISTENCE_TOKEN"):
        FantasyPersistenceClientConfig.from_env()

    monkeypatch.setenv("FANTASY_PERSISTENCE_TOKEN", TOKEN)
    config = FantasyPersistenceClientConfig.from_env()
    assert config.endpoint == ENDPOINT
    assert config.token == TOKEN


def test_transport_rejects_unsupported_protocol_kind_and_non_json_body_before_network():
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500)

    bad_commands = [
        {"protocol_version": 2, "kind": "SYNC_START", "sync_run_id": "sync-1"},
        {"protocol_version": 1, "kind": "DELETE_EVERYTHING"},
        {
            "protocol_version": 1,
            "kind": "SYNC_START",
            "sync_run_id": "sync-1",
            "bad": float("nan"),
        },
    ]
    with _client(handler) as client:
        for command in bad_commands:
            with pytest.raises(UnsafeFantasyPersistenceTransport):
                client.send(command)
    assert requests == 0


def test_transport_enforces_worker_request_size_ceiling_before_network():
    requests = 0
    command = _sync_start_command()
    command["padding"] = "x" * MAX_COMMAND_BODY_BYTES

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500)

    with _client(handler) as client:
        with pytest.raises(
            UnsafeFantasyPersistenceTransport,
            match="512 KiB",
        ):
            client.send(command)
    assert requests == 0


def test_response_must_be_small_json_utf8_object_with_v1_success_shape():
    command = _sync_start_command()
    responses = [
        httpx.Response(200, content=b"ok", headers={"content-type": "text/plain"}),
        httpx.Response(
            200,
            content=b"\xff",
            headers={"content-type": "application/json"},
        ),
        httpx.Response(
            200,
            content=b"not-json",
            headers={"content-type": "application/json"},
        ),
        httpx.Response(
            200,
            json=["not", "object"],
            headers={"content-type": "application/json"},
        ),
        httpx.Response(
            200,
            json={"ok": True, "protocol_version": 2, "kind": "SYNC_START", "sync_run_id": "sync-1", "results": []},
            headers={"content-type": "application/json"},
        ),
    ]

    for response in responses:
        with _client(lambda request, response=response: response) as client:
            with pytest.raises(FantasyPersistenceProtocolError):
                client.send(command)


def test_streamed_response_size_limit_is_enforced():
    command = _sync_start_command()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x" * 1025,
            headers={"content-type": "application/json"},
        )

    with _client(handler, max_response_body_bytes=1024) as client:
        with pytest.raises(FantasyPersistenceProtocolError, match="size limit"):
            client.send(command)


def test_health_uses_public_health_path_without_authorization_and_validates_v1():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "GET"
        assert str(request.url) == "https://fantasy-persistence.example/health"
        assert "authorization" not in request.headers
        return httpx.Response(
            200,
            json={"ok": True, "status": "ok", "protocol_version": 1},
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        payload = client.health()

    assert payload == {"ok": True, "status": "ok", "protocol_version": 1}
    assert len(seen) == 1


def test_health_rejects_wrong_protocol_version():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"ok": True, "status": "ok", "protocol_version": 2},
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        with pytest.raises(FantasyPersistenceProtocolError, match="protocol version"):
            client.health()
