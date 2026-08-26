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
