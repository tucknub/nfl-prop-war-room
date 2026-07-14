# Current Phase

## Phase A — Targeted Correctness Audit

**Status:** Active

**Production deployment:** Not authorized

**Audit baseline:** `8b759f18c34708300acf5e3ef84d0e4cbbbde597`
**Audit branch:** `propwar-targeted-correctness-audit-v1`

## Objective

Verify that public calculations, windows, rankings, links, filters, participation handling, session state, and cross-page values are correct before any additional workflow or visual redesign.

## Allowed work

- New audit scripts, tests, notebooks, and reports.
- Project-control documentation under `docs/propwar/`.
- Confirmed correctness fixes only when required to make the audit executable.

## Prohibited work

- Public page redesign or visual changes.
- Detector research or rule changes.
- Odds, betting recommendations, scores, or predictive claims.
- Changes to canonical statistical definitions or historical validation artifacts.
- Merge, production push, or deployment.

## Exit condition

Phase A passes only when its reproducible audit is complete with no unresolved Critical or High issue and every gate in `PHASE_GATES.md` passes. After the audit commit, the only authorized next action is to wait for the user's screen-recording review.
