# DepthSnap public export contract

Status: **Frozen V1 bridge contract**

This document defines the JSON boundary that a future Python exporter must
produce and the public Next.js application must consume. It does not implement
the exporter or change the Python methodology. The machine-enforced web
authority is `apps/web/src/lib/data-contract.ts`.

## Compatibility policy

- V1 schema identifiers are exact strings. Unknown identifiers fail closed.
- `dataMode` is separate from `schemaVersion`; schema names never include
  `fixture` or `export`.
- Adding a required field, changing a field meaning, changing a closed enum, or
  changing numeric semantics requires a new schema version.
- V1 readers reject unknown fields because public objects are strict.
- Future readers do not automatically reinterpret older or newer versions.
- Fixture and export registries use the same bundle schemas.

## Registry selection

`DEPTHSNAP_DATA_MODE` must be `fixture` or `export`.

- Production with an unset or unsupported value returns
  `unsupported_data_mode` before reading a manifest.
- `next dev` may opt into the fixture default through the explicitly scoped
  development loader path.
- Browser tests set `DEPTHSNAP_DATA_MODE=fixture` explicitly.
- Export mode reads only `public/data/depthsnap/export`.
- Export mode never falls back to a fixture directory.

## Deterministic serialization and hashes

Every bundle and manifest uses:

1. camelCase public field names;
2. object keys sorted lexicographically at every depth;
3. compact JSON separators;
4. UTF-8 with non-ASCII characters preserved;
5. exactly one final newline.

The Python equivalent is `json.dumps(value, sort_keys=True,
separators=(",", ":"), ensure_ascii=False) + "\n"`.

Each manifest entry’s `sha256` is the lowercase hexadecimal SHA-256 of the
exact serialized bundle bytes. The manifest has no self-hash.

## Common bundle fields

Every V1 bundle contains:

| Field | Type | Meaning |
| --- | --- | --- |
| `schemaVersion` | closed schema string | Bundle family/version |
| `dataMode` | `fixture \| export` | Selected source mode |
| `dataNotice` | non-empty string | Supplied source/public notice |
| `status` | `published \| no_published_week \| unavailable` | Supplied publication state |
| `season` | integer, 2000–2200 | Supplied season |
| `throughWeek` | integer 1–18 or `null` | Supplied published-through week |
| `generatedAt` | RFC 3339 timestamp with offset | Bundle generation time |
| `sourceVersion` | non-empty string | Supplied source version |

The UI renders `dataNotice` as the visible fixture banner only when
`dataMode === "fixture"`. Export mode does not display a fixture banner.

Non-published state bundles retain metadata and state copy but do not fabricate
evidence.

## Shared records

### `RawShareEvidence`

- `numerator`: non-negative integer
- `denominator`: positive integer
- `share`: decimal ratio from 0 through 1
- `opportunityLabel`: `opportunities`, `carries`, or `targets`

`numerator` must not exceed `denominator`. `share` must agree with
`numerator / denominator` within `0.0005`.

### `MovementEvidence`

- `previous`: `RawShareEvidence`
- `current`: `RawShareEvidence`
- `percentagePointChange`: number

The supplied percentage-point value must agree with
`(current.share - previous.share) * 100` within `0.05`.

### `TeamIdentity`

- `id`
- `abbreviation`
- `name`
- optional `conference`
- optional `division`
- `monogram`
- `accent`: `teal`, `amber`, or `slate`
- `href`
- `searchAliases`

### `PlayerIdentity`

- `id`
- `name`
- `team`
- `teamId`
- `position`: `RB`, `WR`, or `TE`
- `href`
- optional `jerseyNumber`
- `searchAliases`

### Closed evidence values

- Data quality: `complete`, `reviewed_partial_game`,
  `unavailable_supporting_context`
- Report family: `backfield_control`, `target_hierarchy`, `role_movement`
- Movement direction: `gain`, `decline`, `stable`

## Manifest: `depthsnap.manifest.v1`

The manifest contains exactly:

| Field | Type |
| --- | --- |
| `schemaVersion` | literal `depthsnap.manifest.v1` |
| `productId` | literal `depthsnap` |
| `dataMode` | `fixture \| export` |
| `publicationStatus` | `published \| no_published_week \| unavailable` |
| `validationResult` | `pass \| fail \| not_applicable` |
| `season` | integer, 2000–2200 |
| `throughWeek` | integer 1–18 or `null` |
| `generatedAt` | RFC 3339 timestamp with offset |
| `sourceVersion` | non-empty string |
| `formulaVersion` | optional non-empty string |
| `pipelineRunId` | optional non-empty string |
| `entries` | non-empty array of manifest entries |

Each manifest entry contains exactly:

- `family`
- optional stable `id` for `team` and `player`
- canonical relative POSIX `path`
- `schemaVersion`
- lowercase 64-character `sha256`
- `required`
- non-negative `recordCount`

All V1 entries are required. Paths cannot be absolute, contain backslashes, or
contain `..`.

The loader verifies that manifest publication, season, week, generation,
source, formula, and pipeline-run metadata agree with the status bundle and
that common bundle metadata agrees across the registry.

## Bundle families

### Home: `depthsnap.home.v1`

Common fields plus:

- `reportLinks`
- when published: `leadFinding`, `findings`, `teamSnapshot`,
  `reportLeaderboard`
- when not published: `stateTitle`, `stateMessage`

Feed findings contain `id`, `kind`, `reportFamily`, `roleFamily`, `player`,
`headline`, `current`, optional `movement`, and `evidenceHref`.

