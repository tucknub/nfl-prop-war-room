# DepthSnap V1 release readiness

Date: 2026-07-26

Branch: `propwar-nextjs-public-v1`

Starting head: `ea8e3d3b13a52aab961b08b34dd36518cf42aa12`

Decision: **GO for a truthful 2026 preseason launch after a deployment
provider and canonical public origin are authorized.**

This is a release-hardening gate. It does not change Python methodology,
formulas, thresholds, membership, ordering, or publication gates. It does not
merge, deploy, connect a domain, replace Streamlit, or change the production
branch.

## Production package

From `apps/web`:

```powershell
$env:DEPTHSNAP_DATA_MODE = "export"
$env:DEPTHSNAP_PUBLIC_ORIGIN = "https://<authorized-public-origin>"
npm run package:production
```

For provider-neutral local staging, `DEPTHSNAP_PUBLIC_ORIGIN` may be omitted;
the package command uses `http://127.0.0.1:3400` only as the smoke-test origin.
The command:

1. rejects any supplied data mode other than `export`;
2. validates the committed active registry and rejects a pre-2026 registry;
3. builds a Next.js standalone production server;
4. copies only the active export and required public images;
5. removes source, test, report, trace, historical, fixture, and build-only
   dependency content;
6. scrubs generated local build paths;
7. audits the staged bytes;
8. starts the staged server in production mode and runs smoke tests;
9. audits the package again.

The output is `apps/web/artifacts/production-package`. It is ignored by Git
and must be treated as a generated artifact from an exact commit.

### Audited inventory

Final local audit:

| Item | Result |
|---|---:|
| Publication state | `no_published_week` |
| Season / through week | `2026` / `null` |
| Active registry entries | 9 |
| Active data files including manifest | 10 |
| Package files | 1,298 |
| Package bytes | 23,436,379 |
| Package SHA-256 | `21d8e00261ff335e8767701939379051c9b7631df2df78be6315d6f81d867227` |
| Active source version | `sha256:8fd33bec1f63a940cb3f9bb6134d7edb326e748b7c1196a9b09c07e099a2cb74` |

Top-level runtime inventory is the standalone `.next` output, traced
production `node_modules`, a minimal runtime `package.json`, `server.js`, and
`public`. `public/data/depthsnap` contains exactly one directory: `export`.

### Excluded development and test inventory

These remain useful in the repository or ignored test artifacts but are not
in the production package:

| Excluded content | Development location / count |
|---|---|
| Published synthetic fixture registry | `fixture`, 45 files |
| No-week synthetic fixture registry | `fixture-no-published-week`, 45 files |
| Unavailable synthetic fixture registry | `fixture-unavailable`, 45 files |
| Temporary completed-2025 parity registry | `export-historical-2025`, 587 files / 586 entries |
| Isolated historical and state-test roots | `apps/web/artifacts`, generated |
| Playwright reports, traces, results, screenshots | `apps/web/artifacts`, generated |
| Committed review screenshots | `docs/depthsnap/reviews`, repository evidence only |
| Opportunity Context preservation inventory | `outputs/role_research/depthsnap_bridge`, private source evidence |
| Python source and tests | repository only; no `.py`, `.pyc`, or `__pycache__` in package |
| Staging and rollback directories | excluded and rejected by audit |
| PostCSS and Sharp | build/image dependencies excluded from staged runtime |

The audit fails on forbidden directory names, historical/private content
tokens, Python artifacts, source/test roots, known secret patterns, and real
or JSON-escaped absolute local build paths.

## Current-season publication workflow

The existing Python workflow remains authoritative. The DepthSnap bridge acts
only after that workflow writes its operational status.

| Python operational state | DepthSnap action |
|---|---|
| `PUBLISHED` and independent validation passes | Build populated current-season export, validate it, and atomically promote it |
| `PRESEASON` | Promote truthful `no_published_week` |
| `WAITING_FOR_COMPLETED_WEEK` | Promote truthful `no_published_week` |
| `BLOCKED` with a same-season prior valid registry | Retain the prior registry |
| `BLOCKED` without a same-season prior valid registry | Build `unavailable` only from supplied blocked-state metadata |
| `VALIDATED_NOT_PUBLISHED` | Do not promote |
| Identity, schema, hash, parity, loader, source, or validation failure | Fail closed; retain the previous valid registry |

A 2025 registry does not qualify as a prior current-season registry and is
never substituted for 2026 evidence.

