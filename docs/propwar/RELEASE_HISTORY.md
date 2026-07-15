# PropWar Release History

## Correctness Release v1

- Production commit: `78edeede7b0aac77daf2d7abca863993dd6a6920`
- Previous production commit: `8b759f18c34708300acf5e3ef84d0e4cbbbde597`
- Deployment date: 2026-07-14
- Rollback checkpoint: `production-streamlit-cloud-pre-correctness-v1`
- Validation: 20 focused tests passed; full repository suite 66 passed; compilation, corrected audit, descriptive-data, cross-page, link/state, Explorer, public-language, protected-file, and Git whitespace checks passed.
- Resolved High defects: Home selected-week integrity; Teams/Reports situational denominators; Explorer eligible zero-opportunity games; situational Report context selection; player/team URL and session-state handling.
- Corrected audit: 0 Critical findings, 0 High findings, 0 wrong-week Home rows, 0 situational denominator failures, 0 Explorer zero-opportunity failures, 0 Report-context failures, 0 invalid player/team state failures, and 0 cross-page mismatches.
- Remaining Medium findings: traded-player selector team labeling; missing team deep links; omitted game score, inside-five, and one-play production displays.
- Remaining Low finding: sparse-chart Vega infinite-extent warnings.
- Live QA: passed on desktop 1440×900 and portrait 390×844; all public routes loaded, valid/invalid player and team URLs behaved correctly, all three affected Reports honored context, Explorer matched corrected audit samples and Reset defaults, Research Admin remained hidden, and no live exception or console error occurred.
- Project transition: Phase A closed; Phase B — Weekly Product Redesign is active. Phase B deployment is not automatically authorized.

## `8b759f18c34708300acf5e3ef84d0e4cbbbde597`

- Production branch: `streamlit-cloud-deploy`
- Release: mobile-first public Role & Usage Research interface
- Public pages: Home, Teams, Players, Games, Reports, Explorer
- Default completed season: 2025
- Rollback checkpoint: `production-streamlit-cloud-pre-mobile-ux-v2`
- Phase A audit baseline: this commit

## Phase A audit branch

- Branch: `propwar-targeted-correctness-audit-v1`
- Purpose: correctness evidence and project control only
- Production effect: none authorized

Future production releases must record the production commit, date, scope, validation result, rollback point, and deployment authorization.
