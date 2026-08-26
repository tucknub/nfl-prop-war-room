from __future__ import annotations

import httpx
import pytest

from src.fantasy.persistence_http import (
    MAX_SNAPSHOT_RESPONSE_BODY_BYTES,
    READ_LATEST_SNAPSHOT,
    READ_LEAGUE_SEASON,
    READ_SYNC_RUN,
    FantasyPersistenceClientConfig,
    FantasyPersistenceHttpClient,
    FantasyPersistenceProtocolError,
    FantasyPersistenceTransportError,
    UnsafeFantasyPersistenceTransport,
)


ENDPOINT = "https://fantasy-persistence.example/v1/fantasy/persistence"
TOKEN = "fantasy-hq-read-client-test-token-0123456789"


def _client(handler, **config_overrides):
    config = FantasyPersistenceClientConfig(
        endpoint=ENDPOINT,
        token=TOKEN,
        **config_overrides,
    )
    return FantasyPersistenceHttpClient(
        config,
        transport=httpx.MockTransport(handler),
    )


def _read_payload(kind: str, identifier: str, record):
    return {
        "ok": True,
        "protocol_version": 1,
        "kind": kind,
        "requested_id": identifier,
        "found": record is not None,
        "record": record,
    }


def test_league_season_read_uses_authenticated_canonical_get_path():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.method == "GET"
        assert str(request.url) == (
            "https://fantasy-persistence.example/v1/fantasy/read/"
            "league-seasons/ffl%3A2026"
        )
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert request.headers["accept"] == "application/json"
        assert request.content == b""
        return httpx.Response(
            200,
            json=_read_payload(
                READ_LEAGUE_SEASON,
                "ffl:2026",
                {
                    "league_season_id": "ffl:2026",
                    "league_family_id": "ffl",
                    "platform": "SLEEPER",
                    "platform_league_id": "league-2026",
                    "season": "2026",
                    "display_name": "FFL 2026",
                    "created_at_ms": 100,
                    "metadata": {"verified": True},
                },
            ),
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        result = client.read_league_season("ffl:2026")

    assert result["found"] is True
    assert result["record"]["metadata"] == {"verified": True}
    assert len(seen) == 1


def test_sync_run_missing_is_valid_found_false_and_not_an_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/v1/fantasy/read/sync-runs/sync-404")
        return httpx.Response(
            200,
            json=_read_payload(READ_SYNC_RUN, "sync-404", None),
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        result = client.read_sync_run("sync-404")

    assert result == {
        "ok": True,
        "protocol_version": 1,
        "kind": READ_SYNC_RUN,
        "requested_id": "sync-404",
        "found": False,
        "record": None,
    }


def test_sync_run_response_must_match_requested_identifier():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_read_payload(
                READ_SYNC_RUN,
                "sync-1",
                {
                    "sync_run_id": "other-sync",
                    "league_season_id": "ffl:2026",
                    "status": "STARTED",
                },
            ),
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        with pytest.raises(FantasyPersistenceProtocolError):
            client.read_sync_run("sync-1")


def test_latest_snapshot_validates_identity_state_metadata_and_booleans():
    record = {
        "snapshot_id": "snapshot-1",
        "league_season_id": "ffl:2026",
        "content_fingerprint": "abc",
        "observed_at_ms": 100,
        "accepted_at_ms": 110,
        "provider_status": "OK",
        "rules_ready": True,
        "draft_ready": True,
        "ownership_ready": True,
        "normalized_state": {"league": {"platform": "SLEEPER"}, "transactions": []},
        "source_metadata": {"source": "test"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith(
            "/v1/fantasy/read/league-seasons/ffl%3A2026/latest-snapshot"
        )
        return httpx.Response(
            200,
            json=_read_payload(READ_LATEST_SNAPSHOT, "ffl:2026", record),
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        result = client.read_latest_snapshot("ffl:2026")

    assert result["record"] == record

    mutations = [
        {**record, "league_season_id": "wrong:2026"},
        {**record, "normalized_state": []},
        {**record, "source_metadata": []},
        {**record, "ownership_ready": 1},
    ]
    for mutated in mutations:
        with _client(
            lambda request, mutated=mutated: httpx.Response(
                200,
                json=_read_payload(READ_LATEST_SNAPSHOT, "ffl:2026", mutated),
                headers={"content-type": "application/json"},
            )
        ) as client:
            with pytest.raises(FantasyPersistenceProtocolError):
                client.read_latest_snapshot("ffl:2026")


def test_read_wire_shape_rejects_wrong_kind_id_found_or_record_contract():
    bad_payloads = [
        {
            "ok": True,
            "protocol_version": 1,
            "kind": READ_LEAGUE_SEASON,
            "requested_id": "wrong:2026",
            "found": False,
            "record": None,
        },
        {
            "ok": True,
            "protocol_version": 1,
            "kind": READ_SYNC_RUN,
            "requested_id": "ffl:2026",
            "found": False,
            "record": None,
        },
        {
            "ok": True,
            "protocol_version": 1,
            "kind": READ_LEAGUE_SEASON,
            "requested_id": "ffl:2026",
            "found": "false",
            "record": None,
        },
        {
            "ok": True,
            "protocol_version": 1,
            "kind": READ_LEAGUE_SEASON,
            "requested_id": "ffl:2026",
            "found": False,
            "record": {},
        },
    ]

    for payload in bad_payloads:
        with _client(
            lambda request, payload=payload: httpx.Response(
                200,
                json=payload,
                headers={"content-type": "application/json"},
            )
        ) as client:
            with pytest.raises(FantasyPersistenceProtocolError):
                client.read_league_season("ffl:2026")


def test_read_identifiers_fail_closed_before_network():
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(500)

    invalid = ["", " ffl:2026", "ffl:2026 ", "a/b", "a\\b", "x" * 257, "a\n"]
    with _client(handler) as client:
        for value in invalid:
            with pytest.raises(UnsafeFantasyPersistenceTransport):
                client.read_league_season(value)
    assert requests == 0


def test_read_network_failure_is_one_shot_and_secret_safe():
    requests = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        raise httpx.ReadTimeout("timeout with upstream detail", request=request)

    with _client(handler) as client:
        with pytest.raises(FantasyPersistenceTransportError) as captured:
            client.read_sync_run("sync-1")

    assert requests == 1
    assert TOKEN not in str(captured.value)


def test_latest_snapshot_uses_separate_bounded_response_ceiling():
    assert MAX_SNAPSHOT_RESPONSE_BODY_BYTES > 512 * 1024

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x" * 2049,
            headers={"content-type": "application/json"},
        )

    with _client(handler, max_snapshot_response_body_bytes=2048) as client:
        with pytest.raises(FantasyPersistenceProtocolError, match="size limit"):
            client.read_latest_snapshot("ffl:2026")


def test_snapshot_response_limit_configuration_must_be_positive_integer():
    for value in [0, -1, True, 1.5]:
        with pytest.raises(UnsafeFantasyPersistenceTransport):
            FantasyPersistenceClientConfig(
                endpoint=ENDPOINT,
                token=TOKEN,
                max_snapshot_response_body_bytes=value,
            )


def test_public_package_exports_recovery_read_kinds():
    import src.fantasy as fantasy

    assert fantasy.READ_LEAGUE_SEASON == READ_LEAGUE_SEASON
    assert fantasy.READ_SYNC_RUN == READ_SYNC_RUN
    assert fantasy.READ_LATEST_SNAPSHOT == READ_LATEST_SNAPSHOT
