# DepthSnap Phase 4A implementation inventory

This inventory records the pre-migration state at commit
`966fb0b43375a9e0d923b99aab613096027fcbc8`. It is the required baseline for
moving the public application from TypeScript fixture imports to validated,
versioned JSON bundles.

## Direct fixture dependencies

The following public route or shared component files import fixture data
directly:

| Public surface | Current dependency |
| --- | --- |
| Feed (`/`) | `home.fixture.ts`, `home.presentation.fixture.ts` |
| Reports overview (`/reports`) | `reports.fixture.ts` |
| Shared report page | `reports.fixture.ts` |
| Teams directory (`/teams`) | `identity.fixture.ts`, `identity-data.ts` |
| Team dossier (`/teams/[team]`) | `identity-data.ts` |
| Players directory (`/players`) | `identity.fixture.ts`, `identity-data.ts` |
| Player dossier (`/players/[playerId]`) | `identity-data.ts` |
| Search (`/search`) | `identity.fixture.ts`, `identity-data.ts` |

`identity-data.ts` also imports both report and identity fixtures and derives
directory records, dossier bundles, and search records in TypeScript at
runtime.

## Existing schema discriminators

The existing TypeScript fixtures use three fixture-specific discriminators:

- `depthsnap.home.fixture.v1`
- `depthsnap.report.fixture.v1`
- `depthsnap.identity.fixture.v1`

They also encode `fixture: true` rather than the normative `dataMode`
discriminator. These are replaced in Phase 4A by the exact schema versions in
`PHASE4A_CONTRACT_DECISIONS.md`.

## Stable identities and references

The current synthetic identity source contains:

- eight stable team IDs: `JVT`, `PDX`, `BHM`, `SAC`, `OKC`, `IND`, `SEA`, and
  `MIN`
- 27 stable `player-*` IDs
- stable `/teams/{id}` and `/players/{id}` hrefs

Those opaque fixture IDs and hrefs are preserved. The Phase 4A validator must
reject duplicate IDs and any player, team, dossier, report, home, or search
reference that does not resolve.

## Duplicated evidence before migration

The same synthetic values are currently copied into multiple TypeScript
files. Representative examples include:

| Player | Canonical evidence | Duplicated surfaces |
| --- | --- | --- |
| Marcus Hale | 27 of 34 RB opportunities · 79.4% | Feed lead/presentation, Backfield report, Team dossier derivation, Player dossier derivation, Search |
| Zion Mercer | 22 of 35 RB opportunities · 62.9% | Feed movement/presentation, Backfield report, Team/Player/Search derivation |
| Theo Lane | 10 of 31 team targets · 32.3% | Feed movement/presentation, Target report, Team/Player/Search derivation |
| Miles Redd | 8 of 28 team targets · 28.6% | Feed movement/presentation, Target report, Team/Player/Search derivation |
| Owen Black | 13 of 30 team targets · 43.3% | Feed movement/presentation, Target report, Team/Player/Search derivation |

Phase 4A moves these values into generated JSON bundles and validates
cross-bundle consistency so route code no longer owns canonical fixture
evidence.

## Existing route state and query behavior

The current public UI uses the following query-backed test and presentation
states:

- Feed: `state=empty`, `state=unavailable`
- Reports: `state=loading`, `state=empty`, `state=unavailable`
- Identity routes: `state=loading`, `state=unpublished`,
  `state=unavailable`
- Reports additionally support validated `view`, `sort`, `team`, `position`,
  and `page` parameters.
- Teams and Players directories support their existing search/filter/sort
  parameters.

Phase 4A retains visible loading, no-published-week, unavailable, and
no-matching-filter experiences. Published, no-published-week, and unavailable
data are represented by complete validated bundle sets rather than by
silently falling back to published fixture evidence.

## Python authority observed

`current_role_pipeline.py` and `published_validation.py` remain unchanged.
Their operational contract includes:

- all-play shares backed by raw player numerators and matching team
  denominators
- consecutive completed-week and snap-availability gates
- strict identity, opportunity-to-snap, and report-position coverage checks
- manual reviewed overrides as the only source for partial-game exclusions
- canonical/event/production uniqueness checks
- exact output hashes in the operational manifest
- fail-closed published-output validation

The Phase 4A web contract renders supplied values only. It does not reproduce
Python classification, membership, ranking, completion detection, or
methodology in TypeScript.

