# Fantasy League HQ — Player Identity Audit

**Audit date:** 2026-08-26  
**Status:** Source/architecture evidence; no Fantasy HQ runtime behavior changed.

## Purpose

Measure how safely real Sleeper fantasy players can join to PropWar's existing NFL identity authority before Fantasy HQ is implemented.

The audit used:

- the committed PropWar `outputs/identity/player_identity_crosswalk.csv`;
- real players drafted/rostered in Franchise Football League and Papa Johns during 2024–2025;
- the current Sleeper NFL player map;
- Sleeper external-ID fields when present.

The temporary GitHub Actions audit is evidence gathering only and is not part of the target production architecture.

## Existing PropWar authority

The current PropWar identity export is built primarily from NFL roster/weekly/projection sources and uses GSIS-backed `player_id` values where available. It already includes normalized names, canonical teams, positions, duplicate-name flags, and an explicit rule that duplicate names require ID or team-qualified matching.

This remains the football-side identity authority for the existing Python pipeline.

## Real historical league-player result

Across the distinct players that actually appeared in the audited 2024–2025 FFL/Papa Johns drafts and rosters:

- **330 distinct Sleeper player/team-defense IDs** were observed.
- 93 matched the committed PropWar crosswalk directly through GSIS.
- 1 had an authoritative Sleeper GSIS ID that was newer than the committed crosswalk and therefore only required crosswalk extension.
- 161 had a unique normalized name + team + position match.
- 43 had a unique normalized name + position match.
- 28 were team defenses and should be modeled as canonical NFL team-defense entities rather than human players.
- only **4 were unresolved** by this first-pass logic.
- overall, **98.79%** were canonicalizable with existing authority plus controlled extensions.

This is strong evidence that Fantasy HQ can safely join historical real-league ownership to PropWar evidence without inventing a separate player database.

The four unresolved historical/current-name cases were not evidence of duplicate-player contamination; they were examples of provider/crosswalk naming or current-team staleness that should enter a reviewed alias/identity-extension queue rather than be guessed.

## Current 2026 draft-pool result

Sleeper's raw `active=true` player population is too broad to use as a fantasy player universe. The audit therefore also evaluated team-attached players by Sleeper `search_rank`.

### Search rank <= 500

457 current team-attached QB/RB/WR/TE/K records:

- 85 direct GSIS matches;
- 5 authoritative GSIS extensions;
- 240 unique name + team + position matches;
- 41 unique name + position matches;
- 86 unresolved by the first pass;
- **81.18% canonicalizable** with controlled extensions.

Of those 86 unresolved records:

- **78 were 2026 rookies**;
- only **8 were non-rookies**.

Therefore roughly 91% of the unresolved top-500 problem is rookie/new-player identity timing, not a broad failure to reconcile established fantasy players.

At tighter fantasy-relevance cutoffs the same pattern held: the unresolved population was overwhelmingly rookies/new identities, with only a handful of veteran/current-provider naming cases requiring review.

### Search rank <= 1000

914 current team-attached QB/RB/WR/TE/K records:

- 151 direct GSIS matches;
- 10 GSIS extensions;
- 432 unique name + team + position matches;
- 129 unique name + position matches;
- 192 unresolved;
- **78.99% canonicalizable** with controlled extensions.

Of those 192 unresolved records, **175 were rookies** and 17 were non-rookies.

## 2026 rookie finding

The current Sleeper map creates a critical pre-Week-1 identity edge case.

Among the top-500 rookie set in the audit:

- 78 rookies were present;
- all 78 lacked a Sleeper-exposed GSIS ID;
- all 78 lacked a Sleeper-exposed Yahoo ID;
- all 78 lacked a Sleeper-exposed ESPN ID;
- all 78 had a Sportradar ID;
- all 78 had a FantasyData ID.

Among the top-1000 rookie set:

- 175 rookies were present;
- all 175 lacked a Sleeper-exposed GSIS/Yahoo/ESPN ID;
- Sportradar coverage was complete;
- FantasyData coverage was nearly complete.

