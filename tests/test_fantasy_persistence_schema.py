from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "0001_fantasy_hq_persistence.sql"
)

EXPECTED_TABLES = {
    "fantasy_league_families",
    "fantasy_league_seasons",
    "fantasy_state_snapshots",
    "fantasy_change_events",
    "fantasy_sync_runs",
    "football_entities",
    "football_external_ids",
    "football_identity_review_events",
}


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
    return connection


def _insert_family(
    connection: sqlite3.Connection,
    *,
    family_id: str = "family-1",
    name: str = "Papa Johns",
) -> None:
    connection.execute(
        """
        INSERT INTO fantasy_league_families (
            league_family_id, display_name, created_at_ms
        ) VALUES (?, ?, ?)
        """,
        (family_id, name, 1_000),
    )


def _insert_season(
    connection: sqlite3.Connection,
    *,
    season_id: str = "season-1",
    family_id: str = "family-1",
    platform: str = "sleeper",
    platform_league_id: str = "league-123",
    season: str = "2026",
    name: str = "Papa Johns",
) -> None:
    connection.execute(
        """
        INSERT INTO fantasy_league_seasons (
            league_season_id,
            league_family_id,
            platform,
            platform_league_id,
            season,
            display_name,
            created_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            season_id,
            family_id,
            platform,
            platform_league_id,
            season,
            name,
            1_000,
        ),
    )


def _insert_snapshot(
    connection: sqlite3.Connection,
    *,
    snapshot_id: str,
    season_id: str = "season-1",
    fingerprint: str = "content-a",
    observed_at_ms: int = 2_000,
) -> None:
    connection.execute(
        """
        INSERT INTO fantasy_state_snapshots (
            snapshot_id,
            league_season_id,
            content_fingerprint,
            observed_at_ms,
            accepted_at_ms,
            provider_status,
            rules_ready,
            draft_ready,
            ownership_ready,
            normalized_state_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            season_id,
            fingerprint,
            observed_at_ms,
            observed_at_ms,
            "in_season",
            1,
            1,
            1,
            "{}",
        ),
    )


def _seed_primary_league(connection: sqlite3.Connection) -> None:
    _insert_family(connection)
    _insert_season(connection)


