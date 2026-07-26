# DepthSnap Phase 4B authority gap report

Date: 2026-07-25

Starting branch head: `de7b6ce72e457b1aa5e5599676b8e858f6dfe188`

Resolution date: 2026-07-26

Status: **Resolved by PR #9 normative decisions; Phase 4B implementation resumed.**

This report preserves the original Phase 4B authoritative-input audit and stop
conditions. The newest PR #9 comment titled “Phase 4B normative decisions —
resume authorization” supplied a decision for every stop condition and
authorized the pre-production V1 contract to be amended in place. The
implementation does not change Python calculations, thresholds, report
membership, ordering, completed-week gates, partial-game rules, or Streamlit
production.

## Resolution record

The authorization established:

- the exact four neutral Home finding slugs;
- removal of unsourced `classificationLabel` and `movementLabel`;
- a closed `roleFamily` to `roleLabel` mapping;
- optional team and player narrative fields;
- separate participation-quality and supporting-context dimensions;
- exporter-time `generatedAt` and content-addressed exact-source
  `sourceVersion`;
- active 2026 `no_published_week` publication;
- a temporary, isolated completed-2025 historical parity registry;
- ATL crosswalk completion;
- team-neutral player identities with `currentTeam` and per-row
  `evidenceTeam`;
- deterministic exporter, validation, parity, atomic promotion, rollback,
  cleanup, and frontend export-mode verification.

The amended contract is `EXPORT_CONTRACT.md`; the implementation and evidence
record is `PHASE4B_EXPORTER_AND_PARITY_BRIDGE.md`. The sections below remain as
the historical explanation of why work originally stopped.

## Original safe conclusion

The repository has enough authority to implement deterministic serialization,
exact-byte hashing, registry validation, staging, rollback, and publication
state handling. It does not currently have enough authority to generate a
truthful populated V1 registry without either changing the frozen public
contract or introducing new Python presentation/methodology policy.

Per the Phase 4B stop conditions, populated exporter work must stop until the
conflicts below receive an explicit normative decision.

## Authoritative input inventory

| Public requirement | Existing authority | Result |
|---|---|---|
| Season | Operational status, role manifest, canonical rows | Available |
| Published-through week | Operational status, role manifest, completion gate | Available for a live published partition |
| Publication state | `run_current_role_research.py` operational statuses | Available; a public-state mapping must remain explicit |
| Independent validation | `validate_published_role_outputs()` and builder validation | Available for a live published partition |
| Generated timestamp | Current operational status and current role manifest | Available for live runs; absent from the completed-2025 release artifacts |
| Source version | Canonical `source_version` | Available after a role build; absent from the committed 2026 preseason status |
| Formula version | No current operational field | Optional in V1 and genuinely unavailable |
| Pipeline run ID | Successful current-run `staging_run_id` | Available only after a successful current run |
| Player identity | GSIS `player_id`, supplied name, position, weekly team | Available |
| Current team | Latest valid canonical team at the supplied boundary | Available; no same-final-week ambiguity in completed 2025 |
| Team identity | Canonical team code plus the committed team crosswalk | Incomplete because ATL is absent from the crosswalk |
| All-play evidence | Canonical all-play numerator, denominator, and share | Available and validated |
| Typical-game evidence | Canonical normal-game numerator, denominator, and share | Available and validated |
| Role family | Canonical `role_family` and Python role labels | Available |
| Report membership | Existing Python report-family selection and minimum sample | Reproducible but not persisted |
| Default order | Existing Python Last-4/Share order and tie breaks | Reproducible but not persisted |
| Report rank | Position in the supplied Python order | Reproducible |
| Backfield/Target classification | No validated Python output | **Unavailable** |
| Movement label | No validated Python output | **Unavailable** |
| Movement finding | Existing Python factual copy functions | Reproducible but not persisted |
| Current movement evidence | Existing Python window summary | Available |
| Prior movement raw counts | Computed in Python, then discarded before return | Available internally; must be exposed without changing formulas |
| Home finding order | Existing weekly report builder | Available and tested |
| Home Team Snapshot selection | No Python selection contract | **Unavailable** |
| Home report-leaderboard selection | Report rows exist; no Home composition contract | **Unavailable** |
| Data quality and partial games | Canonical quality and partial-game fields | Available internally; frozen public vocabulary is incomplete |
| Source and output hashes | Source manifests, build manifests, validation artifacts | Available |

## Current authoritative state

The latest committed operational state is
`outputs/role_research/role_research_status_2026.json`:

- status: `PRESEASON`;
- published-through week: `null`;
- generated timestamp: supplied;
- current evidence bundles: not present;
- source version: not supplied.

The completed-2025 descriptive release is independently validated and contains:

- 7,413 canonical rows;
- 7,390 public-primary rows after 23 confirmed-partial rows are excluded;
- 545 player identities;
- 32 canonical team codes;
- 52 included suspected-partial family rows;
- one canonical source version.

