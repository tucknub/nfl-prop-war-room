# DepthSnap Public App Migration

## Decision

PropWar will leave Streamlit as the public product surface under the public product name **DepthSnap — NFL Role Intelligence**.

The existing Python research and current-season operations remain the calculation authority. A new Next.js application will become the public interface after it reaches feature and data parity. Streamlit remains available as a private fallback and research/admin surface during migration.

## Product outcome

The public product should help an NFL researcher complete this path quickly:

1. Open DepthSnap.
2. See the most important documented role changes immediately.
3. Choose a team, player, or one of the three reports.
4. Inspect the raw player opportunities and matching team total.
5. Share or bookmark the exact view.

The public product remains descriptive and evidence-first. It will not add odds, picks, projections, fantasy recommendations, a universal score, or unavailable tracking fields.

## Architecture

```text
Existing Python pipeline
  -> validates canonical role data
  -> publishes deterministic web JSON bundles
  -> commits bundles and manifests to the repository

apps/web (Next.js App Router)
  -> reads validated JSON bundles
  -> renders public pages and interactions
  -> performs no independent role calculations
  -> deploys from the same repository through Vercel
```

### Normative Phase 4A contract

`docs/depthsnap/PHASE4A_CONTRACT_DECISIONS.md` is the normative source for public schema names, data modes, numeric semantics, manifest hashing, identity references, loader behavior, and authority boundaries.

When this migration overview and the normative contract differ, the normative contract controls. An implementation conflict must be documented and resolved rather than silently changing the contract.

### Repository layout

```text
apps/
  web/
    src/app/
    src/components/
    src/lib/
    public/data/depthsnap/

src/
  operations/

dashboard/
  # Existing Streamlit fallback/admin surface

outputs/
  role_research/
  web_exports/
```

## Data contract

The Python layer will generate web-ready JSON from validated canonical files. The frontend must not recalculate authoritative shares from unrelated source rows.

Initial bundle set:

```text
outputs/web_exports/manifest.json
outputs/web_exports/status.json
outputs/web_exports/home.json
outputs/web_exports/reports/index.json
outputs/web_exports/reports/backfield-control.json
outputs/web_exports/reports/target-hierarchy.json
outputs/web_exports/reports/role-movement.json
outputs/web_exports/teams/index.json
outputs/web_exports/teams/{TEAM_ID}.json
outputs/web_exports/players/index.json
outputs/web_exports/players/{PLAYER_ID}.json
outputs/web_exports/search.json
```

Each public finding must retain:

- season and through-week
- player ID, name, team, and position
- role family
- raw player opportunities
- matching team opportunities
- authoritative all-play share
- typical-game supporting share when available
- current and prior values for Role Movement
- data-quality and partial-game status
- source/build version

The manifest must include bundle paths, hashes, schema versions, data mode, source season, published-through week, generated timestamp, and validation metadata.

## Public routes

```text
/                         Role Change Feed
/reports                  Three-report overview
/reports/backfield        Backfield Control
/reports/targets          Target Hierarchy
/reports/movement         Role Movement
/teams                    Team directory/search
/teams/[team]             Unified Team Snapshot
/players                  Player search
/players/[playerId]       Player evidence page
/search                   Team/player search
/methodology              Plain-language methodology
/data-status              Freshness and validation status
```

Advanced Research will remain in Streamlit initially. It will not block the public migration.

## First public screen

The Home page will not begin with product explanation cards. It will begin with the latest available findings:

- biggest backfield-control change
- biggest target-hierarchy change
- most concentrated role
- clearest committee
- newest material role movement

Report shortcuts, data status, and methodology will support those findings rather than precede them.

## Design requirements

- Mobile-first application layout, not a desktop dashboard compressed onto a phone
- Compact top navigation and mobile bottom navigation or sheet
- No permanent wide sidebar
- Strong list/table rhythm rather than repeated large cards
- Current-versus-prior visual comparisons
- Share bars and direction indicators where they clarify the data
- Every share visibly connected to its raw numerator and team denominator
- Exact filtered views represented in the URL
- Designed loading, empty, unavailable, stale-data, and contract-failure states
- Keyboard and screen-reader accessible controls
- No hosted-platform branding or development controls

