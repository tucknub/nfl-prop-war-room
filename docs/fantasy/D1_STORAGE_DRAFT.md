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

### `league_roster_players`

Current accepted ownership state.

- `league_season_id`
- `platform_team_id`
- `platform_player_id`
- `propwar_player_id` nullable
- `roster_status`
- `starter_slot`
- `identity_status`
- `updated_at_utc`

Do not populate a league-wide free-agent pool simply by taking all NFL players minus `league_roster_players` while the league phase is `PRE_DRAFT` and provider rosters are uninitialized.

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

### `player_external_ids`

External identity extensions to the existing PropWar player authority.

- `propwar_player_id`
- provider
- provider_player_id
- status
- evidence source
- first_verified_at
- last_verified_at

Unique on `(provider, provider_player_id)`.

### `fantasy_recommendations`

Persist prospective recommendation records:

- generated timestamp
- league season
- player(s)
- decision type
- recommendation/action
- reason codes
- evidence snapshot/reference
- rules fingerprint
- Player Evidence schema/model/rules versions
- freshness envelope
- later outcome fields

Do not overwrite historical recommendations when the recommendation changes; append a new prospective record.

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

## Pre-draft readiness state

Rules readiness and ownership readiness are separate.

Example statuses:

- `RULES_READY = true` after current scoring/roster rules are verified.
- `DRAFT_READY = true` after provider draft resource is verified.
- `OWNERSHIP_READY = false` while a pre-draft league has empty/uninitialized rosters.
- `RECOMMENDATION_READY` depends on the specific recommendation family: draft/keeper preparation may be allowed while waiver/drop/start-sit remain blocked.

This prevents an empty pre-draft roster state from being mistaken for a valid free-agent market.
