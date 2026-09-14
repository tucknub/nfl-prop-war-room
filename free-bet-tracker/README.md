# Free Bet Tracker

Canonical mobile dashboard: `index.html`

## Structure

- `index.html` — production dashboard UI. Update this file in place; do not create numbered dashboard copies.
- `promos.json` — live promo/free-bet data consumed by the dashboard.
- `manifest.webmanifest` — installable web-app metadata.
- `app-icon.svg` — tracker favicon/PWA icon.
- `Code.gs` — legacy Google Sheets bridge retained for reference; the current dashboard is read-only and is maintained from `promos.json` plus the Google Sheet.

## Time behavior

All expiration timestamps are stored as offset-aware ISO timestamps and rendered in `America/Indiana/Indianapolis` / Eastern Time. Every active promo displays both an exact expiration date/time and a live countdown. Estimated expiration times are explicitly labeled.

## Data behavior

Expired promos disappear from the active view automatically. The UI refreshes `promos.json` every minute and updates countdowns every second. The last successfully loaded data is cached locally as a fallback if the live data feed cannot refresh.