# Phase 4B export-mode review

These screenshots are produced by the active and historical export-mode
Playwright suites. Neither suite reads the fixture registry.

## Active 2026

- `active-2026-desktop-home.png`: truthful no-published-week Home state.
- `active-2026-desktop-data-status.png`: export mode, nine bundles, no supplied
  week.
- `active-2026-mobile-home.png`: mobile no-published-week state.

## Temporary completed-2025 parity

- `historical-2025-desktop-home.png`: Python weekly-report Home composition.
- `historical-2025-desktop-atl.png`: completed ATL crosswalk and team dossier.
- `historical-2025-desktop-team-neutral-player.png`: Adam Thielen with PIT
  current-team presentation and MIN/PIT evidence-team chronology.
- `historical-2025-mobile-home.png`: populated export-mode mobile composition.

Regenerate from `apps/web`:

```powershell
npm run build
npm run test:e2e:export-active
npm run prepare:export-e2e
npm run test:e2e:export-historical
```
