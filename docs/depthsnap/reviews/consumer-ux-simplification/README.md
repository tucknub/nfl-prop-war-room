# Consumer UX Simplification Review Evidence

## Information hierarchy

The review build uses three levels of disclosure:

1. **Answer:** a deterministic football conclusion or current role.
2. **Evidence:** exact percentage, numerator/denominator, period, player/team, and context.
3. **Audit:** source version, schema, quality codes, exact weekly table, and other operational detail behind an explicit collapsed control.

This keeps the product immediately interpretable without weakening exact evidence or the fail-closed data contract.

## Before/after terminology

| Before | Consumer interface |
| --- | --- |
| Validated export | Data verified |
| Published export | Updated through Week 18 |
| Export status | Data status |
| Current supplied evidence | Current role |
| Latest supplied movement | Recent change |
| Supplied hierarchy | Team hierarchy |
| Supplied periods | Compared periods |
| Evidence team | Team |
| Find exact evidence | Search DepthSnap |
| Search supplied identities | Search players and teams |
| No default-report evidence row | No recent qualifying report |
| Plain-language methodology | How this is calculated |
| Report Leaderboard | Quick leaders |
| Future player/team page | View player/team dossier |

Methodology, Data Status, tests, documentation, internal field names, and collapsed technical details retain technical terminology where it is genuinely needed.

## Desktop screenshots — 1440 × 900 at 100% zoom

- [Home](desktop-home.png)
- [Backfield Control](desktop-backfield-control.png)
- [Target Hierarchy](desktop-target-hierarchy.png)
- [Role Movement — gainers](desktop-role-movement-gainers.png)
- [Role Movement — declines](desktop-role-movement-declines.png)
- [Player dossier top](desktop-player-dossier-top.png)
- [Player weekly trend](desktop-player-weekly-trend.png)
- [Team dossier](desktop-team-dossier.png)
- [Search](desktop-search.png)
- [Evidence drawer](desktop-evidence-drawer.png)
- [Evidence drawer — technical details expanded](desktop-evidence-drawer-technical.png)

## Mobile screenshots — 390 × 844 at 100% zoom

- [Home](mobile-home.png)
- [Role Movement](mobile-role-movement.png)
- [Player weekly trend](mobile-player-weekly-trend.png)
- [Search](mobile-search.png)

Additional automated overflow checks run at desktop widths 1280 and 1024 and mobile width 430.

## Evidence source

The screenshots use the temporary completed-2025 historical parity registry in export mode:

- season: 2025;
- through week: 18;
- publication state: published;
- declared bundles: 586;
- fixture fallback: absent.

The historical registry remains outside the production public artifact. It is never substituted for the active truthful 2026 `no_published_week` registry.

## Acceptance summary

- All normal pages avoid banned internal wording.
- Report controls preserve exact current share, movement, and Report order.
- Every visible percentage retains its matching raw counts.
- Green/red/amber/gray meaning includes direction, label, and exact pp where applicable.
- Player weeks are unique within a selected metric and expose an accessible text equivalent.
- Exact weekly evidence and source/quality fields are collapsed by default.
- The evidence drawer traps and restores focus.
- Desktop and mobile review widths have no horizontal overflow.
- Fixture, historical, active-export, release-state, and production-package suites remain isolated.
