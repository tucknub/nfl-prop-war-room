from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.fantasy.changes import FantasySnapshot
from src.fantasy.models import FantasyLeagueState, LeagueRules, Roster
from src.fantasy.persistence import (
    LeagueSeasonIdentity,
    build_unchanged_sync_statement,
    persistence_content_fingerprint,
)
from src.fantasy.persistence_lifecycle import (
    PERSISTENCE_COMPLETED,
    PERSISTENCE_SOURCE_EXISTING,
    PERSISTENCE_SOURCE_RECOVERY,
    PERSISTENCE_SOURCE_WRITE,
    FantasyPersistenceCoordinator,
    FantasyPersistenceLifecycleOutcome,
    FantasyPersistenceOutcomeUnknown,
    FantasyPersistenceStateConflict,
    FantasySyncSession,
)
from src.fantasy.persistence_protocol import (
    FANTASY_PERSISTENCE_PROTOCOL_VERSION,
    SYNC_UNCHANGED,
    UnsafePersistenceCommand,
    build_unchanged_sync_command,
)
from src.fantasy.persistence_rehydrate import PersistedFantasySnapshot
from src.fantasy.persistence_http import FantasyPersistenceTransportError

MIGRATION = Path("migrations/0001_fantasy_hq_persistence.sql")


