# Current Phase

## Phase A — Correctness Fixes

**Status:** Active

**Production deployment:** Not authorized

**Audit baseline:** `8b759f18c34708300acf5e3ef84d0e4cbbbde597`
**Starting audit commit:** `e939b886c9b75d6a06eaf9bf95dc8ec1a1e093ad`

**Working branch:** `propwar-correctness-fixes-v1`

## Objective

Correct the five High findings from the targeted audit, rerun the unchanged audit samples, and reach zero unresolved Critical or High findings before any additional workflow or visual redesign.

## Allowed work

- Confirmed corrections for selected-week integrity, situational denominators, Explorer eligibility, Report context selection, and player/team URL state.
- Focused regression tests and after-fix validation artifacts.
- This phase-status document.

## Prohibited work

- Public page redesign or visual changes.
- Detector research or rule changes.
- Odds, betting recommendations, scores, or predictive claims.
- Changes to canonical statistical definitions or historical validation artifacts.
- Merge, production push, or deployment.

## Exit condition

Phase A passes only when the corrected audit reports no unresolved Critical or High issue and every gate in `PHASE_GATES.md` passes. Passing does not authorize a redesign, merge, push, or deployment.
