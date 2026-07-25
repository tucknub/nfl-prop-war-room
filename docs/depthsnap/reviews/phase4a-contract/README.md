# DepthSnap Phase 4A.1 contract review

Implementation commit: [`787d9ff392d83f9955a67317555ed964d817a30a`](https://github.com/tucknub/nfl-prop-war-room/commit/787d9ff392d83f9955a67317555ed964d817a30a)

GitHub Actions: [DepthSnap Web run 30162156930](https://github.com/tucknub/nfl-prop-war-room/actions/runs/30162156930) completed successfully. CI used `npm ci`, validated and measured the registry before typecheck, completed the production build, ran all Chromium tests, and uploaded phase-neutral browser evidence.

## Phase 4A.1 correction gate

- Production requires an explicit `DEPTHSNAP_DATA_MODE=fixture|export`. An unset mode fails closed outside explicitly scoped development. Playwright declares fixture mode explicitly.
- Export mode reads only `public/data/depthsnap/export/manifest.json`; a missing or invalid export registry renders the contract-failure surface and never falls back to fixtures.
- The common bundle contract now uses production-neutral `dataNotice`; the fixture notice renders only when `dataMode === "fixture"`.
- Manifest metadata now includes `productId`, `publicationStatus`, `validationResult`, `season`, `throughWeek`, `formulaVersion`, and `pipelineRunId`.
- Status checks now carry supplied `required` and `blocking` flags, optional raw coverage (`numerator`, `denominator`, `percentage`), and the closed status vocabulary `pass | fail | attention | unavailable | reviewed | not_applicable`.
- Methodology includes a semantic evidence glossary.
- Data Status includes keyboard- and screen-reader-labeled SHA-256 copy actions on desktop and mobile.
- The validated registry is cached for the server process lifetime. The measured cold load read 45 files (manifest plus 44 bundles); the warm request reused the same promise and read zero additional files.
- The complete handoff contract is documented in [`EXPORT_CONTRACT.md`](../../EXPORT_CONTRACT.md).

## Generated registry inventory

All three fixture registries were regenerated after the schema change:

- `fixture` (`published`)
- `fixture-no-published-week`
- `fixture-unavailable`

Each registry declares 44 required bundles and uses deterministic sorted compact UTF-8 JSON with one trailing newline and manifest-declared SHA-256 hashes.

## Verification

- `npm ci`: passed; 34 packages installed, 35 audited.
- `npm run validate:data`: passed all three 44-bundle registries, deterministic serialization, export isolation, and explicit mode selection.
- `npm run measure:data`: passed; cold load 44 entries / 45 files / 173,741 bytes, warm load 1 hit / 1 miss / 0 additional reads.
- `npm run typecheck`: passed.
- `npm run build`: passed without warnings; 12 application routes compiled.
- `npm run test:e2e`: 42 passed in 24.3 seconds.
- `git diff --check`: passed.
- Glossary browser assertions: passed for all seven terms.
- SHA copy assertions: passed for exact clipboard content, accessible labeling, live confirmation, and mobile visibility.

## Dependency audit

`npm audit --json` reports 3 high-severity findings and 0 critical findings. They are inherited through Next.js 16.2.11 via `postcss` and `sharp`. npm proposes an invalid downgrade to Next.js 9.3.3, so versions were not changed to hide the audit result. `zod` is pinned exactly to `4.4.3`; `tsx` is pinned exactly to `4.23.1`.

## Screenshots

### Methodology and Data Status

- [Desktop Methodology](desktop-methodology.png)
- [Mobile Methodology](mobile-methodology.png)
- [Desktop Data Status](desktop-data-status.png)
- [Mobile Data Status](mobile-data-status.png)

### Fail-closed export mode

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
- The Python exporter and production export registry are intentionally not implemented.
- No production export bundle is committed; explicit export mode therefore demonstrates the reviewed `bundle_missing` failure state.
- Partial-game handling remains a Python-authoritative supplied flag and reviewed override; the frontend does not infer or repair it.
- The three high-severity dependency audit findings remain open pending an appropriate tested upstream maintenance release.
- Nothing was merged, deployed, connected to a domain, or changed in Streamlit production.
