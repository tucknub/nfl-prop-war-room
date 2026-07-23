# DepthSnap Phase 4A Contract Decisions

Status: **Normative for Phase 4A and the later Python export bridge**

This file freezes decisions that must be settled before runtime schemas, manifests, and public loaders are implemented. Codex may refine implementation details, but it must not silently change these product or data-contract decisions.

## 1. Public bundles are production-neutral

Schema versions must not encode the current fixture source.

Use:

- `depthsnap.home.v1`
- `depthsnap.reports.index.v1`
- `depthsnap.report.backfield.v1`
- `depthsnap.report.targets.v1`
- `depthsnap.report.movement.v1`
- `depthsnap.teams.index.v1`
- `depthsnap.team.v1`
- `depthsnap.players.index.v1`
- `depthsnap.player.v1`
- `depthsnap.search.v1`
- `depthsnap.status.v1`
- `depthsnap.manifest.v1`

Do not use `.fixture.` or `.export.` in a schema version. Data origin is represented separately by `dataMode`.

## 2. Data mode is explicit and separate

Every bundle and the manifest must contain:

```json
{"dataMode":"fixture"}
```

or:

```json
{"dataMode":"export"}
```

`DEPTHSNAP_DATA_MODE` selects the loader mode.

- Fixture mode may load only validated fixture bundles.
- Export mode may load only validated exported bundles.
- Export mode must never silently fall back to fixture data.
- The visible fixture notice is driven by `dataMode`, not by a fixture-specific schema.

## 3. JSON field naming

Public DepthSnap JSON uses `camelCase`.

The Python exporter is responsible for mapping internal snake_case columns and operational files to the public camelCase contract. Existing Python source files and canonical CSV columns do not need to be renamed.

## 4. Share and movement numeric semantics

`RawShareEvidence` uses:

- `numerator`: non-negative integer
- `denominator`: positive integer
- `share`: decimal ratio from `0` through `1`, inclusive
- `opportunityLabel`: `opportunities`, `carries`, or `targets`

Example:

```json
{
  "numerator": 27,
  "denominator": 34,
  "share": 0.7941176471,
  "opportunityLabel": "opportunities"
}
```

The UI formats `share` as `79.4%`.

`percentagePointChange` is expressed in percentage points, not as a decimal ratio. A movement from `0.563` to `0.794` is approximately `23.1`, not `0.231`.

Runtime validation must reject:

- denominator less than 1
- numerator less than 0
- numerator greater than denominator
- share outside `[0, 1]`
- a supplied share that materially disagrees with `numerator / denominator`

Use a documented small numeric tolerance for serialization/rounding. Do not silently rewrite a mismatched supplied share.

These conventions match the current Python authority, where `metric_all`, `metric_normal`, and situational `share` are ratios produced from raw player and team counts.

## 5. Publication state and loader failure are different concepts

Bundle publication status is exactly:

- `published`
- `no_published_week`
- `unavailable`

Loader/contract errors are not additional publication statuses. Model them separately with typed failure categories such as:

- `bundle_missing`
- `invalid_json`
- `invalid_bundle`
- `incompatible_schema`
- `manifest_mismatch`
- `hash_mismatch`
- `unresolved_reference`
- `unsupported_data_mode`

The Data Status page may present these failures, but an incompatible schema must not be converted into `unavailable` inside a supposedly valid bundle.

## 6. Required bundles exist in every publication state

The manifest must list every V1 public bundle family in fixture and export modes, including when no week is published.

When status is `no_published_week` or `unavailable`:

- metadata and state copy remain present;
- route-level evidence collections are empty;
- no estimated or stale evidence is substituted;
- canonical team/player identity records may remain available only when the bundle explicitly supplies them as non-evidence directory metadata;
- the UI renders the supplied state rather than inferring one from empty arrays.

This keeps route behavior deterministic and prevents the loader from treating an intentionally empty state as a missing file.

## 7. Stable identity references are opaque

- `team.id` is a stable opaque public ID. It may currently resemble an abbreviation, but consumers must not derive meaning from its format.
- `player.id` is a stable opaque public ID and should use the authoritative player identifier supplied by Python when production exports are created.
- URLs use these stable IDs.
- Team abbreviation, player name, current team, position, and aliases are display/search fields, not identity keys.
- Every referenced player and team must resolve through the canonical identity bundles.
- Duplicate IDs or unresolved references fail validation.

## 8. Data-quality values are closed

V1 public evidence quality values are exactly:

- `complete`
- `reviewed_partial_game`
- `unavailable_supporting_context`

