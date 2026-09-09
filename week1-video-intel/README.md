# NFL Video Intel

This directory contains the static NFL Video Intel application and its reusable source.

## Data packages

- Production packages live in `public/data/{season}/week-{NN}.json`.
- `public/data/manifest.json` controls the real weeks exposed by the production selector.
- `fixtures/data/` is test-only and is not copied into the production build.
- The Week 1 package is the production dataset extracted without factual edits from the previous embedded application data.

## Commands

Run these commands from this directory:

```text
npm install
npm test
npm run dev
npm run build
npm run release
```

`npm run build` writes a disposable verification build to `preview-dist/`. `npm run release` updates the static `index.html`, `assets/`, and `data/` artifacts served by the production URL.

The UI, category taxonomy, status rules, Research Strength v2 calculation, source grouping, and local-storage namespace are week-agnostic. Adding a real week requires a schema-compatible production package plus a manifest entry; it does not require component changes.

Independent-source grouping uses the canonical video URL when present, so multiple labels or timestamps from one YouTube video still count once. The original dataset's declared source counts remain available for parity auditing even when canonical recomputation identifies a mismatch.
