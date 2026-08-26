# Fantasy League HQ — D1 Storage Draft

**Status:** Pre-implementation storage design

## Storage boundary

D1 should persist fantasy-platform state, normalized league history, change events, identity mappings, OAuth connection state, and recommendation history.

D1 should **not** become a second copy of all historical NFL PBP/model data. Existing PropWar Python/data pipelines remain the football-data authority.

## Core tables

### `league_families`

One logical recurring fantasy league across seasons.

Suggested fields:

- `league_family_id` primary key
- `name`
- `primary_platform`
- `active`
- `created_at_utc`
- `updated_at_utc`

### `league_seasons`

One platform league instance for one season.

Suggested fields:

- `league_season_id` primary key
- `league_family_id`
- `platform`
- `platform_league_id`
- `season`
- `status`
- `phase`: e.g. `PRE_DRAFT | DRAFTING | IN_SEASON | COMPLETE`
- `team_count`
- `previous_platform_league_id`
- `rules_fingerprint`
- `raw_rules_json`
- `synced_at_utc`
- `last_successful_sync_at_utc`

Unique constraint on `(platform, platform_league_id)`.

### `draft_states`

Persist provider draft configuration separately from league settings.

Suggested fields:

- `league_season_id`
- `platform_draft_id`
- `status`
- `draft_type`
- `start_time_utc`
- `rounds`
- `teams`
- `draft_slots_json`
- `draft_order_json`
- `raw_draft_json`
- `synced_at_utc`

Reason: provider league convenience fields may conflict with the actual draft resource. Verified 2026 FFL example: `league.settings.draft_rounds = 3` while the actual Sleeper draft is 16 rounds.

### `platform_managers`

Stable manager identity at the provider level.

- `platform`
- `platform_user_id`
- latest display name
- latest team-name metadata
- first seen / last seen

Do not treat seasonal roster IDs as stable manager identities.

### `league_teams`

One manager/team within one league season.

- `league_season_id`
- `platform_team_id` / roster ID
- `platform_user_id`
- display/team name snapshot
- wins/losses/ties
- points for/against
- waiver priority
- FAAB used / remaining

### `football_entities`

Immutable shared identity rows used to connect fantasy ownership, current NFL evidence, historical PropWar evidence, and market rows.

Suggested fields:

- `propwar_entity_id` primary key — opaque and immutable
- `entity_type`: `PLAYER | TEAM_DEFENSE`
- `display_name`
- `current_team`
- `position`
- `identity_status`
- `created_at_utc`
- `updated_at_utc`
- `merged_into_entity_id` nullable

`propwar_entity_id` must not be an external provider ID. A player may exist before GSIS/Yahoo is available; adding those IDs later must not re-key league/draft/recommendation history.

Existing PropWar Python tables may continue to use GSIS-backed `player_id`. The entity registry bridges to those validated tables instead of forcing a migration of historical NFL/model artifacts.

### `player_external_ids`

External IDs/aliases attached to `football_entities`.

Suggested fields:

- `propwar_entity_id`
- `provider`: e.g. `GSIS | PFR | SLEEPER | YAHOO | SPORTRADAR | FANTASYDATA | ESPN | MARKET_VENDOR`
- `provider_player_id`
- `verification_status`
- `evidence_source`
- `first_seen_at_utc`
- `last_seen_at_utc`
- `verified_at_utc`
- `superseded_at_utc` nullable

Unique on `(provider, provider_player_id)` for active mappings.

A provider alias must not silently move between entities. Conflicts enter review.

### `identity_review_events`

Audit corrections/promotions rather than overwriting their history.

Suggested fields:

- `identity_event_id`
- `propwar_entity_id`
- `event_type`: e.g. `CREATED_PROVISIONAL | VERIFIED_NFL_ID | ALIAS_ADDED | CONFLICT_FOUND | ENTITY_MERGED`
- `old_status`
- `new_status`
- `evidence_json`
- `created_at_utc`

A 2026 rookie may begin as `PROVISIONAL_PROVIDER_ENTITY`. If a safe PropWar/nflverse/GSIS bridge becomes available later, attach the new external ID and promote the same entity rather than creating a replacement row.

### `league_roster_players`

Current accepted ownership state.

