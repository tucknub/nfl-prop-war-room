# Free Bet Tracker

Canonical installed dashboard: `daily.html`

## Structure

- `daily.html` — self-updating installed wrapper used on iPhone and desktop.
- `app.html` — core tracker UI and countdown/rendering logic.
- `daily-polish.css` / `daily-polish.js` — branded responsive styling and Mark Used interaction.
- `sheet-source.js` — Sheet-first live data loader. When the bridge is configured, this is the authoritative promo source.
- `bridge-config.json` — contains the deployed Apps Script web-app URL.
- `Code.gs` — Google Sheets bridge for full promo reads and Used? writes.
- `promos.json` — backup snapshot only. It is not the primary live source once the Sheet bridge is configured.
- `manifest.webmanifest` / `app-icon-v3.svg` — installable web-app metadata and current icon.

## Source of truth

The Google Sheet `Free Bet Expiry Tracker`, tab `Free Bets`, is the authoritative tracker database. It stores sportsbook, value, expiration, Used?, promo name, notes, stable ID, promo kind, and whether the expiration is estimated.

When `bridge-config.json` contains a deployed Apps Script URL, the installed app loads the Sheet first and refreshes it every minute. Mark Used writes the matching stable ID back to the Sheet, allowing phone and desktop to agree on active promos.

`promos.json` remains a complete emergency snapshot so the tracker can still render when the Sheet bridge is temporarily unavailable. It should not overwrite newer Sheet data during normal operation.

## Time behavior

All expiration timestamps are rendered in `America/Indiana/Indianapolis` / Eastern Time. Every active promo displays an exact expiration date/time plus a live countdown. Estimated expiration times are explicitly labeled.

## Active-view behavior

Used and expired promos are hidden from the active wallet. The countdown UI updates every second. The Sheet source refreshes every minute and again when the app regains focus. A local cached snapshot is retained only as a resilience fallback.