## Technology

- Next.js App Router
- TypeScript
- React Server Components for initial data rendering
- Small client components only for search, filters, sorting, drawers, and mobile navigation
- Existing shared CSS tokens and approved components in `apps/web`
- A lightweight runtime schema library for Phase 4A; Zod is acceptable
- Playwright for desktop and mobile workflow verification
- Vercel deployment from `apps/web` after parity approval

Do not introduce Tailwind CSS, shadcn/ui, or another component system in Phase 4A merely because an earlier plan mentioned them. The approved interface already has a coherent styling and component foundation. A design-system migration would require a separate decision and is not part of the data-contract work.

No database is required for the first release. Validated JSON bundles are sufficient for the read-only product and keep the Python pipeline authoritative.

## Migration phases

### Phase 0 — Contract and concept

- Lock the architecture.
- Generate and approve desktop and mobile concepts.
- Approve the Home feed, report table, team snapshot, player evidence, navigation, and status states.
- Define initial typed fixtures.

### Phase 1 — Frontend foundation

- Scaffold `apps/web`.
- Add typography, tokens, app shell, navigation, responsive layout, metadata, loading, error, and not-found states.
- Load committed fixtures through typed server-side helpers.

### Phase 2 — Core public experience

- Role Change Feed
- Backfield Control
- Target Hierarchy
- Role Movement
- Shared report controls and shareable URLs

### Phase 3 — Identity and evidence navigation

- Team directory and Team Snapshot
- Player directory and player evidence page
- Global team/player search
- Exact weekly chronology and cross-route evidence links

The identity experience is approved. Methodology and Data Status are completed in Phase 4A because they depend on the frozen publication and validation contract.

### Phase 4A — Public trust surfaces and contract freeze

- Implement `/methodology` from supplied definitions and authority boundaries.
- Implement `/data-status` from supplied publication, source, build, validation, and hash metadata.
- Replace fixture-specific schema names and flags with production-neutral runtime schemas.
- Add the manifest and one server-side loader/registry boundary.
- Validate fixtures through the same schemas required of later Python exports.
- Eliminate direct route imports from fixture modules.
- Test published, no-published-week, unavailable, missing, invalid, incompatible, and hash-mismatch states.
- Do not connect live Python exports, merge, deploy, or change Streamlit production during this phase.

### Phase 4B — Python export bridge

- Generate deterministic JSON bundles from validated canonical outputs.
- Validate schemas, references, record counts, and file hashes.
- Add parity tests against Streamlit/Python calculations.
- Copy approved bundles into the web deployment input during CI.
- Preserve the no-publish preseason state and last-known-good publication behavior.

### Phase 5 — Deployment and cutover

- Deploy branch previews to Vercel.
- Verify mobile and desktop with Playwright.
- Run side-by-side data parity checks.
- Assign the public domain only after parity and usability approval.
- Keep Streamlit available privately as rollback/admin tooling.

## Release gates

The public cutover is blocked until:

- every displayed share matches the Python authority
- all three report families match existing report output
- team and player links reconcile to canonical identity bundles
- every public route consumes the validated loader boundary
- all required bundles and manifest hashes validate
- mobile and desktop core workflows pass
- no horizontal overflow, page errors, or relevant console errors remain
- status, stale-data, and contract-failure states are accurate
- the 2026 no-publish preseason behavior remains unchanged
- a rollback path to the Streamlit public app is documented

## Explicit non-goals for V1

- Authentication
- Subscriptions or payments
- Personalized watchlists
- Notifications
- AI chat
- Odds or sportsbook integrations
- Forecasting or recommendations
- Rebuilding Advanced Research
- Rewriting the Python pipeline in TypeScript
- Migrating to a different frontend design system during contract work

Those features require evidence of repeated use after the public product is easier to understand and navigate.
