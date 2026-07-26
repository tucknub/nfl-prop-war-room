# Phase 4B Python Exporter and Parity Bridge

Date: 2026-07-26

Branch: `propwar-nextjs-public-v1`

Authorization: newest PR #9 comment, “Phase 4B normative decisions — resume
authorization”

Starting head: `215ac8773e82e7c1780fafdcedbb7be4fe151b1d`

Scope status: **implemented and verified; not merged or deployed**

## Outcome

Phase 4B now provides a deterministic Python-to-Next.js export bridge without
changing the role methodology, Streamlit production, the production branch,
or the domain.

It includes:

- all three publication states;
- a truthful active 2026 `no_published_week` registry;
- a temporary completed-2025 historical parity registry;
- deterministic serialization, exact hashes, and content-addressed sources;
- Python and TypeScript validation;
- exact report and Home parity tests;
- team-neutral player identities and per-row `evidenceTeam`;
- the complete 32-team crosswalk including ATL;
- atomic staging, promotion, rollback, failure recovery, and cleanup;
- isolated fixture, active-export, and historical-export frontend modes;
- CI and committed review screenshots.

## Implementation map

| Responsibility | Location |
|---|---|
| Exporter, validation, parity model, atomic operations | `src/export/depthsnap_exporter.py` |
| CLI | `scripts/export_depthsnap.py` |
| Python verification | `tests/test_depthsnap_exporter.py` |
| Supplied blocked-state fixture | `tests/fixtures/depthsnap_role_status_blocked_2026.json` |
| Public Zod schemas | `apps/web/src/lib/data-contract.ts` |
| Registry hashes, counts, refs, parity, and isolation | `apps/web/src/lib/data-registry-core.ts` |
| Export-mode data-root selection | `apps/web/src/lib/data-loader.ts` |
| Contract and identity tests | `apps/web/tests/data-contract.spec.ts` |
| Active export browser suite | `apps/web/tests/export-active.spec.ts` |
| Historical export browser suite | `apps/web/tests/export-historical.spec.ts` |
| Active registry | `apps/web/public/data/depthsnap/export` |
| Temporary historical registry | `apps/web/public/data/depthsnap/export-historical-2025` |
| Private context preservation inventory | `outputs/role_research/depthsnap_bridge/opportunity_context_preservation_2025.json` |

## Registry results

| Registry | State | Bundles | Teams | Players | Through week | Source version |
|---|---:|---:|---:|---:|---:|---|
| Active 2026 | `no_published_week` | 9 | 0 | 0 | none | `sha256:8fd33bec1f63a940cb3f9bb6134d7edb326e748b7c1196a9b09c07e099a2cb74` |
| Historical 2025 | `published` | 586 | 32 | 545 | 18 | `sha256:24e5ed061aa0aeffb68abd0181903c452e24dbca8805f065faaf17deca7181ac` |

Historical manifest family counts are nine singleton bundles, 32 team bundles,
and 545 player bundles.

`.gitattributes` pins all registry JSON plus the four JSON source-metadata
artifacts to LF. Those source metadata files were normalized without semantic
changes before the final build, so the content-addressed versions above are
stable on Windows and Linux checkouts.

Report row counts:

| Report | Last 4 | Last 8 | Last 2 | Season |
|---|---:|---:|---:|---:|
| Backfield Control | 166 | 183 | 137 | 234 |
| Target Hierarchy | 161 | 204 | 76 | 267 |
| Role Movement | 306 | 361 | 199 | 0 |

The empty Season Role Movement view is exact Python parity: that comparison
does not have a prior matching season window and is not synthesized.

The historical Home bundle contains one lead plus 11 feed findings. Each of
the three Home leaderboards contains the first three rows from the
corresponding Python-default report view.

## Exact parity and identity results

Python tests compare the public rows against fresh calls to the existing
`league_window_summary` source path for all three report families and all four
views. The comparison key includes stable player ID, evidence team, and role
family, and checks:

- membership and order;
- authoritative rank;
- current numerator, denominator, and share;
- previous numerator, denominator, and share;
- percentage-point movement;
- participation quality;
- supporting-context status.

Home tests compare the weekly-report builder’s membership and order and verify
Team Snapshot and leaderboard composition.

Identity results:

