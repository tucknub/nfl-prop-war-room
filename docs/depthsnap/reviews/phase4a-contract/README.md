# DepthSnap Phase 4A contract review

Implementation commit: [`97e1b0b3d09a6dfade1a93be36088b08992a911c`](https://github.com/tucknub/nfl-prop-war-room/commit/97e1b0b3d09a6dfade1a93be36088b08992a911c)

GitHub Actions: [DepthSnap Web run 30054679113](https://github.com/tucknub/nfl-prop-war-room/actions/runs/30054679113) completed successfully. The job validated data contracts before typecheck, then completed the production build, Chromium verification, and browser-evidence upload.

## Delivered routes

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

Every route reads through the shared server-side registry/loader boundary. Export mode reads only the export registry and fails closed when that registry is absent; it never falls back to fixture data.

## Runtime contracts and bundle inventory

The V1 runtime schema inventory is:

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

Three deterministic registries are committed: `published`, `no_published_week`, and `unavailable`. Each manifest declares 44 required bundles: Home, reports index, three report families, teams index, eight team dossiers, players index, 27 player dossiers, search, and status. Bundles use sorted compact UTF-8 JSON with one trailing newline and manifest-declared SHA-256 hashes.

## Verification

- `npm ci`: passed; 34 packages added and 35 packages audited.
- `npm run validate:data`: passed all three 44-bundle registries, deterministic serialization, manifest/schema validation, and export-mode isolation.
- `npm run typecheck`: passed.
- `npm run build`: passed; all 12 application routes compiled.
- `npm run test:e2e`: 39 passed in 31.2 seconds.
- `git diff --check`: passed.
- Direct route/component imports from the old fixture modules: none. Legacy fixture modules remain only behind the deterministic generation boundary.

Contract tests cover share/count consistency, duplicate identities, unresolved references, unsupported schemas, wrong families and paths, invalid JSON, missing files, missing manifest families, hash/count mismatches, fixture/export isolation, and the absence of silent fallback. Browser tests cover published, no-week, unavailable, contract-failure, accessibility, desktop/mobile overflow, console/page errors, and all previously approved workflows.

## Dependency audit

`npm audit --json` reports three high-severity findings and no critical findings. They are inherited through Next.js 16.2.11 via `postcss` and `sharp`. npm proposes an invalid product downgrade to Next.js 9.3.3, so dependency versions were not changed during this contract phase. The advisories should be reviewed against an appropriate tested Next.js maintenance release.

## Visual review

The Phase 1 visual reference was compared directly with these screenshots. The approved near-black blue-green canvas, layered graphite/slate surfaces, restrained teal and amber accents, header geometry, sports typography, exact raw-count density, hero media, and mobile clearance were preserved. Existing Feed, report, team, player, and search layouts were not redesigned.

Above the fold, existing workflows retain their approved copy except for production-neutral labels such as “supplied” and stable player IDs. The new Methodology route leads with “Read the count before the share.” The new Data Status route leads with “Publication integrity, in public.” Both use the existing visual language and route shell.

## Screenshots

### Methodology and Data Status

- [Desktop Methodology](desktop-methodology.png)
- [Mobile Methodology](mobile-methodology.png)
- [Desktop Data Status](desktop-data-status.png)
- [Mobile Data Status](mobile-data-status.png)

### Contract failure

- [Desktop export-mode contract failure](desktop-contract-failure.png)
- [Mobile export-mode contract failure](mobile-contract-failure.png)

### Existing-route regression evidence

- [Desktop Home](desktop-home-regression.png)
- [Mobile Home](mobile-home-regression.png)
- [Desktop Backfield Control](desktop-backfield-regression.png)
- [Mobile Backfield Control](mobile-backfield-regression.png)
- [Desktop team dossier](desktop-team-regression.png)
- [Desktop player dossier and weekly timeline](desktop-player-regression.png)
- [Desktop search](desktop-search-regression.png)

## Known limitations

- All public evidence is still synthetic design-fixture data.
- The real Python export bridge is intentionally not connected.
- No export bundle is committed; selecting export mode therefore produces the reviewed `bundle_missing` failure state with no fixture fallback.
- Partial-game handling remains limited to the Python-authoritative supplied flag and manual review described in Methodology; the frontend does not infer or repair it.
- The dependency audit findings above remain open.
- No merge, deployment, domain connection, or Streamlit production change was performed.