def _insert_event(
    connection: sqlite3.Connection,
    *,
    event_fingerprint: str = "event-1",
    season_id: str = "season-1",
    platform: str = "sleeper",
    platform_league_id: str = "league-123",
    season: str = "2026",
    before_snapshot_id: str = "snapshot-before",
    after_snapshot_id: str = "snapshot-after",
) -> None:
    connection.execute(
        """
        INSERT INTO fantasy_change_events (
            event_fingerprint,
            league_season_id,
            event_type,
            platform,
            platform_league_id,
            season,
            before_snapshot_id,
            after_snapshot_id,
            platform_roster_id,
            platform_player_id,
            before_value_json,
            after_value_json,
            source_transaction_ids_json,
            reason_codes_json,
            derived_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_fingerprint,
            season_id,
            "PLAYER_ADDED",
            platform,
            platform_league_id,
            season,
            before_snapshot_id,
            after_snapshot_id,
            "roster-1",
            "player-1",
            '{"owner_roster_id": null}',
            '{"owner_roster_id": "roster-1"}',
            '["transaction-1"]',
            '["OWNERSHIP_CHANGED"]',
            3_000,
        ),
    )


def test_first_migration_creates_expected_storage_contract() -> None:
    connection = _database()
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }

    assert EXPECTED_TABLES <= tables
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)


def test_snapshot_identity_is_distinct_from_content_fingerprint() -> None:
    connection = _database()
    _seed_primary_league(connection)

    _insert_snapshot(
        connection,
        snapshot_id="snapshot-before",
        fingerprint="same-content",
        observed_at_ms=2_000,
    )
    _insert_snapshot(
        connection,
        snapshot_id="snapshot-after",
        fingerprint="same-content",
        observed_at_ms=3_000,
    )

    stored = connection.execute(
        """
        SELECT snapshot_id, content_fingerprint
        FROM fantasy_state_snapshots
        ORDER BY observed_at_ms
        """
    ).fetchall()
    assert stored == [
        ("snapshot-before", "same-content"),
        ("snapshot-after", "same-content"),
    ]

    with pytest.raises(sqlite3.IntegrityError):
        _insert_snapshot(
            connection,
            snapshot_id="snapshot-after",
            fingerprint="different-content",
            observed_at_ms=4_000,
        )


def test_change_event_is_bound_to_exact_snapshot_pair_and_is_idempotent() -> None:
    connection = _database()
    _seed_primary_league(connection)
    _insert_snapshot(connection, snapshot_id="snapshot-before", observed_at_ms=2_000)
    _insert_snapshot(connection, snapshot_id="snapshot-after", observed_at_ms=3_000)

    _insert_event(connection)

    with pytest.raises(sqlite3.IntegrityError):
        _insert_event(connection)

    with pytest.raises(sqlite3.IntegrityError):
        _insert_event(
            connection,
            event_fingerprint="same-snapshot-event",
            before_snapshot_id="snapshot-after",
            after_snapshot_id="snapshot-after",
        )


def test_change_event_cannot_cross_league_seasons_or_spoof_provider_identity() -> None:
    connection = _database()
    _seed_primary_league(connection)
    _insert_snapshot(connection, snapshot_id="snapshot-before", observed_at_ms=2_000)
    _insert_snapshot(connection, snapshot_id="snapshot-after", observed_at_ms=3_000)

    _insert_family(connection, family_id="family-2", name="Mitey Mites")
    _insert_season(
        connection,
        season_id="season-2",
        family_id="family-2",
        platform="sleeper",
        platform_league_id="league-456",
        name="Mitey Mites",
    )
    _insert_snapshot(
        connection,
        snapshot_id="snapshot-other-league",
        season_id="season-2",
        observed_at_ms=3_000,
    )

    with pytest.raises(sqlite3.IntegrityError):
        _insert_event(
            connection,
            event_fingerprint="cross-season-event",
            after_snapshot_id="snapshot-other-league",
        )

    with pytest.raises(sqlite3.IntegrityError):
        _insert_event(
            connection,
            event_fingerprint="spoofed-provider-event",
            platform_league_id="wrong-league-id",
        )


def test_sync_run_can_reference_only_an_accepted_snapshot_from_its_season() -> None:
    connection = _database()
    _seed_primary_league(connection)
    _insert_snapshot(connection, snapshot_id="snapshot-accepted", observed_at_ms=2_000)

    connection.execute(
        """
        INSERT INTO fantasy_sync_runs (
            sync_run_id,
            league_season_id,
            platform,
            platform_league_id,
            season,
            started_at_ms,
            completed_at_ms,
            status,
            accepted_snapshot_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "sync-1",
            "season-1",
            "sleeper",
            "league-123",
            "2026",
            1_900,
            2_100,
            "SUCCEEDED",
            "snapshot-accepted",
        ),
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO fantasy_sync_runs (
                sync_run_id,
                league_season_id,
                platform,
                platform_league_id,
                season,
                started_at_ms,
                status,
                accepted_snapshot_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "sync-2",
                "season-1",
                "sleeper",
                "league-123",
                "2026",
                2_200,
                "SUCCEEDED",
                "missing-snapshot",
            ),
        )


