# Fantasy League HQ — Player Evidence Contract

**Status:** Draft contract; no runtime implementation yet.

## Purpose

Define one shared player-evidence object that can be consumed by Fantasy League HQ, Role Shock, Deep Prop, and later owner tools without each surface rebuilding player identity or NFL evidence independently.

The contract is evidence-first. Missing or unresolved evidence is explicit; it is never silently treated as neutral.

## Canonical key

`propwar_player_id`

The canonical PropWar identity should remain anchored to the existing NFL identity authority (currently GSIS-backed where available). External platform/provider identifiers extend that identity rather than replace it.

## Contract

```text
PlayerEvidence
├── schema_version
├── generated_at_utc
├── as_of_utc
├── identity
├── historical_role
├── current_role
├── role_change
├── current_context
├── market_evidence
└── quality
```

### identity

Required:

- `propwar_player_id`
- `player_name`
- `position`
- `nfl_team`
- `identity_status`: `RESOLVED | REVIEW_REQUIRED | UNRESOLVED`

External IDs when known:

- `gsis_id`
- `pfr_id`
- `sleeper_player_id`
- `yahoo_player_key`
- `sportradar_id`
- `fantasydata_id`
- `provider_ids` object for reviewed market/vendor identifiers

Rules:

- Never auto-resolve an ambiguous duplicate name by name alone.
- Team-qualified aliases may assist matching but may not override a conflicting authoritative ID.
- Provider aliases should retain source + first/last verified timestamps.
- Sleeper's player payload may expose candidate cross-provider fields including `sportradar_id`, `fantasy_data_id`, `espn_id`, and `yahoo_id`. Treat these as high-value crosswalk evidence when populated, but validate them before promotion to `RESOLVED`; never assume every external ID field is complete or current merely because Sleeper returned it.

### historical_role

Per supported role family:

- `role_family`
- `baseline_share`
- `baseline_raw_opportunities`
- `baseline_team_opportunities`
- `baseline_games`
- `baseline_start_season_week`
- `baseline_end_season_week`
- `historical_persistence_precision` when supported by validated detector evidence
- `historical_reversion_rate` when supported
- `source_version`

Primary role families currently supported by the validated role-research foundation:

- `rb_carry_share`
- `rb_opportunity_share`
- `wr_target_share`
- `te_target_share`

### current_role

Per supported family:

- `season`
- `week`
- `role_family`
- `metric_all`
- `metric_normal`
- `raw_opportunities_all`
- `raw_opportunities_normal`
- `team_opportunities_all`
- `team_opportunities_normal`
- `snap_share` when authoritative
- `qualifying_game`
- `confirmed_partial_game`
- `suspected_partial_game`
- `partial_game_reason`
- `data_quality_pass`
- `source_version`

Situational evidence when authoritative:

- early down
- passing down
- short yardage
- two minute
- red zone
- inside 10
- inside 5
- leading / trailing / close

Do not expose the research route proxy as true route participation. True route share remains missing until sourced authoritatively.

### role_change

- `role_family`
- `baseline_share`
- `current_share`
- `change_percentage_points`
- `direction`: `UP | DOWN | FLAT`
- `screen_category` when applicable
- `detector_status`: `NOT_EVALUATED | SCREEN_ONLY | DETECTED | PERSISTENCE_PENDING | PERSISTENT | REVERTED`
- `reason_codes[]`

Screen categories may reuse existing factual weekly-role concepts such as:

- `OPPORTUNITY_GAINED`
- `OPPORTUNITY_LOST`
- `BOX_SCORE_OVERSTATED_ROLE`
- `STRONG_OPPORTUNITY_WEAK_PRODUCTION`

A screening category is not automatically a persistence claim.

### current_context

Only source-backed fields are allowed:

- `roster_status`
- `depth_chart_role`
- `starter_status`
- `depth_chart_rank`
- `injury_status`
- `practice_status`
- `game_status`
- `availability_risk`
- `teammate_availability[]`
- `opponent`
- `game_time_utc`
- `bye_week`

Each field/group should carry source and freshness metadata when the source differs from the main role partition.

### market_evidence

Normalized current market rows relevant to fantasy usage:

- `market_key`
- `market_label`
- `line`
- `over_price`
- `under_price`
- `book`
- `event_id`
- `commence_time`
- `snapshot_time`
- `age_seconds`
- `identity_resolution_status`

Derived market context may include:

- best comparable line
- line gap
- stale/fresh peer status
- movement from retained historical snapshot when available

Rules:

- Market evidence is confirmation/context, not automatically a fantasy projection.
- A market row may not join to NFL/fantasy evidence until canonical player identity is resolved.
- DFS pick'em reference rows must remain distinct from apples-to-apples sportsbook pricing where pricing mechanics differ.

### quality

Required quality envelope:

- `identity_status`
- `role_status`
- `role_as_of_utc`
- `market_status`
- `market_as_of_utc`
- `context_status`
- `context_as_of_utc`
- `missing_evidence[]`
- `stale_evidence[]`
- `blocked_reason_codes[]`
- `recommendation_safe`: boolean

If a required join is unresolved or league ownership is stale, downstream recommendation layers must fail closed rather than infer.

## Downstream use

### Fantasy League HQ

Combines Player Evidence with league-specific state:

`Player Evidence + League Rules + User Roster + Ownership + Matchup = Fantasy Action`

League phase is part of that decision boundary. A valid Player Evidence record does not make a waiver/start-sit recommendation safe when the fantasy league is still pre-draft and ownership is uninitialized.

Pre-draft Fantasy HQ may still use Player Evidence for:

- keeper comparisons;
- draft preparation;
- player watchlists;
- league-specific draft values once scoring/roster rules are verified.

Ownership-dependent actions remain blocked until the platform reports meaningful roster ownership.

### Role Shock

Uses the same role-change evidence and market context to identify NFL usage changes that markets or fantasy ownership may not yet reflect.

### Deep Prop

Should eventually resolve feed labels to `propwar_player_id` and attach current role/context rather than maintaining only text-label player identity.

## Versioning

Every material contract change increments `schema_version`.

Persisted recommendations must retain the schema/model/rules version used at generation time so future audits can reproduce the evidence available when the recommendation was made.