- 545 strict team-neutral player identities;
- 32 canonical teams;
- ATL present and loadable;
- 26 players with cross-team historical evidence;
- 127 weekly evidence rows whose `evidenceTeam` differs from `currentTeam`;
- 7,338 `complete`, 48 `suspected_statistical`, and 4
  `suspected_corroborated` weekly rows;
- 7,390 weekly rows with available supporting context.

Confirmed partial rows remain excluded by existing methodology. Suspected rows
remain included with their exact participation label.

## Atomic protocol

For the active registry:

1. build into a unique sibling `.staging-*` directory;
2. run Python validation against staged bytes;
3. rename active to `export.rollback`;
4. rename staging to active;
5. if step 4 fails, restore rollback to active;
6. retain or explicitly clean rollback according to the CLI flag.

Paths are resolved and guarded before recursive cleanup. The exporter refuses
unsafe staging, rollback, or active targets. Tests inject a promotion failure,
prove that the prior source version is restored, then verify successful
promotion, explicit rollback, and cleanup.

## Commands

From the repository root:

```powershell
$generatedAt = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
python scripts/export_depthsnap.py build-active --generated-at $generatedAt --promote
python scripts/export_depthsnap.py build-historical --generated-at $generatedAt --output apps/web/public/data/depthsnap/export-historical-2025 --replace
python scripts/export_depthsnap.py preserve-context outputs/role_research/depthsnap_bridge/opportunity_context_preservation_2025.json

python scripts/export_depthsnap.py validate apps/web/public/data/depthsnap/export
python scripts/export_depthsnap.py validate apps/web/public/data/depthsnap/export-historical-2025
python -m pytest tests/test_depthsnap_exporter.py -q
```

From `apps/web`:

```powershell
npm ci
npm run generate:data
npm run validate:data
npm run measure:data
npm run typecheck
npm run build
npm run test:e2e
npm run test:e2e:export-active
npm run prepare:export-e2e
npm run test:e2e:export-historical
```

Operational commands:

```powershell
python scripts/export_depthsnap.py rollback
python scripts/export_depthsnap.py cleanup
python scripts/export_depthsnap.py cleanup --remove-rollback
python scripts/export_depthsnap.py build-from-status tests/fixtures/depthsnap_role_status_blocked_2026.json --output <isolated-output> --replace
```

## Fixture/export isolation

Fixture generation writes only the three fixture directories. It does not
write either export registry.

Active export browser verification reads only the committed active
`public/data/depthsnap/export`. Historical verification first copies the
temporary registry to
`apps/web/artifacts/export-e2e-data/depthsnap/export`, then starts a server with
`DEPTHSNAP_DATA_MODE=export` and that independent `DEPTHSNAP_DATA_ROOT`.

Both suites assert that no fixture notice or synthetic-record copy appears.
The loader does not use the fixture publication query variants in export mode.

## Opportunity Context preservation

The private preservation inventory retains the dimensions documented in
`OPPORTUNITY_CONTEXT_SOURCE_MAP.md` and hashes the exact supporting artifacts.
`yardline_100`, `down`, `ydstogo`, and `offense_snaps` remain source-available
but private. No new Opportunity Context field is exposed in V1 public JSON.

## Review screenshots

See `reviews/phase4b-export/README.md` for the active and historical desktop and
mobile evidence set. The export-mode Playwright suites regenerate these files.
CI also uploads fixture and export Playwright reports, traces, and screenshots.

## Known limitations

- The active registry intentionally contains no 2026 evidence until a fully
  completed week clears the existing gates.
- The historical 2025 registry is parity evidence only; it is not selected
  automatically and must not be deployed as current data.
- Historical `generatedAt` records exporter time, not a claimed 2025 source
  event time.
- Formula version and pipeline run ID remain absent when the exact source state
  does not supply them.
- Team offensive-snap denominators, goal-to-go, transaction timing, coaching
  chronology, play-caller chronology, and quarterback-regime chronology remain
  unavailable as authoritative metadata.
- Opportunity Context raw dimensions remain private in V1.
- The web dependency audit retains the separately documented Next.js
  development dependency findings in `NPM_AUDIT.md`; Phase 4B does not force a
  semver-major dependency change.
- No merge, deployment, production-branch change, Streamlit change, Python
  methodology change, or domain change is part of this work.
