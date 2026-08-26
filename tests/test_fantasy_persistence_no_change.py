from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

import httpx
import pytest

from src.fantasy.changes import FantasySnapshot
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.persistence import (
    LeagueSeasonIdentity,
    build_no_change_sync_statement,
    persistence_content_fingerprint,
)
from src.fantasy.persistence_http import (
    FantasyPersistenceClientConfig,
    FantasyPersistenceHttpClient,
    FantasyPersistenceTransportError,
)
from src.fantasy.persistence_lifecycle import (
    PERSISTENCE_COMPLETED,
    PERSISTENCE_REGISTERED,
    PERSISTENCE_SOURCE_EXISTING,
    PERSISTENCE_SOURCE_RECOVERY,
    PERSISTENCE_SOURCE_WRITE,
    PERSISTENCE_STARTED,
    FantasyPersistenceCoordinator,
    FantasyPersistenceLifecycleOutcome,
    FantasyPersistenceOutcomeUnknown,
    FantasyPersistenceStateConflict,
    FantasySyncSession,
)
from src.fantasy.persistence_protocol import (
    JAVASCRIPT_MAX_SAFE_INTEGER,
    SYNC_NO_CHANGE,
    UnsafePersistenceCommand,
    build_no_change_sync_command,
)
from src.fantasy.persistence_rehydrate import PersistedFantasySnapshot


ENDPOINT = "https://fantasy-persistence.example/v1/fantasy/persistence"
TOKEN = "fantasy-hq-no-change-test-token-0123456789"


def _identity() -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id="ffl:2026",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
    )


def _state(*, name: str = "Franchise Football League") -> FantasyLeagueState:
    return FantasyLeagueState(
        platform="SLEEPER",
        platform_league_id="league-2026",
        name=name,
        season="2026",
        status="in_season",
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
        managers=(),
        rosters=(
            Roster(
                platform_roster_id="1",
                platform_user_id="me",
                players=("player-1",),
                starters=("player-1",),
                reserve=(),
                taxi=(),
                settings={},
            ),
        ),
        rules_ready=True,
        draft_ready=True,
        ownership_ready=True,
    )


def _previous() -> PersistedFantasySnapshot:
    snapshot = FantasySnapshot("snap-prev", _state())
    return PersistedFantasySnapshot(
        snapshot=snapshot,
        league_season_id="ffl:2026",
        content_fingerprint=persistence_content_fingerprint(snapshot),
        observed_at_ms=100,
        accepted_at_ms=110,
        provider_status="HEALTHY",
        source_metadata={"source": "test"},
    )


def _current(*, name: str = "Franchise Football League") -> FantasySnapshot:
    return FantasySnapshot("snap-current", _state(name=name))


def _sync_record(status: str = PERSISTENCE_STARTED, **overrides: Any) -> dict[str, Any]:
    row = {
        "sync_run_id": "sync-2",
        "league_season_id": "ffl:2026",
        "platform": "SLEEPER",
        "platform_league_id": "league-2026",
        "season": "2026",
        "started_at_ms": 200,
        "completed_at_ms": None,
        "status": status,
        "accepted_snapshot_id": None,
        "error_code": None,
    }
    row.update(overrides)
    return row


def _read(record):
    return {"found": record is not None, "record": record}


def _session() -> FantasySyncSession:
    return FantasySyncSession(
        identity=_identity(),
        sync_run_id="sync-2",
        registration=FantasyPersistenceLifecycleOutcome(
            stage="REGISTRATION",
            state=PERSISTENCE_REGISTERED,
            source=PERSISTENCE_SOURCE_EXISTING,
            identifier="ffl:2026",
        ),
        sync=FantasyPersistenceLifecycleOutcome(
            stage="SYNC_START",
            state=PERSISTENCE_STARTED,
            source=PERSISTENCE_SOURCE_EXISTING,
            identifier="sync-2",
        ),
    )


