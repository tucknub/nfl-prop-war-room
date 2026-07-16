# Data Status Audit

## Verified availability

- **Latest completed boundary:** `Data through 2025 Week 18`.
- **Latest-week game coverage:** 16 unique games and 432 public player-role rows.
- **Completion reconciliation:** 16 of 16 games have `game_partition_complete = true` across every canonical row.
- **Displayed status:** The page header uses the validated boundary above.

## Unavailable trusted metadata

- **Refresh timestamp:** unavailable. No committed public extract contains an ingestion or dataset refresh timestamp.
- Injury-report timestamps describe postgame evidence timing, not the data refresh time, and are not reused.
- Filesystem modification times are local transport metadata and are not displayed.

## Interpretation

`game_partition_complete` supports a completed-game/partition boundary. It does not support a claim about when the repository was refreshed, so no such timestamp is shown.