This does **not** prove nflverse/current NFL roster sources lack GSIS IDs. The production identity flow should first attempt reconciliation against PropWar's current NFL/nflverse identity sources. The finding is narrower: **Sleeper itself cannot be treated as a reliable pre-Week-1 GSIS/Yahoo bridge for rookies.**

## Architecture decision: immutable internal entity key

Fantasy HQ should not make any external provider ID—including GSIS—the database row's immutable primary key.

Introduce an opaque, stable internal identity such as:

`propwar_entity_id`

The existing Python NFL pipeline may continue to use its GSIS-backed `player_id` internally; Fantasy HQ adds a compatibility layer rather than forcing an immediate NFL-pipeline rewrite.

### Identity model

Each football entity has:

- immutable `propwar_entity_id`;
- entity type: `PLAYER | TEAM_DEFENSE`;
- display name/team/position metadata;
- identity status;
- zero or more external IDs.

External IDs may include:

- GSIS;
- PFR;
- Sleeper;
- Yahoo;
- Sportradar;
- FantasyData;
- ESPN;
- reviewed sportsbook/provider aliases.

### Identity status

Recommended statuses:

- `VERIFIED_NFL_ID` — authoritative NFL/GSIS bridge exists;
- `VERIFIED_EXTERNAL_BRIDGE` — reviewed multi-source external bridge exists while NFL ID is pending;
- `PROVISIONAL_PROVIDER_ENTITY` — current provider entity is real enough for league display/draft state but not yet safe to join to NFL role/market evidence;
- `REVIEW_REQUIRED`;
- `MERGED` / alias redirect for corrected duplicates;
- `UNRESOLVED`.

A provisional rookie may exist in Fantasy HQ for draft/ownership display without being allowed to consume historical NFL role evidence. When an authoritative GSIS/current NFL identity becomes available, attach it to the same `propwar_entity_id`; **do not re-key the player or rewrite historical draft/recommendation rows.**

## Resolution order

Recommended identity resolution order:

1. direct existing PropWar/GSIS identity;
2. current PropWar/nflverse roster identity;
3. provider-supplied authoritative/reviewed external-ID bridge;
4. unique normalized name + current team + position with review/verification policy;
5. unique name + position only as lower-confidence review evidence, not an unconditional permanent bridge;
6. provisional provider entity when the player is real/current but no safe NFL bridge exists;
7. unresolved/review required.

Never use fuzzy display-name matching to auto-resolve a collision.

## Team defenses

Sleeper team defenses are not human-player identities. Normalize them to one `TEAM_DEFENSE` entity per canonical NFL team.

The same team-defense entity can then be reused for:

- FFL roster ownership;
- scoring/ranking;
- schedule/opponent context;
- future D/ST analysis.

Do not create pseudo-player GSIS IDs for team defenses.

## Yahoo implication

Sleeper's `yahoo_id` is useful crosswalk evidence when populated, and the audited historical real-player set showed no duplicate Yahoo IDs. However, it cannot be the sole Yahoo bridge because current rookies may not have a Sleeper Yahoo ID yet.

Yahoo ingestion must retain the actual Yahoo player key and resolve it through the shared identity registry using authoritative IDs/current NFL context/reviewed name-team-position evidence as available.

## Validation requirements

Before Fantasy HQ recommendations may join ownership to NFL evidence:

- report direct NFL-ID resolution rate;
- report externally bridged rate;
- report provisional rate;
- report review-required/unresolved rate;
- explicitly test duplicate-name cases;
- explicitly test traded players/current-team staleness;
- test rookie promotion from provisional -> verified NFL identity without changing `propwar_entity_id`;
- test team-defense normalization;
- block NFL-role/market joins for provisional entities that lack a safe canonical NFL bridge.

## Implementation conclusion

The identity problem is **not** a blocker for Fantasy HQ.

Historical real-league coverage is already extremely high, and the remaining current-season gap is concentrated in rookies/new provider identities. The correct fix is an immutable internal entity registry plus external-ID promotion/review—not a second fantasy-specific player database and not unsafe fuzzy matching.
