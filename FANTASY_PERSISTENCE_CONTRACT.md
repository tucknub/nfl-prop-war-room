# Fantasy League HQ Persistence Contract

## Scope

This document defines the storage boundary for Fantasy League HQ. The first schema lives in `migrations/0001_fantasy_hq_persistence.sql` and is intentionally valid SQLite so it can be exercised locally with Python `sqlite3` and later applied to Cloudflare D1.

This slice does **not** configure Wrangler, create a D1 database, deploy a Worker, add Yahoo OAuth, add Streamlit UI, or write production fantasy state.

## Core invariants

### Observation identity is not content identity

`fantasy_state_snapshots.snapshot_id` is the immutable identity of one accepted provider observation.

`fantasy_state_snapshots.content_fingerprint` identifies the normalized content observed in that snapshot.

Two different observations may therefore have different `snapshot_id` values and the same `content_fingerprint`. That is expected when a provider sync repeats with no meaningful state change.

A `snapshot_id` cannot be reused because it is the primary key.

### Change events bind exact observations

Every row in `fantasy_change_events` references both the exact before and after snapshots.

The schema uses composite foreign keys so both snapshots must belong to the same `league_season_id` as the event. The event's `platform`, `platform_league_id`, and `season` must also match that league-season record.

`event_fingerprint` is the primary key. Re-inserting the same deterministic event is rejected by the database, while the same football transition observed later can have a different fingerprint because the snapshot pair is different.

### Historical rows are protected

Historical relationships use `ON UPDATE RESTRICT ON DELETE RESTRICT`. The first schema intentionally avoids cascading deletion of accepted snapshots, events, identities, or league-season history.

Accepted `fantasy_state_snapshots`, `fantasy_change_events`, and `football_identity_review_events` are also guarded by database triggers that abort direct `UPDATE` or `DELETE` statements. These rows are append-only at the database boundary, not merely by application convention.

`fantasy_sync_runs` is intentionally mutable because a started sync must be completed or failed. `football_entities`, accepted external-ID mappings, and league metadata are not given blanket append-only triggers because later verified corrections or lifecycle updates may be legitimate and must be accompanied by explicit audit behavior in the writer layer.

A later retention or repair policy for append-only rows must be explicit and separately reviewed, including an intentional migration that drops or replaces the relevant guards.

### JSON is stored as text and validated

Normalized snapshots, change values, reason codes, transaction IDs, identity evidence, and metadata are stored as JSON text. Every JSON-designated column is protected with `json_valid(...)` checks so malformed serialized state fails at the storage boundary.

### Provider IDs may remain unresolved

`fantasy_change_events.platform_player_id` intentionally has no foreign key to `football_entities`.

The change engine is allowed to preserve a trustworthy provider player ID before PropWar has resolved that player into its canonical NFL identity layer. This prevents identity uncertainty from blocking factual league-state history.

## League hierarchy

`fantasy_league_families` is the stable, provider-neutral identity of a real fantasy league across seasons.

`fantasy_league_seasons` binds one family to one platform league for one season. The schema prevents two rows from claiming the same `(platform, platform_league_id, season)` and prevents one league family from having two canonical records for the same season.

The hierarchy is:

```text
fantasy_league_families
        |
        +-- fantasy_league_seasons
                |
                +-- fantasy_state_snapshots
                |       |
                |       +-- fantasy_change_events
                |
                +-- fantasy_sync_runs
```

## Sync history

`fantasy_sync_runs` records provider synchronization attempts separately from accepted snapshots.

A sync may fail without creating a snapshot. When `accepted_snapshot_id` is present, its composite foreign key requires that snapshot to belong to the same league season.

The future Worker should persist a successful accepted observation and its derived change events atomically. Cloudflare D1's batch API is the intended transaction boundary, but no D1 writer is included in this migration slice.

## Canonical football identity

`football_entities.propwar_entity_id` is the stable PropWar identity used by the persistence layer. It is not required to be generated independently of every upstream namespace.

Production already uses nflverse/GSIS `player_id` as the operational canonical player key in the identity crosswalk and roster/role pipeline. The persistence bridge must preserve that compatibility:

- when a player already has a trusted production GSIS-backed `player_id`, seed `propwar_entity_id` with that **same value** rather than inventing a second identifier;
- also record that value in `football_external_ids` as the accepted `gsis` external ID so provider relationships remain explicit;
- when a player enters Fantasy HQ before a stable GSIS ID exists, create a durable generated PropWar entity ID and never renumber that entity later;
- when GSIS becomes available for that pre-GSIS player, attach it as a verified external ID to the existing entity.

This makes the persistence entity layer an extension of PropWar's existing identity system, not a replacement identity universe.

Accepted external links live in `football_external_ids`.

```text
existing GSIS-backed player
player_id == propwar_entity_id
                    |
                    +-- gsis / scope / same player_id
                    +-- sleeper / scope / external_id
                    +-- yahoo / scope / external_id

pre-GSIS player
stable generated propwar_entity_id
                    |
                    +-- sleeper / scope / external_id
                    +-- yahoo / scope / external_id
                    +-- gsis / scope / verified later
```

`provider_scope` is a non-null string because some providers can issue identifiers that are season/game scoped. A blank scope represents a provider ID treated as globally stable.

Within one provider scope:

- one external ID can map to only one PropWar entity;
- one PropWar entity can have only one accepted external ID.

The bridge must prefer exact trusted IDs. Existing production identity behavior already blocks ambiguous/conflicting rows and warns on duplicate normalized names; the persistence bridge must not weaken those rules.

## Identity review audit

Ambiguous or rejected identity work belongs in `football_identity_review_events`, not in `football_external_ids`.

A review event can exist before an accepted external link. It records the provider ID, candidate/previous PropWar entity when known, decision, reason codes, evidence, timestamps, and reviewer marker.

Each review row is a completed audit event and is append-only. A later decision is represented by another review event rather than mutating the prior event.

No name-based fuzzy match is automatically accepted by this schema. Name/team information may produce a review candidate, but an accepted external mapping must meet the later bridge's explicit verification rules.

## Intended future write order

The later D1/Worker implementation should follow this order for one provider sync:

1. resolve or create the league family and league-season identity;
2. record the sync attempt;
3. normalize and validate provider state;
4. insert a new immutable accepted snapshot;
5. derive deterministic change events from the previous accepted snapshot;
6. insert the events using their deterministic fingerprints;
7. mark the sync completed with its accepted snapshot;
8. commit the accepted snapshot, events, and sync completion as one database transaction/batch.

Identity-linking work is independent of steps 1-8 and must not rewrite historical provider IDs stored on fantasy events.

## Deliberately deferred

The schema does not yet define recommendation output, projections, lineup decisions, waiver recommendations, betting-market evidence, notifications, OAuth tokens, raw provider-response archives, or UI state. Those belong in later bounded slices after persistence and identity behavior are proven.
