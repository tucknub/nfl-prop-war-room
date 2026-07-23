# DepthSnap Phase 4A — Codex Handoff

Status: **Ready for implementation on the open migration branch**

## Start here

Repository: `tucknub/nfl-prop-war-room`

Working branch: `propwar-nextjs-public-v1`

Open PR: `#9 — Build DepthSnap public Next.js app`

Before editing:

```bash
git fetch origin
git switch propwar-nextjs-public-v1
git pull --ff-only origin propwar-nextjs-public-v1
git status --short
```

The working tree must be clean.

Read in this order:

1. `docs/depthsnap/PHASE4A_CONTRACT_DECISIONS.md`
2. `docs/propwar/NEXTJS_PUBLIC_APP_MIGRATION.md`
3. this handoff
4. existing fixture types and data composition under `apps/web/src/lib` and `apps/web/src/data`
5. the current Python operational contract in `src/operations/current_role_pipeline.py` and `src/operations/published_validation.py`

The contract-decisions file is normative. Do not silently reinterpret it.

## Objective

Complete the final fixture-backed trust and contract phase before any real Python export is connected.

Deliver:

- a complete Methodology route;
- a complete Data Status route;
- production-neutral runtime schemas;
- deterministic fixture JSON bundles and manifest;
- one server-side loader/registry boundary used by every public route;
- public-safe contract failure states;
- tests and browser evidence.

Do not connect production Python exports in this phase.

## Required implementation order

### 1. Inventory before refactoring

Create a concise inventory of:

- every current route-level fixture import;
- every distinct evidence value duplicated across fixture modules;
- every current schema/version discriminator;
- every stable team/player reference;
- every route state currently supported through query parameters.

Use the inventory to avoid losing existing approved behavior during normalization.

### 2. Add runtime schema primitives

Add a lightweight runtime schema library. Zod is acceptable.

Define shared schemas first:

- `dataMode`
- publication status
- timestamps and season/week metadata
- player and team identity
- raw share evidence
- movement evidence
- data quality
- report family
- typed loader failure
- manifest entry and manifest

Derive TypeScript types from schemas where practical. Avoid maintaining separate incompatible interfaces.

Raw evidence validation must enforce the numeric rules in the normative contract, including consistency between `share` and `numerator / denominator` within a documented small tolerance.

Do not coerce malformed production values merely to pass validation.

### 3. Define the V1 bundle schemas

Implement exactly these public schemas:

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

Every bundle must carry `dataMode` separately from `schemaVersion`.

The schemas must represent all three publication states without fabricating evidence.

### 4. Normalize fixture bundles

Convert the approved fixture evidence into deterministic JSON bundles under a single clearly named fixture directory.

Recommended deployment-shaped location:

```text
apps/web/public/data/depthsnap/fixture/
```

The exact internal build path may differ, but the loader must not require route components to know it.

Requirements:

- one canonical identity record per stable player/team ID;
- no unresolved references;
- supplied authoritative order retained explicitly;
- cross-route evidence values identical;
- all required bundles listed in the manifest;
- deterministic serialization and hashes;
- visible fixture notice driven by `dataMode`.

Do not duplicate fixture values into route-specific TypeScript constants after creating bundles.

### 5. Add one server-side loader boundary

Create one loader/registry API for all public pages.

It must:

1. read `DEPTHSNAP_DATA_MODE`;
2. load the selected manifest;
3. validate manifest schema and mode;
4. resolve the requested bundle family/path;
5. verify its SHA-256 hash;
6. parse and validate the runtime schema;
7. validate identity references and declared record counts;
8. return typed data or a typed public-safe failure.

Rules:

- fixture mode loads fixture bundles only;
- export mode loads export bundles only;
- export mode never falls back to fixtures;
- unsupported mode fails safely;
- route components do not import fixture modules directly after migration;
- loader errors are distinct from valid bundle publication states.

### 6. Migrate every public route

Migrate:

- `/`
- `/reports`
- `/reports/backfield`
- `/reports/targets`
- `/reports/movement`
- `/teams`
- `/teams/[team]`
- `/players`
- `/players/[playerId]`
- `/search`
- `/methodology`
- `/data-status`

