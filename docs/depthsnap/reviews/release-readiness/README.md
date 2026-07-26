# DepthSnap release-readiness review evidence

Generated in production export mode from the provider-neutral standalone
package.

- `production-desktop-home.png`: truthful 2026 preseason Home.
- `production-mobile-home.png`: 390 x 844 responsive Home and mobile
  navigation.
- `production-desktop-data-status.png`: the exact active
  `no_published_week` registry and source version loaded by the server.
- `production-desktop-unavailable.png`: supplied 2026 blocked metadata with no
  prior same-season registry.
- `production-desktop-contract-failure.png`: sanitized hash mismatch with no
  fixture or historical fallback.

Regenerate from `apps/web`:

```powershell
npm run package:production
npm run prepare:release-states
npm run test:e2e:release-states
```

These files are review evidence only. The production artifact audit rejects
screenshots, Playwright reports, traces, and test artifacts from the staged
runtime.