The `Current Role Operations` workflow keeps the established Tuesday and
Thursday schedule at 13:30 UTC from September through January. A manual run
accepts `season`, optional `through_week`, and `dry_run`. January resolves to
the prior NFL season. Scheduled/manual runs may refresh authoritative external
sources; ordinary pull-request CI runs only committed no-network contract
tests and the release rehearsal.

For a dry run, the Python pipeline receives `--no-publish`, produces
`VALIDATED_NOT_PUBLISHED`, and the bridge does not promote or commit. No
workflow deploys the web application.

## Production environment contract

| Variable / runtime | Contract |
|---|---|
| `DEPTHSNAP_DATA_MODE` | Must be `export`; missing, `fixture`, or any other value fails closed in production |
| `DEPTHSNAP_DATA_ROOT` | Required in production; must resolve to `public/data/depthsnap` from the package root |
| `DEPTHSNAP_PUBLIC_ORIGIN` | Required for a real deployment build/runtime; canonical HTTPS origin used by social metadata |
| `DEPTHSNAP_ENABLE_HSTS` | Build-time opt-in; set to `1` only after the provider serves this application exclusively over HTTPS |
| `HOSTNAME`, `PORT` | Provider/runtime bindings; local smoke uses `127.0.0.1:3400` |
| Node | 22.x, npm 10 or later |
| Python operations | 3.12 |

`DEPTHSNAP_ALLOW_TEST_DATA_MODE` and `DEPTHSNAP_ALLOW_TEST_DATA_ROOT` exist
only for isolated test servers. They are not approved production variables.

Build and start:

```powershell
npm run package:production
Set-Location artifacts/production-package
$env:DEPTHSNAP_DATA_MODE = "export"
$env:DEPTHSNAP_DATA_ROOT = "public/data/depthsnap"
node server.js
```

Missing or invalid production data returns the closed contract-failure
experience. Public responses use sanitized failure detail; internal paths,
stack traces, secrets, and source filenames are not rendered.

## Cache and freshness decision

- Next-generated hashed JavaScript and CSS files use framework-managed
  immutable caching.
- Registry filenames are stable even though the manifest carries their
  hashes. Manifest, status, and bundle responses therefore use
  `max-age=0, must-revalidate`; ETags may satisfy a revalidation.
- No browser or CDN may assign a long freshness lifetime to
  `public/data/depthsnap/export`.
- The server caches one fully validated registry for its process lifetime.
  Atomic promotion alone does not mutate a live process cache.
- Every promoted registry must be followed by a rebuild/redeploy from the new
  generated-data commit, or by a controlled process restart when the provider
  uses a mounted registry.
- Data Status is rendered from the same loaded registry instance as all other
  routes, including its exact `sourceVersion`.
- There is no fixture or historical cache fallback.

## Rollback rehearsal

`python scripts/rehearse_depthsnap_release.py` automates:

1. valid active registry;
2. invalid replacement attempt;
3. prior registry retained;
4. valid replacement;
5. explicit rollback;
6. successful later promotion;
7. staging cleanup;
8. rollback cleanup.

Result: all eight checkpoints passed. The observer saw only complete valid
source versions, never a partial registry. One staging directory and one
rollback directory were removed by guarded cleanup.

## Security headers and CSP decision

Every application response has:

- `X-Content-Type-Options: nosniff`;
- `X-Frame-Options: DENY`;
- `Referrer-Policy: strict-origin-when-cross-origin`;
- a deny-by-default Permissions Policy for camera, microphone, geolocation,
  payment, USB, and browsing topics;
- `Cross-Origin-Opener-Policy: same-origin`.

HSTS is intentionally absent from the provider-neutral package and is enabled
only with `DEPTHSNAP_ENABLE_HSTS=1` for an authorized HTTPS-only deployment.

A global Content Security Policy is intentionally not included in V1. The
production application uses Next-managed inline bootstrap scripts; an
untested policy would break hydration or require unsafe claims. Production
smoke tests explicitly confirm the current no-CSP decision. Add CSP only after
a provider-specific report-only observation period and an automated
navigation/hydration regression pass.

## Dependency and secret review

Commands:

```powershell
npm audit
npm audit --omit=dev
python -m pip check
npm run audit:production
```

Both npm audits report 3 high, 0 critical findings: Next.js aggregates
advisories from its pinned PostCSS 8.4.31 and optional Sharp 0.34.5
dependencies. npm's offered fix is an invalid downgrade from Next.js 16.2.11
to 9.3.3 and was not applied. Next.js 16.2.12 still declared the same
transitive versions when reviewed.

