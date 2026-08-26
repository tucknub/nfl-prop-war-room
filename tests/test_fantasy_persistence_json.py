from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "0001_fantasy_hq_persistence.sql"
)


def _database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(MIGRATION_PATH.read_text(encoding="utf-8"))
    return connection


def test_json_columns_reject_malformed_payloads() -> None:
    connection = _database()

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO fantasy_league_families (
                league_family_id,
                display_name,
                created_at_ms,
                metadata_json
            ) VALUES ('family-1', 'League One', 1000, 'not-json')
            """
        )

    connection.execute(
        """
        INSERT INTO fantasy_league_families (
            league_family_id,
            display_name,
            created_at_ms
        ) VALUES ('family-1', 'League One', 1000)
        """
    )
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
        ) VALUES ('season-1', 'family-1', 'sleeper', 'league-1', '2026', 'League One', 1000)
        """
    )

    with pytest.raises(sqlite3.IntegrityError):
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
            ) VALUES (
                'snapshot-1', 'season-1', 'fingerprint-1', 2000, 2000,
                'in_season', 1, 1, 1, 'not-json'
            )
            """
        )


def test_text_primary_keys_explicitly_reject_null_ids() -> None:
    connection = _database()

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO fantasy_league_families (
                league_family_id,
                display_name,
                created_at_ms
            ) VALUES (NULL, 'League One', 1000)
            """
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO football_entities (
                propwar_entity_id,
                entity_type,
                canonical_name,
                created_at_ms,
                updated_at_ms
            ) VALUES (NULL, 'PLAYER', 'Player One', 1000, 1000)
            """
        )


def test_existing_gsis_player_id_can_remain_the_propwar_entity_id() -> None:
    connection = _database()
    existing_player_id = "00-0031234"

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
        ) VALUES (?, 'PLAYER', 'Existing Player', 'WR', 'IND', 1000, 1000)
        """,
        (existing_player_id,),
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
        ) VALUES (?, ?, 'gsis', '', ?, 1000, 'EXISTING_PRODUCTION_PLAYER_ID')
        """,
        (f"gsis:{existing_player_id}", existing_player_id, existing_player_id),
    )

    stored = connection.execute(
        """
        SELECT e.propwar_entity_id, x.provider, x.external_id
        FROM football_entities AS e
        JOIN football_external_ids AS x
          ON x.propwar_entity_id = e.propwar_entity_id
        WHERE e.propwar_entity_id = ?
        """,
        (existing_player_id,),
    ).fetchone()

    assert stored == (existing_player_id, "gsis", existing_player_id)


def test_accepted_snapshot_change_event_and_identity_review_are_append_only() -> None:
    connection = _database()
    connection.execute(
        """
        INSERT INTO fantasy_league_families (
            league_family_id, display_name, created_at_ms
        ) VALUES ('family-1', 'League One', 1000)
        """
    )
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
        ) VALUES ('season-1', 'family-1', 'sleeper', 'league-1', '2026', 'League One', 1000)
        """
    )
    for snapshot_id, fingerprint, observed_at_ms in (
        ('snapshot-before', 'content-before', 2000),
        ('snapshot-after', 'content-after', 3000),
    ):
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
            ) VALUES (?, 'season-1', ?, ?, ?, 'in_season', 1, 1, 1, '{}')
            """,
            (snapshot_id, fingerprint, observed_at_ms, observed_at_ms),
        )

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
            derived_at_ms
        ) VALUES (
            'event-1', 'season-1', 'PLAYER_ADDED', 'sleeper', 'league-1', '2026',
            'snapshot-before', 'snapshot-after', 3000
        )
        """
    )
    connection.execute(
        """
        INSERT INTO football_identity_review_events (
            identity_review_event_id,
            provider,
            external_id,
            decision,
            created_at_ms
        ) VALUES ('review-1', 'sleeper', 'player-1', 'REVIEW_REQUIRED', 3000)
        """
    )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            "UPDATE fantasy_state_snapshots SET provider_status = 'changed' WHERE snapshot_id = 'snapshot-after'"
        )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            "DELETE FROM fantasy_change_events WHERE event_fingerprint = 'event-1'"
        )

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        connection.execute(
            "UPDATE football_identity_review_events SET decision = 'ACCEPTED' WHERE identity_review_event_id = 'review-1'"
        )
