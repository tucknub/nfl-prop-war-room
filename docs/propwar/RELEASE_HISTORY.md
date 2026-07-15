# PropWar Release History

## Weekly Role Report Calibration v1

- Application commit: `87b267b30b9e2947e7ccbb9089a45f42c34eb39b`
- Previous production commit: `cec6244e0987ebfdc2e9c0138f0a707aec867887`
- Production push completed: 2026-07-15 12:19:50 EDT; the final documentation-only production commit is recorded in Git history immediately after this release entry.
- Streamlit deployment: the Git push completed successfully, but the running process initially retained stale imported modules. The supported Streamlit Community Cloud **Reboot app** operation was used, after which live Home served the calibrated application.
- Rollback checkpoint: `production-streamlit-cloud-pre-weekly-calibration-v1`, verified locally and on origin to peel exactly to `cec6244e0987ebfdc2e9c0138f0a707aec867887`.
- Validation: 25 focused calibration tests passed; the full repository suite reported 91 passed; Python compilation, seven-week replay, independent calibration validation, corrected targeted audit, cross-page, link/state, public-language, leakage, protected-file/scope, and Git whitespace checks passed on the integrated production branch.
- Seven-week replay: 79 default cards and 425 technical matches across 2025 Weeks 2, 5, 8, 11, 14, 17, and 18; every default week contained 10–12 situations; wrong-week cards, duplicate primary player-weeks, share-reconciliation failures, future-leakage failures, and multi-team label failures were all zero.
- Minnesota consolidation: live Week 8 displayed one Minnesota RB-opportunity situation with Aaron Jones primary and reciprocal evidence for Jordan Mason and Zavier Scott. Zavier Scott's technical Box Score Overstated qualification remained visible in expanded evidence.
- Target-role allocation: live default Week 17 contained 12 situations, including WR and TE target-share situations; no player appeared twice and no team had more than two cards.
- Early-season handling: live Week 2 displayed the one-game-baseline notice and all 10 cards used the explicit Week 1 baseline label.
- Week 18 handling: Week 18 remained selectable but not default, with a visible caution covering rest decisions, playoff position, and end-of-season rotations.
- Multi-team labels: live Week 18 player paths showed Adam Thielen—PIT, Brandin Cooks—BUF, Tyler Lockett—LV, Nick Vannett—LA, Marquez Valdes-Scantling—PIT, and Tank Bigsby—PHI.
- Mobile QA: exact 390×844 live Chromium checks found 390px viewport, client, and document widths; zero horizontal overflow; zero clipped cards; readable Week 2, Week 8, and Week 18 notices/evidence; operable expanders; and hit-testable Player, Team, and Game links.
- Desktop QA: exact 1440×900 live Chromium checks found zero horizontal overflow, zero clipped cards, readable category columns and consolidated evidence, matching card payloads, and no Home exception.
- Route regression: Home, Teams, Players, Games, Reports, and Explorer loaded without exception; Research Admin remained absent from public navigation; direct player, team, and game states remained deterministic.
- Remaining Medium findings: the previously documented Games omissions for score, inside-five, and one-play production displays remain outside this release's scope.
- Remaining Low finding: sparse supporting-page chart states may emit Vega infinite-extent warnings. No calibrated Home exception was observed.
- Project transition: Phase B2B — Live Calibrated Home Review is active. Production deployment during Phase B2B is not automatically authorized.

## Weekly Role Report v1

- Production commit: `54f9f0f978f1a2c6782d02b3ed61b06b8c4f00a2`
- Previous production commit: `009703cfaead7beaaef6ddf53202557b87bde744`
- Git push completed: 2026-07-15 07:46:12 EDT.
- Streamlit update event: 2026-07-15 07:46:17 EDT; a supported app reboot was required at approximately 08:11 EDT to clear the running process's stale imported-module cache.
- Rollback checkpoint: `production-streamlit-cloud-pre-weekly-role-report-v1`, verified to peel to `009703cfaead7beaaef6ddf53202557b87bde744` before push.
- Validation: 21 focused Weekly Role Report and public-language tests passed; the full repository suite reported 82 passed; Python compilation, corrected audit, historical replay, cross-page, link/state, public-language, protected-file, and Git whitespace checks passed on the integrated production branch.
- Historical replay: 66 default cards and 354 technical matches across 2025 Weeks 2, 5, 8, 11, 14, and 18; zero duplicate default player-week cards, zero wrong-week cards, zero share-reconciliation failures, and every replay week remained within the 8–15 default-card range.
- Live replay checks: Week 2 displayed 12 cards (3 gained, 3 lost, 3 overstated, 3 strong-opportunity/weak-production); Weeks 8 and 18 each displayed 11 cards (3, 3, 2, 3). All counts matched the committed replay artifacts.
- Live evidence links: Player, Team, and Game links passed for gained, lost, and overstated cards; season/week state remained visible; browser Back returned to the correct Home week; invalid player, team, and game values failed safely.
- Mobile QA: 390×844 passed with 390px client and scroll widths, the first complete card ending within the initial viewport, readable count/baseline evidence, operable links, four icon-plus-text category headings, 112px bottom safe padding, and zero console errors.
- Desktop QA: 1440×900 passed with no horizontal overflow, the intended two-column category layout, identical card data, readable expanded evidence, unchanged navigation, and zero console errors.
- Route regression: Home, Teams, Players, Games, Reports, and Explorer loaded without an exception; Research Admin remained absent from public navigation.
- Known Medium limitations retained: traded-player selector team labeling and the previously documented Games omissions for score, inside-five, and one-play production displays.
- Known Low limitation retained: sparse chart states can emit Vega infinite-extent warnings; no live console errors were observed on Home.
- Project transition: Phase B2 — Live Weekly Role Report Review is active. Production deployment during Phase B2 is not automatically authorized.

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