It is not a current operational `PUBLISHED` partition. Its release artifacts do
not supply the frozen registry's required generated timestamp. Substituting it
for the 2026 preseason state would violate the no-stale/no-prior-season rule.

## Original mandatory stop conditions

### 1. Home finding categories do not fit the frozen enum

The authoritative weekly report includes:

- Opportunity Gained;
- Opportunity Lost;
- Box Score Overstated the Role;
- Strong Opportunity, Weak Production.

The frozen Home contract only permits:

- `backfield_increase`;
- `target_share_increase`;
- `role_decline`;
- `concentrated_role`;
- `committee_formation`.

The unsupported authoritative categories are present in the tested default Home
membership and order. Filtering, relabeling, or replacing them would change
authoritative output.

### 2. Required supplied labels do not exist

No validated Python artifact supplies:

- `classificationLabel` for Backfield Control;
- `classificationLabel` for Target Hierarchy;
- `movementLabel` for Role Movement;
- team `suppliedSummary`;
- player `suppliedRoleDescription`;
- Team Snapshot selection;
- Home leaderboard selection.

Using a role-family display name would be truthful descriptive copy, but it
would not reproduce the required supplied classification.

### 3. The frozen data-quality enum cannot preserve Python policy

Python excludes confirmed partial games and retains suspected partial games with
their caveat. Completed 2025 includes:

- 48 `suspected_statistical` family rows;
- 4 `suspected_corroborated` family rows.

V1 only accepts:

- `complete`;
- `reviewed_partial_game`;
- `unavailable_supporting_context`.

Mapping statistical suspicion to `reviewed_partial_game` is false. Mapping it
to `complete` hides supplied evidence. Dropping those rows changes report
membership and order.

### 4. Required publication metadata is incomplete

- The 2026 preseason state has no `sourceVersion`.
- The completed-2025 artifacts have no source-supplied registry timestamp.
- There is no current live `PUBLISHED` partition in the branch.

A contract failure must not be converted into a valid `unavailable` registry,
and the historical release must not be silently substituted.

### 5. Team identity reconciliation is incomplete

The canonical 2025 evidence includes ATL, but the committed authoritative team
crosswalk omits ATL. An exporter must stop rather than synthesize the missing
team record.

### 6. Historical team stints exceed the frozen embedded identity shape

The completed-2025 season view contains player-team evidence rows for players
whose supplied current team differs from the evidence team. The frozen embedded
`PlayerIdentity` has only one team/current-team reference and no separate
evidence-team identity. Treating the evidence team as current, or the current
team as the evidence denominator's team, would be false.

The Last-4 default window has no such conflict among minimum-sample report rows,
but suppressing the season view would be a product-contract change.

## Safe publication-state mapping

The bridge may implement this mapping after required common metadata is
available:

| Python state | Public behavior |
|---|---|
| `PUBLISHED` plus independent validation PASS | Generate and validate `published` |
| `PRESEASON` or `WAITING_FOR_COMPLETED_WEEK` | Generate `no_published_week` with empty evidence |
| `BLOCKED` with a prior valid registry | Retain the prior valid registry |
| `BLOCKED` without a prior valid registry | Generate `unavailable` only from supplied state metadata |
| `VALIDATED_NOT_PUBLISHED` | Do not promote; retain the prior valid registry |
| Contract, loader, identity, or validation failure | Fail closed; do not downgrade to a publication state |

## Independent implementation plan after resolution

Once the normative decisions are supplied, Phase 4B can proceed without
changing calculations:

1. Read only independently validated operational outputs.
2. Normalize supplied identities and exact evidence into an exporter-side model.
3. Generate compact UTF-8 JSON with recursive key sorting and one LF newline.
4. Hash the exact bytes and build a manifest without a self-hash.
5. Validate schemas, hashes, record counts, identities, references, numeric
   consistency, publication metadata, and cross-route parity.
6. Generate into a sibling staging directory.
7. Rename the prior active directory to a rollback directory, promote the
   validated staging directory, and restore the prior directory if promotion
   fails.
8. Validate with the frozen TypeScript/Zod registry in CI as an independent
   compatibility gate.
9. Run fixture and export browser suites in separate server processes.

## Decisions required to unblock populated export

The next normative decision must address all of the following:

1. Extend or map Home finding categories without changing Python membership.
2. Supply authoritative classification/movement labels and Home composition
   rules, or explicitly redefine those fields as neutral presentation labels.
3. Extend the public data-quality vocabulary for suspected and unreviewed
   partial-game states, or define an explicitly truthful mapping.
4. Supply `sourceVersion` for non-published operational states.
5. Establish a generated-timestamp/publication descriptor for the completed
   historical release if it is intended to be the last-known-good public
   registry.
6. Add ATL to the authoritative team identity crosswalk.
7. Define how a frozen player identity represents evidence from an earlier team
   stint, or explicitly limit the exported view set.

No exporter, generated registry, screenshots, implementation commit, or review
assets should claim completion before these decisions are resolved.
