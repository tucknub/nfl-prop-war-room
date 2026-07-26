# DepthSnap public export contract

Status: **Pre-production V1, amended in place for Phase 4B**

The normative decisions in PR #9, “Phase 4B normative decisions — resume
authorization,” resolve the authority gaps recorded in
`PHASE4B_AUTHORITY_GAP_REPORT.md`. Because no V1 export has been deployed, the
contract remains `*.v1` and is amended in place. Compatibility obligations
begin with the first production publication.

The machine-enforced authority is
`apps/web/src/lib/data-contract.ts`. The Python implementation is
`src/export/depthsnap_exporter.py`.

## Compatibility policy

- V1 schema identifiers are exact; unknown identifiers fail closed.
- Public objects are strict and reject unknown fields.
- `dataMode` is separate from `schemaVersion`.
- Fixture and export registries use the same schemas.
- After the first production publication, a required-field change, field
  meaning change, closed-enum change, or numeric-semantics change requires a
  new schema version.

## Registry selection and isolation

`DEPTHSNAP_DATA_MODE` must be `fixture` or `export`.

- Production with an unset or unsupported value returns
  `unsupported_data_mode`.
- Development may opt into the fixture default only through its explicitly
  scoped loader path.
- Export mode reads only `<dataRoot>/export`.
- Production requires `DEPTHSNAP_DATA_ROOT` to resolve exactly to
  `public/data/depthsnap` from the runtime package root.
- Independent roots require the explicit test-only
  `DEPTHSNAP_ALLOW_TEST_DATA_ROOT=1` override.
- Export mode never falls back to fixtures.
- A validated registry is cached for the process lifetime. Replacing an active
  registry requires a controlled restart or rebuild/redeploy before readers
  see it.

The committed roots are:

- active: `apps/web/public/data/depthsnap/export`;
- temporary parity only:
  `apps/web/public/data/depthsnap/export-historical-2025`.

The historical root is never selected by the application implicitly.
The provider-neutral production package copies only the active root. Fixture,
historical, private, test, Python, staging, and rollback content is rejected by
the production artifact audit.

## Deterministic serialization, timestamps, and source versions

Every bundle and manifest uses:

1. camelCase public fields;
2. keys sorted lexicographically at every depth;
3. compact JSON separators;
4. UTF-8 with non-ASCII characters preserved;
5. exactly one trailing LF.

Python equivalent:

```python
json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
```

Each entry SHA-256 covers the exact serialized bundle bytes. The manifest has
no self-hash.

- `generatedAt` is the actual exporter invocation time, or an explicit
  RFC 3339 timestamp supplied for a reproducibility test.
- `sourceVersion` is `sha256:<digest>` over the exact source-artifact inventory
  and hashes used by that registry. It is not a season label or pipeline name.

Repeated builds with the same sources and explicit `generatedAt` must be
byte-for-byte identical.

Repository attributes pin registry JSON and exact JSON source-metadata
artifacts to LF so Git checkout settings cannot alter hashed bytes.

## Common fields and publication states

Every V1 bundle includes:

| Field | Meaning |
|---|---|
| `schemaVersion` | Exact bundle schema |
| `dataMode` | `fixture` or `export` |
| `dataNotice` | Supplied public notice |
| `status` | `published`, `no_published_week`, or `unavailable` |
| `season` | Supplied season |
| `throughWeek` | Week 1–18 or `null` |
| `generatedAt` | RFC 3339 generation timestamp |
| `sourceVersion` | Content-addressed exact sources |

Publication mapping:

| Python state | Public registry behavior |
|---|---|
| Independently validated `PUBLISHED` | Populated `published` registry |
| `PRESEASON` or `WAITING_FOR_COMPLETED_WEEK` | Empty `no_published_week` registry |
| `BLOCKED`, with supplied state metadata and no prior valid registry | Empty `unavailable` registry |
| `BLOCKED`, with a prior valid registry | Retain prior registry; do not promote |
| `VALIDATED_NOT_PUBLISHED` | Do not promote |
| Contract, identity, source, or validation failure | Fail closed; no state downgrade |

Every publication state emits the nine singleton families. Only a populated
publication also emits one bundle per team and player. Non-published bundles
contain no team, player, report, movement, hierarchy, or weekly evidence.

The active committed registry truthfully represents 2026
`no_published_week`. The completed-2025 registry is temporary parity evidence,
not the active season and not a deployable current publication.

## Shared evidence and identity records

### Raw evidence

`RawShareEvidence` contains:

- non-negative integer `numerator`;
- positive integer `denominator`;
- `share` from 0 through 1;
- `opportunityLabel`: `opportunities`, `carries`, or `targets`.

`numerator <= denominator`, and `share` must match
`numerator / denominator` within `0.0005`.

`MovementEvidence` contains `previous`, `current`, and
`percentagePointChange`. The change must match
`(current.share - previous.share) * 100` within `0.05`.

### Team-neutral players and evidence teams

`PlayerIdentity` contains only:

- `id`;
- `name`;
- `position`: `RB`, `WR`, or `TE`;
- `href`;
- optional `jerseyNumber`;
- `searchAliases`.

It never embeds team, team ID, or current-team state.

- Dossiers and directory records carry `currentTeam` separately.
- Every report, finding, hierarchy, movement, period-summary, leaderboard, and
  weekly evidence row carries `evidenceTeam`.