@dataclass
class FakeTransport:
    sync_reads: list[Any] = field(default_factory=list)
    send_effects: list[Any] = field(default_factory=list)
    calls: list[tuple[str, str]] = field(default_factory=list)

    def read_sync_run(self, sync_run_id: str):
        self.calls.append(("read_sync", sync_run_id))
        if not self.sync_reads:
            raise AssertionError("unexpected sync read")
        effect = self.sync_reads.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect

    def read_league_season(self, league_season_id: str):
        raise AssertionError("unexpected league read")

    def send(self, command):
        kind = str(command["kind"])
        self.calls.append(("send", kind))
        if self.send_effects:
            effect = self.send_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return effect
        return {"ok": True}


def test_no_change_statement_is_one_constrained_update():
    previous = _previous()
    statement = build_no_change_sync_statement(
        _identity(),
        sync_run_id="sync-2",
        accepted_snapshot_id=previous.snapshot.snapshot_id,
        content_fingerprint=previous.content_fingerprint,
        completed_at_ms=250,
    )

    assert statement.sql.startswith("UPDATE fantasy_sync_runs")
    assert "INSERT INTO fantasy_state_snapshots" not in statement.sql
    assert "ORDER BY s.accepted_at_ms DESC, s.snapshot_id DESC LIMIT 1" in statement.sql
    assert "s.content_fingerprint = ?" in statement.sql
    assert statement.parameters[2] == "snap-prev"
    assert statement.parameters[-1] == previous.content_fingerprint
    assert statement.expected_affected_rows == 1


def test_no_change_protocol_command_matches_fixed_contract():
    previous = _previous()
    command = build_no_change_sync_command(
        _identity(),
        sync_run_id="sync-2",
        accepted_snapshot_id="snap-prev",
        content_fingerprint=previous.content_fingerprint,
        completed_at_ms=250,
    )

    assert command == {
        "protocol_version": 1,
        "kind": SYNC_NO_CHANGE,
        "identity": {
            "league_season_id": "ffl:2026",
            "platform": "SLEEPER",
            "platform_league_id": "league-2026",
            "season": "2026",
        },
        "sync_run_id": "sync-2",
        "accepted_snapshot_id": "snap-prev",
        "content_fingerprint": previous.content_fingerprint,
        "completed_at_ms": 250,
    }


def test_no_change_protocol_rejects_unsafe_timestamp_and_fingerprint():
    previous = _previous()
    with pytest.raises(UnsafePersistenceCommand, match="JavaScript safe integer"):
        build_no_change_sync_command(
            _identity(),
            sync_run_id="sync-2",
            accepted_snapshot_id="snap-prev",
            content_fingerprint=previous.content_fingerprint,
            completed_at_ms=JAVASCRIPT_MAX_SAFE_INTEGER + 1,
        )

    with pytest.raises(ValueError, match="SHA-256"):
        build_no_change_sync_command(
            _identity(),
            sync_run_id="sync-2",
            accepted_snapshot_id="snap-prev",
            content_fingerprint="not-a-fingerprint",
            completed_at_ms=250,
        )


def test_commit_no_change_directly_reuses_previous_snapshot():
    transport = FakeTransport(sync_reads=[_read(_sync_record())])
    outcome = FantasyPersistenceCoordinator(transport).commit_no_change(
        _session(),
        previous=_previous(),
        current_snapshot=_current(),
        completed_at_ms=250,
    )

    assert outcome.state == PERSISTENCE_COMPLETED
    assert outcome.source == PERSISTENCE_SOURCE_WRITE
    assert outcome.accepted_snapshot_id == "snap-prev"
    assert transport.calls == [
        ("read_sync", "sync-2"),
        ("send", SYNC_NO_CHANGE),
    ]


def test_commit_no_change_rejects_any_full_persistence_content_change_before_network():
    transport = FakeTransport()
    with pytest.raises(
        FantasyPersistenceStateConflict,
        match="requires a new accepted snapshot",
    ):
        FantasyPersistenceCoordinator(transport).commit_no_change(
            _session(),
            previous=_previous(),
            current_snapshot=_current(name="Changed Name"),
            completed_at_ms=250,
        )
    assert transport.calls == []


def test_commit_no_change_rejects_inconsistent_previous_fingerprint():
    previous = replace(_previous(), content_fingerprint="a" * 64)
    transport = FakeTransport()
    with pytest.raises(
        FantasyPersistenceStateConflict,
        match="internally inconsistent",
    ):
        FantasyPersistenceCoordinator(transport).commit_no_change(
            _session(),
            previous=previous,
            current_snapshot=_current(),
            completed_at_ms=250,
        )
    assert transport.calls == []


