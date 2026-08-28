# PropWar Live Proving Plan

PropWar is now in **private-beta proving mode**.

The goal is no longer to add features. The goal is to use the four core workspaces during real 2026 NFL weeks and decide whether they reliably produce useful decisions.

## Product under test

Only these four owner workspaces define the core product:

1. **Today** — What matters right now?
2. **Players** — What changed with this player?
3. **Markets** — What is unusual or potentially mispriced?
4. **Fantasy** — What should I do with my teams?

Everything under More is supporting evidence, advanced research, or a specialized owner tool.

## Feature freeze

Until the proving criteria below are satisfied, do not prioritize:

- new scanners
- new standalone dashboards
- new model families
- AI chat
- Yahoo expansion
- ESPN integration
- additional specialty league tools
- generic research boards

Allowed work:

- production bugs
- speed
- data freshness
- false-positive fixes
- confusing copy/hierarchy
- broken links/routes
- evidence quality
- action-ranking calibration
- current-season role ingestion

## Before Week 1

Confirm:

- Home opens reliably in the deployed Streamlit environment.
- Players opens reliably and exact player identity links are safe.
- Markets opens and current configured-book coverage is understandable.
- Fantasy finds the expected Sleeper leagues and remembered username works.
- 2026 Current Role Operations remains fail-closed before a completed regular-season week.
- Current Role Operations runs on Python 3.14 and has Tue/Wed/Thu retry cadence.

## Weekly proving loop

### After games complete

Current Role Operations should:

1. detect the latest complete consecutive regular-season week
2. load current nflverse sources
3. pass identity/snap/source validation
4. publish only when all gates pass
5. leave prior published data untouched when gates fail

Record any:

- missing source
- delayed snap counts
- player identity mismatch
- team mismatch
- partial-game issue
- false role-change classification

### Today

For every surfaced action, ask:

- Was the action genuinely worth my attention?
- Was the WHY specific enough?
- Was freshness obvious?
- Did the deep link open the right evidence?
- Did a lower-value item displace something more important?
- Was any missing source handled clearly rather than guessed?

Do not optimize for number of actions. Empty is acceptable.

### Players

For players actually researched that week, ask:

- Did the page answer WHAT CHANGED quickly?
- Was current team/player identity correct?
- Did Role Change Detector agree with the underlying game logs?
- When current-season role + market data exist, was the comparison season-safe?
- Was detailed role evidence easy to access without overwhelming the first screen?

### Markets

For surfaced BET/WATCH/CHECK/SHOP opportunities, record:

- current price
- opening/previous price
- what happened afterward
- whether the same wager remained available
- whether the signal was a good-side or bad-side anomaly
- whether settlement/market-definition differences explained the gap
- whether the action label was useful

False positives matter more than raw alert count.

### Fantasy

During normal weekly use, record whether PropWar helped with:

- lineup decisions
- waivers
- FAAB
- matchup review
- trade/manager fit
- cross-league ownership/exposure

For each recommendation, ask:

- Did it save time?
- Did it surface something I would have missed?
- Was it obvious which league/action mattered?
- Did market-backed evidence improve the decision?
- Did the grouped Team / Start-Sit / Waivers / Matchup / Trades / League / Across leagues structure feel natural?

## Issue classification

Every issue found during live use should be classified as one of:

- **P0 — Broken:** app/page cannot be used or produces unsafe/wrong identity/data.
- **P1 — Wrong decision:** surfaced action is materially misleading or incorrectly ranked.
- **P2 — Friction:** correct information is slow, buried, duplicated, or confusing.
- **P3 — Nice to have:** improvement that does not block the core decision.

Fix P0/P1 first. Do not let P3 ideas restart feature sprawl.

## Private-beta exit criteria

PropWar can move toward a Cloudflare product shell only after:

- several real 2026 NFL weeks of use
- no recurring production-breaking core-page errors
- 2026 role data publishes reliably
- Today repeatedly surfaces a small useful action set
- Players repeatedly answers WHAT CHANGED cleanly
- Markets false-positive behavior is understood and acceptable
- Fantasy is fast enough for normal weekly use
- core internal routes remain healthy
- major issues are P2/P3 rather than P0/P1

## Cloudflare trigger

Do not migrate just because Cloudflare can host it.

Migrate when the product shape is stable enough that we are rebuilding a known experience:

- Cloudflare Workers + Static Assets for the product shell
- branded custom domain
- Cloudflare storage/cache where useful
- preserve Python analytics engines behind an API/container boundary initially
- migrate incrementally, not as a rewrite

Until then, Streamlit remains the proving environment.