### Reports index: `depthsnap.reports.index.v1`

Common fields plus `modules`. A module contains `kind`, `family`, `title`,
`question`, `description`, `href`, and its supplied current or movement row.
Non-published indexes have an empty `modules` array.

### Current reports

Schemas:

- `depthsnap.report.backfield.v1`
- `depthsnap.report.targets.v1`

Common fields plus:

- `reportFamily`
- `title`
- `question`
- `description`
- `availableViews`
- `defaultView`
- `defaultSort`
- `availableSorts`
- `teamOptions`
- `resultCount`
- `views`
- `stateTitle` and `stateMessage` when not published

Each published view has `viewId`, `summary`, and `rows`. A current row contains
`id`, `authoritativeRank`, `player`, `roleFamily`, `current`, optional
`supportingContext`, `classificationLabel`, `teamHref`, `playerHref`,
`evidenceHref`, and `dataQuality`.

### Role Movement: `depthsnap.report.movement.v1`

Uses the report metadata fields above. Each published movement row contains
`id`, `authoritativeRank`, `player`, `roleFamily`, `movement`, `direction`,
`movementLabel`, `finding`, optional `supportingContext`, `teamHref`,
`playerHref`, `evidenceHref`, and `dataQuality`.

### Teams index: `depthsnap.teams.index.v1`

Common fields plus `teams`. Each directory record contains `team`, optional
`topBackfield`, optional `topWr`, optional `topTe`, and optional
`largestMovement`. Non-published indexes contain no evidence rows.

### Team dossier: `depthsnap.team.v1`

Common fields plus:

- `team`
- `suppliedSummary`
- `backfieldHierarchy`
- `wrTargetHierarchy`
- `teTargetHierarchy`
- `movements`
- `linkedPlayers`
- `availableViews`
- `dataQuality`

Hierarchy rows carry supplied `authoritativeOrder`; the frontend does not
reclassify them.

### Players index: `depthsnap.players.index.v1`

Common fields plus `players` and `teamOptions`. Each directory record contains
`player`, optional `currentEvidence`, `suppliedRoleDescription`,
`memberships`, and optional `latestMovement`.

### Player dossier: `depthsnap.player.v1`

Common fields plus:

- `player`
- `currentTeam`
- `suppliedRoleDescription`
- optional `currentEvidence`
- optional `supportingContext`
- optional `latestMovement`
- `reportMemberships`
- `weeklyEvidence`
- `periodSummaries`
- `movementHistory`
- `teamHierarchyContext`
- `dataQuality`

A weekly point contains `week`, `periodLabel`, optional `evidence`,
`opportunityLabel`, `dataQuality`, and optional `partialGame`.

### Search: `depthsnap.search.v1`

Common fields plus `records`. Each record contains `type`, `id`, `displayName`,
`secondaryLabel`, `summary`, `href`, and `searchAliases`.

### Status: `depthsnap.status.v1`

Common fields plus:

- optional `formulaVersion`
- optional `pipelineRunId`
- `manifestSchemaVersion`
- `bundleCount`
- `validationSummary`
- `checks`
- `limitations`

Each status check contains:

| Field | Type |
| --- | --- |
| `id` | stable non-empty string |
| `label` | non-empty string |
| `status` | `pass \| fail \| attention \| unavailable \| reviewed \| not_applicable` |
| `detail` | non-empty string |
| `required` | boolean |
| `blocking` | boolean |
| `numerator` | optional non-negative integer |
| `denominator` | optional non-negative integer |
| `percentage` | optional number from 0 through 100 |

Coverage numerator and denominator must be supplied together. Numerator cannot
exceed denominator. When a positive denominator and percentage are both
supplied, the percentage must agree within `0.05` percentage points.

Checks are explanatory operational evidence. The frontend displays them and
does not calculate a publication verdict.

## Python exporter responsibilities

The future Python exporter must:

- remain authoritative for identity, membership, order, classifications,
  findings, evidence, publication, and operational checks;
- map internal snake_case data to this public camelCase contract;
- emit every required family in every publication state;
- retain exact supplied numerators, denominators, shares, movements, and
  quality values;
- resolve every stable team/player reference;
- serialize deterministically and populate the manifest hashes/counts;
- supply manifest publication/version metadata;
- write only to the export registry;
- complete its own validation before making an export registry available.

## Frontend loader responsibilities

The frontend loader must:

- require an explicit production mode;
- select only the matching registry directory;
- validate the manifest and every required entry;
- verify paths, versions, hashes, counts, identities, cross-route evidence, and
  registry-wide metadata agreement;
- return typed data or a public-safe typed failure;
- display supplied publication/check results without deriving a new verdict;
- never substitute fixture data in export mode.

The application caches one fully validated immutable registry promise per
process, mode, publication variant, and data root. The cold load reads the
manifest plus every required bundle and performs all fail-closed checks. Warm
requests reuse that validated registry and perform no additional file reads.
Changing a deployed registry requires a new process/build rather than an
in-place mutation.

## Failure behavior

Closed loader failure categories are:

- `bundle_missing`
- `invalid_json`
- `invalid_bundle`
- `incompatible_schema`
- `manifest_mismatch`
- `hash_mismatch`
- `unresolved_reference`
- `unsupported_data_mode`

Failures expose a safe title, message, and public detail. They do not expose
absolute paths, stack traces, credentials, tokens, or private source URLs.
They are distinct from valid `unavailable` publication bundles.