- `league_season_id`
- `platform_team_id`
- `platform_player_id`
- `propwar_entity_id` nullable while unresolved
- `roster_status`
- `starter_slot`
- `identity_status`
- `updated_at_utc`

Do not populate a league-wide free-agent pool simply by taking all NFL players minus `league_roster_players` while the league phase is `PRE_DRAFT` and provider rosters are uninitialized.

A roster row must remain visible even when `propwar_entity_id` is unresolved; do not discard provider ownership facts because NFL identity is not yet bridged.

### `league_transactions`

- provider transaction ID
- league season
- type/status
- created/processed timestamps
- involved teams
- adds/drops
- FAAB details
- draft picks
- raw provider metadata

Unique on provider transaction ID within platform.

Transaction records should attach `propwar_entity_id` when safely resolved but preserve original platform player IDs for audit/replay.

### `league_matchups`

Persist weekly/final platform matchup state separately from PropWar projections.

### `league_state_snapshots`

Compact state fingerprints and optional normalized snapshots used for change detection. Do not retain duplicate full snapshots when the meaningful state hash is unchanged.

### `fantasy_change_events`

Examples:

- `PLAYER_ADDED`
- `PLAYER_DROPPED`
- `PLAYER_BECAME_AVAILABLE`
- `STARTER_CHANGED`
- `IR_CHANGED`
- `FAAB_CHANGED`
- `TRANSACTION_COMPLETED`
- `LEAGUE_RULE_CHANGED`
- `DRAFT_STATE_CHANGED`
- `OWNERSHIP_INITIALIZED`

Pre-draft → post-draft initialization should create `OWNERSHIP_INITIALIZED` once; it should not create thousands of fake `PLAYER_ADDED` or `PLAYER_BECAME_AVAILABLE` events merely because rosters went from empty placeholders to valid draft ownership.

### `fantasy_recommendations`

Persist prospective recommendation records:

- generated timestamp
- league season
- `propwar_entity_id` for relevant player entities
- decision type
- recommendation/action
- reason codes
- evidence snapshot/reference
- rules fingerprint
- Player Evidence schema/model/rules versions
- freshness envelope
- later outcome fields

Do not overwrite historical recommendations when the recommendation changes; append a new prospective record.

An identity promotion (for example provisional rookie -> verified GSIS) must not rewrite the entity key stored on an earlier recommendation.

### `sync_runs`

- platform
- league season
- started/completed timestamps
- status
- rows/resources fetched
- source health
- error code/message

### `oauth_connections`

Yahoo connection state only; never expose raw token data through the owner API.

Refresh-token material must be encrypted at rest and mutable for token rotation.

## Current vs historical NFL data

Keep in existing PropWar Python/data infrastructure:

- historical PBP;
- weekly NFL stats;
- role-research history;
- feature tables;
- model/backtest artifacts;
- raw/large sportsbook inputs.

D1 may retain compact current Player Evidence references/cache rows if that reduces API/UI latency, but Python remains the calculation authority.

## Identity resolution/readiness

Identity readiness is separate from league/rules/ownership readiness.

Examples:

- `VERIFIED_NFL_ID` — safe to join current/historical NFL evidence.
- `VERIFIED_EXTERNAL_BRIDGE` — safe according to reviewed bridge rules.
- `PROVISIONAL_PROVIDER_ENTITY` — safe for provider roster/draft display, but NFL role/market joins remain blocked.
- `REVIEW_REQUIRED` / `UNRESOLVED` — preserve platform facts, suppress joins requiring canonical NFL evidence.

Team defenses use one canonical `TEAM_DEFENSE` entity per NFL team rather than pseudo-player identifiers.

## Pre-draft readiness state

Rules readiness and ownership readiness are separate.

Example statuses:

- `RULES_READY = true` after current scoring/roster rules are verified.
- `DRAFT_READY = true` after provider draft resource is verified.
- `OWNERSHIP_READY = false` while a pre-draft league has empty/uninitialized rosters.
- `RECOMMENDATION_READY` depends on the specific recommendation family: draft/keeper preparation may be allowed while waiver/drop/start-sit remain blocked.

This prevents an empty pre-draft roster state from being mistaken for a valid free-agent market.