Production impact is bounded: PostCSS processes repository-owned CSS at build
time, the application does not accept untrusted CSS or image input, Next image
optimization is disabled, and both PostCSS and Sharp are absent from the
audited staged runtime. This is an accepted build-environment risk pending a
compatible tested Next.js dependency update.

`pip check` reports no broken requirements. The repository has no configured
Python advisory-database scanner and `pip-audit` was not installed; Python is
not present in the deployed web package. Add a pinned Python lock and
`pip-audit` to operations maintenance rather than changing dependencies during
this release gate.

The production package path/secret scan passed.

## Verification results

| Verification | Result |
|---|---:|
| Complete Python repository suite | 160 passed, 1 non-blocking Streamlit serialization warning |
| Exporter/release focused suite | 19 passed |
| Release rollback rehearsal | passed |
| Python active registry | 9 entries, 2026 `no_published_week` |
| Python historical registry | 586 entries, 2025 Week 18 |
| Fixture regeneration | 44 bundles in each of 3 states; committed bytes unchanged |
| TypeScript registry validation | passed for all fixture, active, and historical roots |
| Registry load measurement | active 10 files / 12,287 bytes; historical 587 files / 10,273,390 bytes |
| Typecheck | passed |
| Next production build | passed |
| Fixture browser suite | 43 passed |
| Active 2026 browser suite | 2 passed |
| Historical 2025 browser suite | 3 passed |
| Staged production browser suite | 3 passed |
| Unavailable / contract-failure suite | 2 passed |
| Independent browser pass | desktop/mobile/deep links/search/metadata/status: passed after staging-origin correction |
| Production artifact audit | passed |
| `git diff --check` | passed |

The browser suites cover Home, reports overview and all three report families,
team/player indexes and dossiers, Search, Methodology, Data Status, direct deep
links, truthful no-week, unavailable, contract failure, desktop/mobile,
keyboard navigation, names and status announcements, overflow, and relevant
console/page errors.

## Review evidence

- [Production desktop Home](reviews/release-readiness/production-desktop-home.png)
- [Production mobile Home](reviews/release-readiness/production-mobile-home.png)
- [Production Data Status](reviews/release-readiness/production-desktop-data-status.png)
- [Unavailable state](reviews/release-readiness/production-desktop-unavailable.png)
- [Contract-failure state](reviews/release-readiness/production-desktop-contract-failure.png)
- [Phase 4B ATL and team-neutral parity evidence](reviews/phase4b-export/README.md)

## Launch checklist

- [x] Truthful active 2026 no-week registry validates.
- [x] Populated, no-week, and unavailable states validate.
- [x] Current workflow bridge follows every authorized state transition.
- [x] Historical 2025 evidence is isolated and cannot become current fallback.
- [x] Production package contains only the active export.
- [x] Runtime fails closed on missing mode, root, registry, or contract.
- [x] Atomic promotion, failed replacement, rollback, later promotion, and
  cleanup are rehearsed.
- [x] Desktop/mobile product and accessibility regression suites pass.
- [x] Metadata, icon, web manifest, and generated social preview are present.
- [x] Security headers and cache behavior are tested.
- [x] Dependency and production path/secret scans are documented.
- [x] PR CI contains all Python, fixture, active, historical, package, audit,
  smoke, and release-state verification without deployment.
- [ ] Authorize a deployment provider, canonical public origin, restart/redeploy
  mechanism, and HTTPS/HSTS setting.
- [ ] Run the exact production package from the authorized release commit.
- [ ] Perform provider-specific post-deploy smoke checks.

## First completed 2026 week checklist

- Confirm the week is consecutive from Week 1 and all games clear the existing
  completed-game gate.
- Confirm the Python attempt state is `PUBLISHED`.
- Run independent current-output validation.
- Run `publish_current_depthsnap.py` and confirm a populated 2026 registry.
- Validate manifest hashes, identities, ATL crosswalk, team-neutral players,
  `evidenceTeam`, report/Home parity, and all four view windows.
- Confirm the active source version differs from preseason and no historical
  source version appears.
- Run production package, artifact audit, and production smoke tests.
- Commit only validated generated current outputs and the active registry.
- Trigger the authorized rebuild/redeploy or controlled restart.
- Confirm public Data Status matches the promoted `sourceVersion` and through
  week.
- Retain the prior valid deployment/registry until post-deploy verification
  completes.

## Remaining provider-specific decision

One decision remains: select and authorize the deployment provider and its
canonical public origin, build environment, artifact handoff, HTTPS/HSTS
setting, and automatic rebuild/redeploy or controlled restart after an
operational registry commit.

That decision does not block code-level preseason readiness. It does block an
actual deployment, which was outside this gate and was not performed.
