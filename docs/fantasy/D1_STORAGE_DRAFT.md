# Fantasy League HQ — Cloudflare D1 Storage Draft

**Status:** Draft storage design; no database provisioned by this document.

## Boundary

D1 stores compact fantasy-platform state, change history, external identity extensions, connection metadata, and recommendation audit history.

D1 does **not** replace the existing historical NFL/PropWar data warehouse, role-research outputs, feature tables, model artifacts, or large raw sportsbook/NFL source datasets.

## Design rules

- Use migrations from the first database version.
- Prefer `STRICT` tables where practical.
- Enforce foreign keys.
- Store provider IDs as text.
- Store timestamps in UTC ISO-8601 text or a single consistently documented integer epoch representation; do not mix formats in one column family.
- Retain raw provider settings/metadata as JSON text when needed for auditability, while promoting commonly queried fields to typed columns.
- Use state fingerprints to avoid duplicate snapshots/events.
- Never store plaintext Yahoo client secrets or refresh tokens in ordinary tables.

## Candidate tables

### `fantasy_leagues`

- `id` TEXT PRIMARY KEY
- `platform` TEXT NOT NULL
- `platform_league_id` TEXT NOT NULL
- `name` TEXT NOT NULL
- `season` INTEGER NOT NULL
- `status` TEXT
- `team_count` INTEGER
- `my_platform_user_id` TEXT
- `my_platform_team_id` TEXT
- `rules_version` INTEGER NOT NULL DEFAULT 1
- `last_synced_at_utc` TEXT
- `created_at_utc` TEXT NOT NULL
- UNIQUE(`platform`, `platform_league_id`)

### `fantasy_league_rules`

- `league_id` TEXT PRIMARY KEY REFERENCES `fantasy_leagues(id)`
- `scoring_json` TEXT NOT NULL
- `roster_positions_json` TEXT NOT NULL
- `waiver_rules_json` TEXT
- `playoff_rules_json` TEXT
- `raw_provider_settings_json` TEXT
- `unmapped_rules_json` TEXT
- `source_updated_at_utc` TEXT

### `fantasy_managers`

- `league_id` TEXT NOT NULL
- `platform_user_id` TEXT NOT NULL
- `display_name` TEXT
- `team_name` TEXT
- `is_commissioner` INTEGER NOT NULL DEFAULT 0
- PRIMARY KEY (`league_id`, `platform_user_id`)

### `fantasy_teams`

- `league_id` TEXT NOT NULL
- `platform_team_id` TEXT NOT NULL
- `platform_user_id` TEXT
- `wins` INTEGER
- `losses` INTEGER
- `ties` INTEGER
- `points_for` REAL
- `points_against` REAL
- `waiver_priority` INTEGER
- `faab_used` REAL
- `faab_remaining` REAL
- PRIMARY KEY (`league_id`, `platform_team_id`)

### `fantasy_roster_current`

- `league_id` TEXT NOT NULL
- `platform_team_id` TEXT NOT NULL
- `platform_player_id` TEXT NOT NULL
- `propwar_player_id` TEXT
- `roster_status` TEXT NOT NULL
- `starter_slot` TEXT
- `identity_status` TEXT NOT NULL
- `source_updated_at_utc` TEXT
- PRIMARY KEY (`league_id`, `platform_team_id`, `platform_player_id`)

Indexes:

- (`league_id`, `propwar_player_id`)
- (`league_id`, `roster_status`)

### `fantasy_matchups_current`

- `league_id` TEXT NOT NULL
- `week` INTEGER NOT NULL
- `matchup_id` TEXT NOT NULL
- `platform_team_id` TEXT NOT NULL
- `points` REAL
- `custom_points` REAL
- `status` TEXT
- PRIMARY KEY (`league_id`, `week`, `matchup_id`, `platform_team_id`)

### `fantasy_transactions`

- `league_id` TEXT NOT NULL
- `platform_transaction_id` TEXT NOT NULL
- `transaction_type` TEXT NOT NULL
- `status` TEXT
- `created_at_utc` TEXT
- `processed_at_utc` TEXT
- `teams_json` TEXT
- `adds_json` TEXT
- `drops_json` TEXT
- `faab_json` TEXT
- `draft_picks_json` TEXT
- `provider_metadata_json` TEXT
- PRIMARY KEY (`league_id`, `platform_transaction_id`)

### `fantasy_sync_runs`

- `id` TEXT PRIMARY KEY
- `league_id` TEXT NOT NULL
- `started_at_utc` TEXT NOT NULL
- `completed_at_utc` TEXT
- `status` TEXT NOT NULL
- `state_fingerprint` TEXT
- `previous_state_fingerprint` TEXT
- `changed` INTEGER NOT NULL DEFAULT 0
- `provider_http_status` INTEGER
- `error_code` TEXT
- `error_message` TEXT