def _identity() -> LeagueSeasonIdentity:
    return LeagueSeasonIdentity(
        league_season_id="ffl:2026",
        platform="SLEEPER",
        platform_league_id="league-2026",
        season="2026",
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


def _snapshot(snapshot_id: str = "snapshot-1") -> FantasySnapshot:
    return FantasySnapshot(snapshot_id=snapshot_id, league=_state(), transactions=())


def _persisted(snapshot: FantasySnapshot | None = None) -> PersistedFantasySnapshot:
    snapshot = snapshot or _snapshot()
    return PersistedFantasySnapshot(
        snapshot=snapshot,
        league_season_id="ffl:2026",
        content_fingerprint=persistence_content_fingerprint(snapshot),
        observed_at_ms=100,
        accepted_at_ms=110,
        provider_status="HEALTHY",
        source_metadata={},
    )


def _session() -> FantasySyncSession:
    return FantasySyncSession(
        identity=_identity(),
        sync_run_id="sync-new",
        registration=FantasyPersistenceLifecycleOutcome(
            stage="REGISTRATION",
            state="REGISTERED",
            source="EXISTING",
            identifier="ffl:2026",
        ),
        sync=FantasyPersistenceLifecycleOutcome(
            stage="SYNC_START",
            state="STARTED",
            source="EXISTING",
            identifier="sync-new",
        ),
    )


def _sync_record(status: str = "STARTED", **overrides):
    row = {
        "sync_run_id": "sync-new",
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


class FakeTransport:
    def __init__(self, *, sync_reads, send_effects=None):
        self.sync_reads = list(sync_reads)
        self.send_effects = list(send_effects or [])
        self.calls = []

    def read_sync_run(self, sync_run_id):
        self.calls.append(("read_sync", sync_run_id))
        value = self.sync_reads.pop(0)
        if isinstance(value, Exception):
            raise value
        return {"found": value is not None, "record": value}

    def send(self, command):
        self.calls.append(("send", command["kind"]))
        if self.send_effects:
            value = self.send_effects.pop(0)
            if isinstance(value, Exception):
                raise value
            return value
        return {"ok": True}


def _db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(MIGRATION.read_text(encoding="utf-8"))
    db.execute(
        "INSERT INTO fantasy_league_families "
        "(league_family_id, display_name, created_at_ms, metadata_json) "
        "VALUES ('ffl', 'FFL', 1, '{}')"
    )
    db.execute(
        "INSERT INTO fantasy_league_seasons "
        "(league_season_id, league_family_id, platform, platform_league_id, season, "
        "display_name, created_at_ms, metadata_json) "
        "VALUES ('ffl:2026', 'ffl', 'SLEEPER', 'league-2026', '2026', 'FFL 2026', 1, '{}')"
    )
    return db


def _seed_accepted_snapshot(
    db: sqlite3.Connection,
    *,
    snapshot_id: str,
    fingerprint: str,
    accepted_at_ms: int,
    sync_run_id: str,
) -> None:
    db.execute(
        "INSERT INTO fantasy_state_snapshots "
        "(snapshot_id, league_season_id, content_fingerprint, observed_at_ms, accepted_at_ms, "
        "provider_status, rules_ready, draft_ready, ownership_ready, normalized_state_json, "
        "source_metadata_json) VALUES (?, 'ffl:2026', ?, ?, ?, 'HEALTHY', 1, 1, 1, '{}', '{}')",
        (snapshot_id, fingerprint, accepted_at_ms - 1, accepted_at_ms),
    )
    db.execute(
        "INSERT INTO fantasy_sync_runs "
        "(sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, "
        "completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) "
        "VALUES (?, 'ffl:2026', 'SLEEPER', 'league-2026', '2026', ?, ?, 'COMPLETED', ?, NULL, NULL, '{}')",
        (sync_run_id, accepted_at_ms - 2, accepted_at_ms + 1, snapshot_id),
    )


def _seed_started(db: sqlite3.Connection, sync_run_id: str = "sync-new") -> None:
    db.execute(
        "INSERT INTO fantasy_sync_runs "
        "(sync_run_id, league_season_id, platform, platform_league_id, season, started_at_ms, "
        "completed_at_ms, status, accepted_snapshot_id, error_code, error_summary, request_metadata_json) "
        "VALUES (?, 'ffl:2026', 'SLEEPER', 'league-2026', '2026', 200, NULL, 'STARTED', NULL, NULL, NULL, '{}')",
        (sync_run_id,),
    )


def test_python_protocol_builds_narrow_unchanged_command():
    fingerprint = "a" * 64
    command = build_unchanged_sync_command(
        _identity(),
        sync_run_id=" sync-new ",
        completed_at_ms=250,
        accepted_snapshot_id="snapshot-1",
        content_fingerprint=fingerprint,
    )
    assert command == {
        "protocol_version": FANTASY_PERSISTENCE_PROTOCOL_VERSION,
        "kind": SYNC_UNCHANGED,
        "identity": {
            "league_season_id": "ffl:2026",
            "platform": "SLEEPER",
            "platform_league_id": "league-2026",
            "season": "2026",
        },
        "sync_run_id": "sync-new",
        "completed_at_ms": 250,
        "accepted_snapshot_id": "snapshot-1",
        "content_fingerprint": fingerprint,
    }
    assert "sql" not in command


def test_python_protocol_rejects_non_sha256_fingerprint():
    with pytest.raises(UnsafePersistenceCommand, match="SHA-256"):
        build_unchanged_sync_command(
            _identity(),
            sync_run_id="sync-new",
            completed_at_ms=250,
            accepted_snapshot_id="snapshot-1",
            content_fingerprint="not-a-fingerprint",
        )


def test_sql_statement_reuses_only_current_latest_accepted_snapshot():
    db = _db()
    try:
        fingerprint = "a" * 64
        _seed_accepted_snapshot(
            db,
            snapshot_id="snapshot-1",
            fingerprint=fingerprint,
            accepted_at_ms=100,
            sync_run_id="sync-old",
        )
        _seed_started(db)
        statement = build_unchanged_sync_statement(
            _identity(),
            sync_run_id="sync-new",
            completed_at_ms=250,
            accepted_snapshot_id="snapshot-1",
            content_fingerprint=fingerprint,
        )
        result = db.execute(statement.sql, statement.parameters)
        assert result.rowcount == 1
        row = db.execute(
            "SELECT status, accepted_snapshot_id FROM fantasy_sync_runs WHERE sync_run_id='sync-new'"
        ).fetchone()
        assert row == ("COMPLETED", "snapshot-1")
        assert db.execute("SELECT COUNT(*) FROM fantasy_state_snapshots").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM fantasy_change_events").fetchone()[0] == 0
    finally:
        db.close()


def test_sql_statement_rejects_stale_snapshot_after_newer_acceptance():
    db = _db()
    try:
        old_fp = "a" * 64
        new_fp = "b" * 64
        _seed_accepted_snapshot(
            db,
            snapshot_id="snapshot-old",
            fingerprint=old_fp,
            accepted_at_ms=100,
            sync_run_id="sync-old",
        )
        _seed_accepted_snapshot(
            db,
            snapshot_id="snapshot-newer",
            fingerprint=new_fp,
            accepted_at_ms=150,
            sync_run_id="sync-newer",
        )
        _seed_started(db)
        statement = build_unchanged_sync_statement(
            _identity(),
            sync_run_id="sync-new",
            completed_at_ms=250,
            accepted_snapshot_id="snapshot-old",
            content_fingerprint=old_fp,
        )
        result = db.execute(statement.sql, statement.parameters)
        assert result.rowcount == 0
        row = db.execute(
            "SELECT status, accepted_snapshot_id FROM fantasy_sync_runs WHERE sync_run_id='sync-new'"
        ).fetchone()
        assert row == ("STARTED", None)
    finally:
        db.close()


def test_sql_statement_rejects_wrong_content_fingerprint():
    db = _db()
    try:
        _seed_accepted_snapshot(
            db,
            snapshot_id="snapshot-1",
            fingerprint="a" * 64,
            accepted_at_ms=100,
            sync_run_id="sync-old",
        )
        _seed_started(db)
        statement = build_unchanged_sync_statement(
            _identity(),
            sync_run_id="sync-new",
            completed_at_ms=250,
            accepted_snapshot_id="snapshot-1",
            content_fingerprint="b" * 64,
        )
        result = db.execute(statement.sql, statement.parameters)
        assert result.rowcount == 0
    finally:
        db.close()


def test_lifecycle_commits_unchanged_without_new_snapshot():
    previous = _persisted()
    current = FantasySnapshot("observation-new", _state(), ())
    transport = FakeTransport(sync_reads=[_sync_record()])
    outcome = FantasyPersistenceCoordinator(transport).commit_unchanged(
        _session(),
        previous=previous,
        current_snapshot=current,
        completed_at_ms=250,
    )
    assert outcome.state == PERSISTENCE_COMPLETED
    assert outcome.source == PERSISTENCE_SOURCE_WRITE
    assert outcome.accepted_snapshot_id == "snapshot-1"
    assert transport.calls == [
        ("read_sync", "sync-new"),
        ("send", SYNC_UNCHANGED),
    ]


def test_lifecycle_refuses_changed_content_before_write():
    previous = _persisted()
    changed_state = _state()
    changed_state = FantasyLeagueState(
        **{**changed_state.__dict__, "name": "Changed League Name"}
    )
    current = FantasySnapshot("observation-new", changed_state, ())
    transport = FakeTransport(sync_reads=[_sync_record()])
    with pytest.raises(FantasyPersistenceStateConflict, match="content differs"):
        FantasyPersistenceCoordinator(transport).commit_unchanged(
            _session(),
            previous=previous,
            current_snapshot=current,
            completed_at_ms=250,
        )
    assert transport.calls == []


def test_lifecycle_is_idempotent_for_same_existing_accepted_snapshot():
    previous = _persisted()
    current = FantasySnapshot("observation-new", _state(), ())
    transport = FakeTransport(
        sync_reads=[
            _sync_record(
                PERSISTENCE_COMPLETED,
                completed_at_ms=250,
                accepted_snapshot_id="snapshot-1",
            )
        ]
    )
    outcome = FantasyPersistenceCoordinator(transport).commit_unchanged(
        _session(),
        previous=previous,
        current_snapshot=current,
        completed_at_ms=250,
    )
    assert outcome.source == PERSISTENCE_SOURCE_EXISTING
    assert outcome.accepted_snapshot_id == "snapshot-1"
    assert not any(call[0] == "send" for call in transport.calls)


def test_ambiguous_unchanged_write_recovers_exact_completed_snapshot_without_retry():
    previous = _persisted()
    current = FantasySnapshot("observation-new", _state(), ())
    transport = FakeTransport(
        sync_reads=[
            _sync_record(),
            _sync_record(
                PERSISTENCE_COMPLETED,
                completed_at_ms=250,
                accepted_snapshot_id="snapshot-1",
            ),
        ],
        send_effects=[FantasyPersistenceTransportError("reset")],
    )
    outcome = FantasyPersistenceCoordinator(transport).commit_unchanged(
        _session(),
        previous=previous,
        current_snapshot=current,
        completed_at_ms=250,
    )
    assert outcome.source == PERSISTENCE_SOURCE_RECOVERY
    assert transport.calls.count(("send", SYNC_UNCHANGED)) == 1


def test_ambiguous_unchanged_write_remaining_started_is_unknown_without_retry():
    previous = _persisted()
    current = FantasySnapshot("observation-new", _state(), ())
    transport = FakeTransport(
        sync_reads=[_sync_record(), _sync_record()],
        send_effects=[FantasyPersistenceTransportError("reset")],
    )
    with pytest.raises(FantasyPersistenceOutcomeUnknown) as captured:
        FantasyPersistenceCoordinator(transport).commit_unchanged(
            _session(),
            previous=previous,
            current_snapshot=current,
            completed_at_ms=250,
        )
    assert captured.value.stage == SYNC_UNCHANGED
    assert captured.value.observed_state == "STARTED"
    assert transport.calls.count(("send", SYNC_UNCHANGED)) == 1


def test_public_package_exports_unchanged_sync_contract():
    import src.fantasy as fantasy

    assert fantasy.SYNC_UNCHANGED == SYNC_UNCHANGED
    assert fantasy.build_unchanged_sync_command is build_unchanged_sync_command
    assert fantasy.build_unchanged_sync_statement is build_unchanged_sync_statement