Publication-level `unavailable` remains a bundle status, not an evidence-row quality grade.

Do not introduce numeric quality scores, confidence values, or frontend-derived grades.

## 9. Authoritative ordering is supplied

Python/fixture bundles supply:

- report rank;
- hierarchy order;
- movement order when shown as authoritative;
- supplied classifications and findings.

The frontend may apply an explicit user-selected presentation sort, alphabetical directory ordering, or search relevance ordering. It must not create the default authority ranking or classify roles from thresholds.

Current fixture composition that derives dossier rows from report fixtures may remain internally normalized, but the frozen export schemas must carry supplied order explicitly. Phase 4A loaders and validation should make this boundary clear.

## 10. Manifest and hashing

The manifest is `depthsnap.manifest.v1` and contains one entry per public bundle.

Each bundle entry includes at least:

- `family`
- `path`
- `schemaVersion`
- `sha256`
- `required`
- `recordCount` when meaningful

Hash rules:

- SHA-256 lowercase hexadecimal;
- hash the exact UTF-8 bytes written to the bundle file;
- exported JSON uses deterministic serialization;
- deterministic Python serialization target: `sort_keys=True`, compact separators, UTF-8, `ensure_ascii=False`, plus one final newline;
- the manifest does not include a self-hash;
- no absolute paths, credentials, tokens, or private URLs appear in public bundles.

Phase 4A may validate fixture hashes using the same rules. Cryptographic signing is out of scope.

## 11. Time and version fields

- Timestamps use RFC 3339 UTC, for example `2026-07-23T19:35:27Z`.
- `season` is an integer.
- `throughWeek` is an integer for `published` and may be `null` for `no_published_week` or `unavailable` where no authoritative week exists.
- `sourceVersion`, optional `formulaVersion`, and optional `pipelineRunId` are supplied strings.
- The frontend displays these values but does not manufacture them.

## 12. One loader boundary

After Phase 4A, route components must not import fixture modules directly.

All route data flows through one server-side loader/registry boundary that:

1. reads the selected mode;
2. loads the manifest;
3. verifies the manifest schema and mode;
4. locates the requested bundle family;
5. verifies the file hash where applicable;
6. validates the runtime schema;
7. verifies stable references and declared record counts;
8. returns typed data or a typed public-safe failure.

Fixture bundles must pass the exact same runtime schemas as future Python exports.

## 13. Canonical fixture evidence must remain normalized

The same evidence record must agree across Feed, Reports, Team, Player, Search, Methodology examples, and Data Status references.

Phase 4A should eliminate direct route-level fixture imports and avoid adding more copied values. The current normalized identity layer is a useful foundation, but `home.presentation.fixture.ts`, report fixtures, and identity composition must be placed behind the loader boundary and validated as a coherent bundle set.

## 14. Runtime schemas are the contract authority in the web app

Use a lightweight runtime schema library. Zod is acceptable.

Prefer deriving TypeScript types from schemas or sharing schema primitives so compile-time types and runtime validation cannot drift.

Schemas fail closed on:

- unsupported version;
- wrong bundle family;
- malformed data;
- invalid raw evidence;
- unresolved identity;
- duplicate stable ID;
- missing required bundle;
- manifest/hash mismatch;
- record-count mismatch.

Do not coerce malformed production values simply to make a bundle pass.

## 15. Phase 4A product copy is decided outside the loader

Methodology explains supplied evidence and the Python authority. Data Status displays supplied publication and validation results. Neither route may create operational conclusions from checks.

The final publication decision is supplied by Python. Individual checks are explanatory evidence, not frontend inputs to a new publication algorithm.

## 16. Phase 4A non-goals

Do not in Phase 4A:

- connect the real Python exporter;
- change Python formulas or publication gates;
- deploy Vercel;
- merge PR #9;
- replace Streamlit production;
- add accounts, payments, alerts, odds, projections, recommendations, or fantasy advice;
- add cryptographic signing;
- make future schema versions backward-compatible automatically.

## 17. Acceptance gate before the Python bridge

Phase 4A is complete only when:

- Methodology and Data Status are approved on desktop and mobile;
- every fixture bundle validates through runtime schemas;
- every route consumes the loader boundary rather than fixture modules;
- `npm run validate:data` fails on malformed, incompatible, missing, mismatched, and unresolved test cases;
- fixture and export modes cannot be confused or silently substituted;
- the manifest and schema compatibility rules are documented;
- existing Phase 1–3 screenshots have no unintended visual regression;
- CI runs data validation before typecheck, build, and browser verification.
