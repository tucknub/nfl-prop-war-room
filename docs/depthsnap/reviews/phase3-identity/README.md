# DepthSnap Phase 3 identity review

Phase 3 implementation commit: `d6934c5eb2b8fd2badcc4b0d6e049f15a05734e6`

This review bundle covers the typed synthetic identity, dossier, chronology, and search experience. No production data or Python export is connected.

## Routes

- `/teams`
- `/teams/[team]`
- `/players`
- `/players/[playerId]`
- `/search`

Existing Feed and report routes remain in place. Their team and player evidence links now resolve to stable fixture identity routes.

## Fixture and contract architecture

- `TeamIdentity` and canonical player identities provide stable IDs, safe monograms, aliases, and hrefs.
- `TeamEvidenceBundle` combines supplied backfield, WR, TE, movement, player, freshness, and quality records.
- `PlayerEvidenceBundle` combines current evidence, report memberships, weekly chronology, team context, movements, and quality records.
- `WeeklyEvidencePoint` preserves exact numerator, denominator, share, opportunity label, quality, partial-game, and missing-week states.
- `SearchIdentity` supplies the local team/player index and aliases.
- Team, player, and search views normalize their shared evidence from the existing report fixtures. Cross-route browser assertions verify that exact evidence agrees with Feed and reports.

## Test results

- `npm install`: passed; dependencies were already current.
- `npm run typecheck`: passed.
- `npm run build`: passed; all Phase 3 routes compiled.
- `npm run test:e2e`: **28 passed** in 21.2 seconds.
- Phase 2 workflow gate: replacement run `30034940020` passed after the separate documented Playwright-container fix.
- npm audit remains documented separately in `docs/depthsnap/NPM_AUDIT.md`: 3 high-severity transitive findings, 0 critical. No unsafe forced dependency change was applied.

## Desktop screenshots — 1440 × 900

- [Teams directory](./phase3-desktop-teams.png)
- [Team dossier](./phase3-desktop-team-dossier.png)
- [Players directory](./phase3-desktop-players.png)
- [Player dossier](./phase3-desktop-player-dossier.png)
- [Search results](./phase3-desktop-search.png)
- [Player weekly timeline](./phase3-desktop-player-timeline.png)
- [Unknown team](./phase3-desktop-unknown-team.png)
- [Unknown player](./phase3-desktop-unknown-player.png)
- [Unavailable team](./phase3-desktop-unavailable-team.png)
- [Unavailable player](./phase3-desktop-unavailable-player.png)

## Mobile screenshots — 390 × 844

- [Teams directory](./phase3-mobile-teams.png)
- [Team dossier](./phase3-mobile-team-dossier.png)
- [Players directory](./phase3-mobile-players.png)
- [Player dossier](./phase3-mobile-player-dossier.png)
- [Search results](./phase3-mobile-search.png)
- [Open search interaction](./phase3-mobile-search-open.png)
- [Player weekly timeline](./phase3-mobile-player-timeline.png)
- [Unknown team](./phase3-mobile-unknown-team.png)
- [Unknown player](./phase3-mobile-unknown-player.png)

## Regression screenshots

- [Desktop Feed](./phase3-regression-desktop-feed.png)
- [Mobile Feed](./phase3-regression-mobile-feed.png)
- [Desktop Backfield Control](./phase3-regression-desktop-backfield.png)
- [Mobile Backfield Control](./phase3-regression-mobile-backfield.png)

## Visual review

- Preserved the approved near-black blue-green canvas, layered graphite surfaces, teal current values, restrained amber/coral movement cues, desktop top navigation, and fixed mobile bottom navigation.
- Team and player pages use identity-led dossier composition rather than report tables.
- Exact raw counts remain adjacent to every displayed share.
- Weekly bars supplement a semantic exact-value table; missing weeks remain visibly unavailable.
- Mobile screenshots show purpose-built hierarchy, movement, chronology, and search layouts with at least 112px bottom clearance and no horizontal overflow.
- Feed and Backfield captures show no unintended composition regression. Intentional changes are limited to stable team/player destinations.

## Known limitations

- All records are visibly labeled synthetic design fixtures.
- The Python export bridge is intentionally not connected.
- Methodology and Data Status remain future content destinations.
- Only players with supplied fixture chronology receive multi-week timelines; other fixture players show their supplied current point or an explicit no-chronology state.
- Safe monograms and neutral initials are used instead of unsupported player photography or branded team marks.
- Search is a local typed fixture index; it does not query reports, news, or external services.