Preserve approved URLs, responsive behavior, accessibility, and evidence formatting.

After migration, a repository search should show no route/component import from the old fixture data modules except inside the fixture generation/build boundary if deliberately retained.

### 7. Build Methodology

Methodology must explain only supplied definitions and the existing Python authority.

Required sections:

- what DepthSnap measures;
- Backfield Control;
- Target Hierarchy;
- Role Movement;
- numerator, denominator, and share;
- all-play authority versus normal-game supporting context;
- current/prior comparison and percentage-point change;
- completed-week gate;
- identity and snap coverage expectations;
- partial-game handling and its limitation;
- closed data-quality labels;
- descriptive-not-predictive scope;
- links to Data Status and the three reports.

Do not reproduce Python thresholds or formulas in TypeScript to generate classifications.

### 8. Build Data Status

Data Status must display supplied metadata rather than deriving a new publication verdict.

Required presentation:

- publication state;
- data mode;
- season and published-through week;
- generated timestamp;
- source version;
- optional formula/pipeline run versions when supplied;
- manifest schema/version;
- bundle count and validation summary;
- source/build checks supplied by the bundle;
- hashes in a readable expandable or compact presentation;
- limitations;
- stale/no-week/unavailable states;
- public-safe loader/contract failure details.

Do not expose local paths, stack traces, secrets, tokens, or private source URLs.

### 9. Add automated checks

At minimum, add tests for:

- every fixture bundle validates;
- deterministic manifest and hashes;
- share/count consistency;
- duplicate team/player IDs;
- unresolved references;
- wrong bundle family;
- unsupported schema version;
- invalid JSON;
- missing required bundle;
- manifest path mismatch;
- hash mismatch;
- record-count mismatch;
- fixture/export mode isolation;
- no silent fixture fallback in export mode;
- published state;
- no-published-week state;
- unavailable state;
- Methodology and Data Status accessibility;
- all current route workflows on desktop and mobile;
- no horizontal overflow;
- no relevant console, page, or application errors.

Add a dedicated contract-validation script if useful, for example:

```bash
npm run validate:data
```

CI must run it before build/browser verification.

### 10. Produce review evidence

Return:

- concise implementation summary;
- changed-file list grouped by purpose;
- runtime schema inventory;
- manifest/bundle inventory;
- commands executed and results;
- desktop and mobile screenshots for Methodology and Data Status;
- screenshots of at least one contract-failure state;
- evidence that existing Home, report, team, player, and search routes did not regress;
- final branch head SHA;
- any unresolved conflict with the normative contract.

Store review assets under a new Phase 4A review directory without replacing earlier approved evidence.

## Required commands before completion

Run from `apps/web` unless the script requires repository root:

```bash
npm ci
npm run typecheck
npm run build
npm run test:e2e
```

Also run the new data-contract validation command added during this phase.

A successful build alone is not completion.

## Stop conditions

Stop and report rather than guessing when:

- the normative contract conflicts with a Python-authoritative output;
- a required evidence value cannot be represented without recalculation;
- identity references cannot be resolved deterministically;
- fixture and export modes cannot be isolated;
- an existing approved route would require a product-level redesign;
- the change would modify Python formulas, publication gates, Streamlit production, deployment, or the production branch.

Continue with independent work that is not blocked by the conflict.

## Explicit prohibitions

Do not:

- merge PR #9;
- deploy Vercel;
- change the public domain;
- replace or disable Streamlit;
- alter Python role formulas or operational gates;
- connect live Python outputs;
- introduce odds, picks, projections, recommendations, fantasy advice, accounts, payments, alerts, or AI chat;
- introduce Tailwind/shadcn or redesign the approved interface as part of contract work;
- silently fall back to fixture data in export mode;
- create authority rankings, findings, classifications, or publication verdicts in TypeScript.

## Completion definition

Phase 4A is complete only when:

- Methodology and Data Status are fully implemented and reviewed;
- every fixture bundle validates through production-neutral schemas;
- every route uses the single loader boundary;
- failure states are safe and understandable;
- fixture/export isolation is tested;
- existing approved routes remain visually and functionally intact;
- CI and browser verification are green;
- no deployment or merge has occurred.