### `fantasy_change_events`

- `id` TEXT PRIMARY KEY
- `league_id` TEXT NOT NULL
- `event_type` TEXT NOT NULL
- `platform_team_id` TEXT
- `platform_player_id` TEXT
- `propwar_player_id` TEXT
- `occurred_at_utc` TEXT NOT NULL
- `detected_at_utc` TEXT NOT NULL
- `before_json` TEXT
- `after_json` TEXT
- `source_transaction_id` TEXT
- `importance` TEXT
- `dedupe_key` TEXT NOT NULL UNIQUE

### `player_external_identities`

This extends rather than replaces the existing PropWar identity authority.

- `propwar_player_id` TEXT NOT NULL
- `provider` TEXT NOT NULL
- `provider_player_id` TEXT NOT NULL
- `provider_label` TEXT
- `nfl_team_at_verification` TEXT
- `position_at_verification` TEXT
- `status` TEXT NOT NULL
- `first_verified_at_utc` TEXT
- `last_verified_at_utc` TEXT
- `verification_source` TEXT
- PRIMARY KEY (`provider`, `provider_player_id`)
- UNIQUE (`propwar_player_id`, `provider`)

Ambiguous identities should use a separate review queue rather than violate uniqueness assumptions.

### `player_identity_review_queue`

- `id` TEXT PRIMARY KEY
- `provider` TEXT NOT NULL
- `provider_player_id` TEXT
- `provider_label` TEXT
- `candidate_propwar_ids_json` TEXT
- `reason_code` TEXT NOT NULL
- `status` TEXT NOT NULL
- `created_at_utc` TEXT NOT NULL
- `resolved_at_utc` TEXT
- `resolved_propwar_player_id` TEXT

### `fantasy_recommendations`

- `id` TEXT PRIMARY KEY
- `league_id` TEXT NOT NULL
- `week` INTEGER
- `recommendation_type` TEXT NOT NULL
- `propwar_player_id` TEXT
- `comparison_player_id` TEXT
- `action` TEXT NOT NULL
- `generated_at_utc` TEXT NOT NULL
- `expires_at_utc` TEXT
- `evidence_schema_version` INTEGER NOT NULL
- `rules_version` TEXT NOT NULL
- `evidence_json` TEXT NOT NULL
- `reason_codes_json` TEXT NOT NULL
- `source_freshness_json` TEXT NOT NULL
- `recommendation_safe` INTEGER NOT NULL
- `supersedes_recommendation_id` TEXT

Recommendations are append-only for audit purposes. A changed opinion creates a new row referencing the prior recommendation; it does not overwrite the old evidence.

### `fantasy_recommendation_outcomes`

- `recommendation_id` TEXT PRIMARY KEY REFERENCES `fantasy_recommendations(id)`
- `evaluated_at_utc` TEXT NOT NULL
- `outcome_json` TEXT NOT NULL
- `evaluation_version` TEXT NOT NULL

## OAuth / connection storage

### `platform_connections`

Non-secret connection metadata only:

- `id` TEXT PRIMARY KEY
- `platform` TEXT NOT NULL
- `platform_user_id` TEXT
- `status` TEXT NOT NULL
- `connected_at_utc` TEXT
- `last_refresh_at_utc` TEXT
- `reconnect_required` INTEGER NOT NULL DEFAULT 0
- `scopes_json` TEXT

Yahoo refresh-token material should be encrypted before persistence and isolated from ordinary league tables. The encryption key and Yahoo client secret belong in Worker secrets, not in D1 rows or GitHub.

If a future architecture provides a safer dedicated secret/token store with rotation semantics, prefer that over custom token storage.

## Snapshot policy

Do not insert a full duplicate snapshot on every scheduled poll.

Flow:

1. Fetch provider state.
2. Normalize deterministically.
3. Compute state fingerprint.
4. Compare with last accepted fingerprint.
5. If identical, record sync health only.
6. If changed, update current-state tables and emit deterministic change events.

Historical transactions and recommendation rows remain append-only.

## Suggested first migration

The first implementation migration should include only the minimum needed to prove one Sleeper league end-to-end:

- `fantasy_leagues`
- `fantasy_league_rules`
- `fantasy_managers`
- `fantasy_teams`
- `fantasy_roster_current`
- `fantasy_matchups_current`
- `fantasy_transactions`
- `fantasy_sync_runs`
- `fantasy_change_events`
- `player_external_identities`
- `player_identity_review_queue`

Add recommendations only after the league state and identity layer are verified against the source platform.