def test_external_identity_can_gain_gsis_later_without_changing_propwar_entity() -> None:
    connection = _database()
    connection.execute(
        """
        INSERT INTO football_entities (
            propwar_entity_id,
            entity_type,
            canonical_name,
            position,
            nfl_team,
            created_at_ms,
            updated_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("player-rookie-1", "PLAYER", "Example Rookie", "WR", "IND", 1_000, 1_000),
    )

    connection.execute(
        """
        INSERT INTO football_external_ids (
            external_identity_id,
            propwar_entity_id,
            provider,
            provider_scope,
            external_id,
            linked_at_ms,
            verification_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "identity-sleeper-1",
            "player-rookie-1",
            "sleeper",
            "",
            "sleeper-rookie-1",
            1_100,
            "PROVIDER_EXACT_ID",
        ),
    )
    connection.execute(
        """
        INSERT INTO football_external_ids (
            external_identity_id,
            propwar_entity_id,
            provider,
            provider_scope,
            external_id,
            linked_at_ms,
            verification_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "identity-gsis-1",
            "player-rookie-1",
            "gsis",
            "",
            "00-0039999",
            2_000,
            "VERIFIED_CROSSWALK",
        ),
    )

    providers = connection.execute(
        """
        SELECT provider, external_id
        FROM football_external_ids
        WHERE propwar_entity_id = ?
        ORDER BY provider
        """,
        ("player-rookie-1",),
    ).fetchall()
    assert providers == [
        ("gsis", "00-0039999"),
        ("sleeper", "sleeper-rookie-1"),
    ]


def test_external_ids_are_one_to_one_inside_provider_scope() -> None:
    connection = _database()
    for entity_id, name in (("player-1", "Player One"), ("player-2", "Player Two")):
        connection.execute(
            """
            INSERT INTO football_entities (
                propwar_entity_id,
                entity_type,
                canonical_name,
                created_at_ms,
                updated_at_ms
            ) VALUES (?, 'PLAYER', ?, 1000, 1000)
            """,
            (entity_id, name),
        )

    connection.execute(
        """
        INSERT INTO football_external_ids (
            external_identity_id,
            propwar_entity_id,
            provider,
            provider_scope,
            external_id,
            linked_at_ms,
            verification_method
        ) VALUES ('identity-1', 'player-1', 'yahoo', '2026', 'nfl.p.123', 1000, 'OAUTH_PROVIDER_ID')
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO football_external_ids (
                external_identity_id,
                propwar_entity_id,
                provider,
                provider_scope,
                external_id,
                linked_at_ms,
                verification_method
            ) VALUES ('identity-2', 'player-2', 'yahoo', '2026', 'nfl.p.123', 1000, 'OAUTH_PROVIDER_ID')
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO football_external_ids (
                external_identity_id,
                propwar_entity_id,
                provider,
                provider_scope,
                external_id,
                linked_at_ms,
                verification_method
            ) VALUES ('identity-3', 'player-1', 'yahoo', '2026', 'nfl.p.999', 1000, 'OAUTH_PROVIDER_ID')
            """
        )

    connection.execute(
        """
        INSERT INTO football_external_ids (
            external_identity_id,
            propwar_entity_id,
            provider,
            provider_scope,
            external_id,
            linked_at_ms,
            verification_method
        ) VALUES ('identity-4', 'player-1', 'yahoo', '2027', 'nfl.p.999', 2000, 'OAUTH_PROVIDER_ID')
        """
    )


def test_identity_review_history_exists_before_or_after_an_accepted_link() -> None:
    connection = _database()
    connection.execute(
        """
        INSERT INTO football_entities (
            propwar_entity_id,
            entity_type,
            canonical_name,
            created_at_ms,
            updated_at_ms
        ) VALUES ('player-1', 'PLAYER', 'Player One', 1000, 1000)
        """
    )

    connection.execute(
        """
        INSERT INTO football_identity_review_events (
            identity_review_event_id,
            provider,
            provider_scope,
            external_id,
            candidate_propwar_entity_id,
            decision,
            reason_codes_json,
            created_at_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "review-1",
            "sleeper",
            "",
            "sleeper-player-1",
            "player-1",
            "REVIEW_REQUIRED",
            '["MISSING_GSIS_CROSSWALK"]',
            1_000,
        ),
    )

    assert connection.execute(
        "SELECT decision FROM football_identity_review_events WHERE identity_review_event_id = 'review-1'"
    ).fetchone() == ("REVIEW_REQUIRED",)


def test_audit_history_is_restrictive_not_cascading() -> None:
    connection = _database()
    _seed_primary_league(connection)
    _insert_snapshot(connection, snapshot_id="snapshot-before", observed_at_ms=2_000)
    _insert_snapshot(connection, snapshot_id="snapshot-after", observed_at_ms=3_000)
    _insert_event(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "DELETE FROM fantasy_state_snapshots WHERE snapshot_id = 'snapshot-after'"
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "DELETE FROM fantasy_league_seasons WHERE league_season_id = 'season-1'"
        )