- `currentEvidence` and `currentEvidenceTeam` are supplied together.
- A player may have historical evidence teams that differ from `currentTeam`.
  The frontend must preserve those stints rather than rewriting them.

`TeamIdentity` contains stable ID, abbreviation, name, optional conference and
division, monogram, accent, href, and aliases. The canonical 32-team crosswalk
includes ATL.

### Closed role and quality vocabulary

Role family to display label is exact:

| `roleFamily` | `roleLabel` |
|---|---|
| `rb_carry_share` | `RB carry share` |
| `rb_opportunity_share` | `RB opportunity share` |
| `wr_target_share` | `WR target share` |
| `te_target_share` | `TE target share` |

`classificationLabel` and `movementLabel` are not part of V1.

Participation and supporting context are separate:

- `participationQuality`:
  `complete`, `suspected_statistical`, `suspected_corroborated`,
  `reviewed_partial_game`;
- `supportingContextStatus`: `available`, `unavailable`.

The bridge must preserve suspected rows and their supplied label. It must not
map suspicion to `complete` or `reviewed_partial_game`.

Home finding kinds are exactly:

- `opportunity_gained`;
- `opportunity_lost`;
- `box_score_overstated_role`;
- `strong_opportunity_weak_production`.

## Bundle families

The singleton families are:

- `depthsnap.home.v1`;
- `depthsnap.reports.index.v1`;
- `depthsnap.report.backfield.v1`;
- `depthsnap.report.targets.v1`;
- `depthsnap.report.movement.v1`;
- `depthsnap.teams.index.v1`;
- `depthsnap.players.index.v1`;
- `depthsnap.search.v1`;
- `depthsnap.status.v1`.

Populated registries additionally contain:

- `depthsnap.team.v1` for every team;
- `depthsnap.player.v1` for every player.

Report views are `last4`, `last8`, `last2`, and `season`. Membership,
authoritative order, raw current/prior values, supporting context, movement,
and finding copy come directly from the existing Python report builders.
`classificationLabel` and `movementLabel` are absent. `suppliedSummary` and
`suppliedRoleDescription` are optional.

The Home bundle uses the Python weekly-report order. Team Snapshot and the
three report leaderboards are deterministic compositions of that supplied
evidence, as authorized in PR #9. The frontend does not reclassify or rerank
them.

## Manifest

`depthsnap.manifest.v1` contains:

- product ID `depthsnap`;
- data mode and publication state;
- validation result;
- season and through week;
- generation and source versions;
- optional formula version and pipeline run ID;
- a non-empty entry array.

Each required entry has family, optional stable ID for team/player, canonical
relative POSIX path, exact schema, lowercase SHA-256, and record count.

The loader verifies:

- safe paths and exact family paths;
- schema versions;
- bundle hashes and record counts;
- publication metadata agreement;
- team/player uniqueness and references;
- team-neutral player identity;
- `currentTeam` and `evidenceTeam` references;
- cross-route evidence parity.

Closed failure categories are `bundle_missing`, `invalid_json`,
`invalid_bundle`, `incompatible_schema`, `manifest_mismatch`,
`hash_mismatch`, `unresolved_reference`, and `unsupported_data_mode`.

## Python exporter and promotion requirements

The exporter must:

- read the existing validated Python sources without changing methodology;
- preserve Python membership, ordering, formulas, findings, and raw values;
- expose prior numerator, denominator, and share already computed by the
  existing summary path;
- build all three publication states;
- resolve the full team crosswalk and stable players;
- validate schemas, numeric relationships, refs, hashes, counts, and metadata
  before promotion;
- stage in a sibling directory;
- atomically rename active to rollback and staging to active;
- restore active automatically if promotion fails;
- support explicit rollback and guarded staging/rollback cleanup;
- never write a partial registry into the active directory.

The active 2026 build uses atomic staging/promotion. Historical parity writes
to its explicitly named, isolated directory and is not promoted active.

## Production artifact and cache requirements

The standalone production package must:

- build with `DEPTHSNAP_DATA_MODE=export`;
- reject a missing, invalid, or pre-2026 active registry;
- stage only the active validated `export` directory;
- exclude fixture, historical, private, source, test, screenshot, trace,
  staging, rollback, and local-path content;
- start successfully in production mode and pass route smoke tests.

Registry JSON uses `max-age=0, must-revalidate` because its filenames remain
stable across promotions; ETags may satisfy a revalidation. Next-generated
hashed static assets may use immutable caching. A promotion must be followed
by the documented process restart or rebuild/redeploy because registry
validation is cached for the process lifetime.

## Opportunity Context preservation

Phase 4B does not expose new Opportunity Context fields in V1. It preserves the
source dimensions and availability classifications documented in
`OPPORTUNITY_CONTEXT_SOURCE_MAP.md`. The private, content-addressed inventory
is:

`outputs/role_research/depthsnap_bridge/opportunity_context_preservation_2025.json`

Source-available fields that remain private include `yardline_100`, `down`,
`ydstogo`, and `offense_snaps`. Absence from V1 public JSON does not mean those
source dimensions were discarded.

## Verification authority

Required verification includes:

- Python exporter unit and failure-injection tests;
- Python validation of active and historical registries;
- exact source-to-export parity for all report families and all four views;
- Home membership/order and composition parity;
- deterministic byte/hash checks;
- frontend Zod/registry validation;
- fixture/export isolation;
- production Next.js build;
- fixture, active-export, and historical-export browser suites;
- CI review artifacts and screenshots.