def test_commit_no_change_is_idempotent_only_for_same_accepted_snapshot():
    same = FakeTransport(
        sync_reads=[
            _read(
                _sync_record(
                    PERSISTENCE_COMPLETED,
                    completed_at_ms=250,
                    accepted_snapshot_id="snap-prev",
                )
            )
        ]
    )
    outcome = FantasyPersistenceCoordinator(same).commit_no_change(
        _session(),
        previous=_previous(),
        current_snapshot=_current(),
        completed_at_ms=250,
    )
    assert outcome.source == PERSISTENCE_SOURCE_EXISTING
    assert not any(call[0] == "send" for call in same.calls)

    different = FakeTransport(
        sync_reads=[
            _read(
                _sync_record(
                    PERSISTENCE_COMPLETED,
                    completed_at_ms=250,
                    accepted_snapshot_id="other",
                )
            )
        ]
    )
    with pytest.raises(
        FantasyPersistenceStateConflict,
        match="different accepted snapshot",
    ):
        FantasyPersistenceCoordinator(different).commit_no_change(
            _session(),
            previous=_previous(),
            current_snapshot=_current(),
            completed_at_ms=250,
        )


def test_ambiguous_no_change_recovers_exact_completed_snapshot_without_retry():
    transport = FakeTransport(
        sync_reads=[
            _read(_sync_record()),
            _read(
                _sync_record(
                    PERSISTENCE_COMPLETED,
                    completed_at_ms=250,
                    accepted_snapshot_id="snap-prev",
                )
            ),
        ],
        send_effects=[FantasyPersistenceTransportError("reset")],
    )
    outcome = FantasyPersistenceCoordinator(transport).commit_no_change(
        _session(),
        previous=_previous(),
        current_snapshot=_current(),
        completed_at_ms=250,
    )

    assert outcome.source == PERSISTENCE_SOURCE_RECOVERY
    assert outcome.accepted_snapshot_id == "snap-prev"
    assert transport.calls.count(("send", SYNC_NO_CHANGE)) == 1


def test_ambiguous_no_change_still_started_is_unknown_and_never_retries():
    transport = FakeTransport(
        sync_reads=[_read(_sync_record()), _read(_sync_record())],
        send_effects=[FantasyPersistenceTransportError("reset")],
    )
    with pytest.raises(FantasyPersistenceOutcomeUnknown) as captured:
        FantasyPersistenceCoordinator(transport).commit_no_change(
            _session(),
            previous=_previous(),
            current_snapshot=_current(),
            completed_at_ms=250,
        )

    assert captured.value.observed_state == PERSISTENCE_STARTED
    assert transport.calls.count(("send", SYNC_NO_CHANGE)) == 1


def test_http_transport_accepts_no_change_command_and_validates_sync_response():
    previous = _previous()
    command = build_no_change_sync_command(
        _identity(),
        sync_run_id="sync-2",
        accepted_snapshot_id="snap-prev",
        content_fingerprint=previous.content_fingerprint,
        completed_at_ms=250,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert b'"kind":"SYNC_NO_CHANGE"' in request.content
        return httpx.Response(
            200,
            json={
                "ok": True,
                "protocol_version": 1,
                "kind": SYNC_NO_CHANGE,
                "sync_run_id": "sync-2",
                "results": [{"statement_index": 0, "changes": 1}],
            },
            headers={"content-type": "application/json"},
        )

    config = FantasyPersistenceClientConfig(endpoint=ENDPOINT, token=TOKEN)
    with FantasyPersistenceHttpClient(
        config,
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.send(command)

    assert result["kind"] == SYNC_NO_CHANGE
    assert result["sync_run_id"] == "sync-2"


def test_public_package_exports_no_change_contract():
    import src.fantasy as fantasy

    assert fantasy.SYNC_NO_CHANGE == SYNC_NO_CHANGE
    assert fantasy.build_no_change_sync_command is build_no_change_sync_command
    assert fantasy.build_no_change_sync_statement is build_no_change_sync_statement
