# Fantasy League HQ — Normalized League State Contract

**Status:** Draft contract; no runtime implementation yet.

## Purpose

Normalize Sleeper and Yahoo league state into one platform-neutral model. The platform API remains authoritative for league facts; PropWar remains authoritative for NFL evidence and interpretation.

## Top-level model

```text
FantasyLeagueState
├── schema_version
├── synced_at_utc
├── source_health
├── league
├── rules
├── managers
├── teams
├── rosters
├── matchup_state
├── standings
├── transactions
└── platform_metadata
```

## league

- `propwar_league_id` — internal stable ID
- `platform`: `SLEEPER | YAHOO`
- `platform_league_id`
- `name`
- `season`
- `season_type`
- `status`
- `team_count`
- `my_platform_user_id`
- `my_platform_team_id` / roster ID
- `previous_platform_league_id` when relevant

Do not infer the user's team by team name. Resolve it through the authenticated/platform user identity and roster/team ownership relationship.

## rules

Store normalized rules plus the raw provider settings object for auditability.

### scoring

- passing yards
- passing TD
- interceptions
- rushing yards
- rushing TD
- receptions
- receiving yards
- receiving TD
- fumbles
- kicking rules
- D/ST rules
- bonuses
- any other provider-defined scoring modifiers

Unknown/custom rules must remain visible in `unmapped_scoring_rules[]`; do not silently drop them.

### roster construction

Ordered starter slots plus roster limits:

- QB
- RB
- WR
- TE
- FLEX variants
- Superflex / OP when present
- K
- D/ST
- IDP positions when present
- bench
- IR/reserve

Retain provider slot order when it matters for mapping starters to lineup positions.

### waivers / transactions

Normalize where available:

- waiver type
- FAAB budget
- waiver priority
- transaction lock settings
- trade deadline/settings
- acquisition limits

## managers

- `platform_user_id`
- `display_name`
- `team_name`
- `avatar` when useful
- commissioner/owner flags where available

## teams

- `platform_team_id`
- `platform_user_id`
- `display_name`
- wins
- losses
- ties
- points for
- points against
- waiver priority when applicable
- FAAB used / remaining when derivable authoritatively

## rosters

Each roster row contains:

- `platform_team_id`
- `platform_player_id`
- `propwar_player_id` when resolved
- `roster_status`: `STARTER | BENCH | IR | TAXI | OTHER`
- `starter_slot` when known
- `ownership_status`
- `identity_status`

The normalized league state must preserve unresolved platform players rather than drop them.

## matchup_state

Per league week:

- `week`
- `matchup_id`
- team IDs
- starters
- current/final points where provided
- custom commissioner points where provided
- matchup status

Fantasy HQ may supplement this with its own evidence/projections, but must distinguish platform-reported points from PropWar-derived estimates.

## standings

Derived from authoritative team/league state; preserve:

- rank
- wins/losses/ties
- points for
- points against where available
- playoff seed when the platform exposes it authoritatively

Do not reverse-engineer hidden tiebreakers unless the league rules are known.

## transactions

Normalize:

- `platform_transaction_id`
- `transaction_type`: `WAIVER | FREE_AGENT | TRADE | COMMISSIONER | OTHER`
- `status`
- `created_at_utc`
- `processed_at_utc`
- involved team IDs
- adds
- drops
- FAAB bid / budget movement when available
- traded draft picks when relevant
- provider metadata/reason

Transaction history is important for future league-specific FAAB intelligence and `What Changed?` events.

## provider-specific facts

### Sleeper

Current official API provides useful league fields including:

- `settings`
- `scoring_settings`
- `roster_positions`
- all league users
- all rosters and starters
- weekly matchups
- transactions, including waiver bid data in applicable transactions
- drafts/picks
- current NFL state
- trending adds/drops

Sleeper IDs should be stored as strings even when they look numeric.

### Yahoo

Yahoo Fantasy Sports API models game, league, team and player resources and private league access requires OAuth. League scoring, roster positions and scoring modifiers are league-context data and should map into this normalized contract.

Yahoo resource keys should be retained exactly as provider identifiers; never derive identity by display name when a Yahoo key exists.

## source_health

Required fields:

- `status`: `FRESH | STALE | PARTIAL | ERROR | NOT_CONNECTED`
- `synced_at_utc`
- `last_successful_sync_at_utc`
- `provider_error_code`
- `provider_error_message`
- `stale_after_seconds`
- `recommendations_requiring_ownership_safe`: boolean

If roster/ownership state is stale or partial, waiver/drop recommendations must be suppressed or visibly downgraded.

## Change-event derivation

Compare the newly normalized state with the previous accepted state and create events only for meaningful differences:

- `PLAYER_ADDED`
- `PLAYER_DROPPED`
- `PLAYER_BECAME_AVAILABLE`
- `STARTER_CHANGED`
- `IR_CHANGED`
- `FAAB_CHANGED`
- `WAIVER_PRIORITY_CHANGED`
- `TRANSACTION_COMPLETED`
- `MATCHUP_CHANGED`
- `STANDINGS_CHANGED`
- `LEAGUE_RULE_CHANGED`

Do not create duplicate history merely because a scheduled sync returned the same state.

## League-specific decision rule

No universal fantasy rank is authoritative across all leagues.

Downstream action is evaluated as:

`Player Evidence + This League's Rules + This League's Ownership + My Roster + Current Matchup/Calendar Context = League-Specific Action`
