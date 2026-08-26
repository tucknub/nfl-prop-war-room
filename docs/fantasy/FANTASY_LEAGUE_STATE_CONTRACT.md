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
├── draft_state
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

## Current-season rules authority

**The current platform league object is authoritative for the current season.**

Never inherit lineup, scoring, waiver, playoff, keeper, or transaction settings from a prior-season league merely because the current league is linked through `previous_platform_league_id` or otherwise appears to be a renewal of the same named league.

Cross-season league history exists for comparison and learning only. A renewed league may materially change format between seasons.

Example already verified from Franchise Football League:

- 2025 was Superflex.
- 2026 is 1QB.
- Fantasy HQ must value quarterbacks, roster scarcity, lineup decisions, waivers, and replacement-level players using the 2026 current league settings.

On every accepted league sync:

1. Read the complete current league `scoring_settings`, `roster_positions`, and relevant `settings` from the provider.
2. Normalize them into `rules`.
3. Retain the raw provider settings object for auditability.
4. Compute a deterministic `rules_fingerprint` from the normalized current-season rules.
5. Compare the fingerprint with the previously accepted state for the **same platform league ID and season**.
6. Emit `LEAGUE_RULE_CHANGED` only when the current league's rules actually change; a different prior-season ruleset is historical context, not an error.
7. Recompute league-specific player value and recommendations whenever the accepted current-season rules fingerprint changes.

Historical rules should be stored season-by-season; they must never silently override current rules.

## rules

Store normalized rules plus the raw provider settings object for auditability.

Required rule metadata:

- `rules_fingerprint`
- `rules_source_platform`
- `rules_source_league_id`
- `rules_source_season`
- `rules_synced_at_utc`

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

**Scoring-category presence does not imply roster-position presence.** Providers may retain scoring keys for K, D/ST, IDP, or other categories even when the current league has no corresponding starter/roster slot. Use `roster_positions`/provider roster rules to determine which positions are active in the league. Retain inactive scoring settings for auditability, but do not use them to infer lineup requirements or player value for positions the league does not roster.

Verified 2026 Papa Johns example: raw Sleeper scoring retains kicking and D/ST values, but the league has no K or DEF roster slots.

### roster construction

Ordered starter slots plus roster limits when the **league resource** authoritatively exposes them:

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
- season-long position maximums, if independently exposed as league rules

Retain provider slot order when it matters for mapping starters to lineup positions.

A slot that existed in a prior season but is absent from the current-season provider response must be treated as absent. Do not fill missing current-season positions from historical defaults. For example, a 2025 `SUPER_FLEX` slot must not survive into 2026 if the 2026 `roster_positions` array no longer contains it.

Do not promote a position limit found only in a draft resource into a season-long roster maximum. Draft and league constraints are separate source domains.

### reserve / IR / taxi

Normalize reserve capacity and eligibility explicitly from provider settings when those concepts are not represented directly inside the ordered `roster_positions` array.

Retain separately:

- reserve/IR slot count
- taxi slot count
- eligible statuses (OUT, IR, PUP/NA, suspended, doubtful, etc.) where the provider exposes them
- provider-specific reserve flags

Do not assume `reserve_slots = 1` means generic IR behavior. Eligibility must come from the current provider settings.

Verified Sleeper behavior: current leagues can expose `reserve_slots` in `settings` while the ordered `roster_positions` array contains no explicit `IR` token.

### waivers / transactions

Normalize where available:

- waiver type
- FAAB budget
- waiver priority
- waiver clear period
- transaction lock settings
- trade deadline/settings
- acquisition limits
- season-long position limits only when the league resource authoritatively exposes them

## draft_state

Draft-specific settings must come from the provider's **draft resource**, not from similarly named convenience fields on the league object when a draft resource exists.

Normalize:

- `platform_draft_id`
- `status`
- `type`
- `start_time_utc`
- `rounds`
- `teams`
- draft slot counts by position
- bench rounds/slots
- pick timer
- draft order when assigned
- keeper picks/flags when available
- `enforce_position_limits`
- draft-only `position_limits` by position when present

Reason: provider league settings can contain fields that are not the authoritative current draft configuration, and draft resources can contain constraints that do **not** appear as season-long league rules. Verified 2026 examples:

- FFL league object reports `draft_rounds = 3`, while the actual Sleeper draft resource reports 16 rounds.
- Papa Johns league object also reports `draft_rounds = 3`, while its actual Sleeper draft resource reports 15 rounds.
- Papa Johns draft settings expose `enforce_position_limits = 1` and `position_limit_qb = 3`; the current league settings do not independently expose a verified season-long QB maximum. Therefore QB=3 is normalized as a draft constraint only.

Fantasy HQ must use the provider draft resource for draft-specific decisions and must not silently copy draft-only constraints into `rules`.

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
- `propwar_entity_id` when resolved
- `roster_status`: `STARTER | BENCH | IR | TAXI | OTHER`
- `starter_slot` when known
- `ownership_status`
- `identity_status`

The normalized league state must preserve unresolved platform players rather than drop them.

### Pre-draft ownership guard

A pre-draft league with empty rosters is **not** a valid free-agent pool.

If league/draft status is `pre_draft` (or provider equivalent) and roster player lists are empty/uninitialized:

- do not classify every unrostered NFL player as `AVAILABLE`;
- set ownership state to `PRE_DRAFT_UNASSIGNED` where appropriate;
- suppress Waiver Radar, drop recommendations, lineup decisions, and ownership-driven alerts;
- permit draft/keeper preparation features that explicitly operate before roster assignment;
- re-evaluate recommendation readiness after keeper assignment/draft completion or once authoritative roster ownership exists.

Both verified 2026 Sleeper leagues currently satisfy this guard: FFL has 10 empty rosters and Papa Johns has 12 empty rosters while each league is `pre_draft`.

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

For renewed Sleeper leagues, `previous_league_id` is history linkage only. It must not be used to inherit current scoring or roster settings.

For draft configuration, use `/league/<league_id>/drafts` and the corresponding draft object rather than assuming `league.settings.draft_rounds` represents the live draft length.

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

If current-season rules cannot be retrieved, Fantasy HQ must not substitute a prior-season ruleset for recommendations. The league may be shown with `RULES_UNAVAILABLE`, but league-specific valuation must fail closed until current rules are verified.

Pre-draft empty ownership is a distinct state from a healthy in-season free-agent pool and must not set `recommendations_requiring_ownership_safe = true`.

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
- `DRAFT_STATE_CHANGED`
- `OWNERSHIP_INITIALIZED`

Do not create duplicate history merely because a scheduled sync returned the same state.

Draft-only changes should create/update `DRAFT_STATE_CHANGED`; they should not create `LEAGUE_RULE_CHANGED` unless the league resource itself also changed.

## League-specific decision rule

No universal fantasy rank is authoritative across all leagues.

Downstream action is evaluated as:

`Player Evidence + This League's Current Rules + This League's Ownership + My Roster + Current Matchup/Calendar Context = League-Specific Action`
