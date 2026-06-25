# Google Sheets Import Pack

This pack is a local CSV import bundle. It does not upload anything to Google Sheets and does not use Google API credentials.

## Current Readiness

- Final Live Readiness: `NO-GO`
- Blocked gates: `Historical test mode, Roster Gate, Role Gate, Injury Gate, Market Odds Gate`
- Current model mode: `historical_test` unless changed in `config.yaml`.

The board is not live-betting ready until `Live Readiness = GO`.

## Import Map

| File | Google Sheet tab | Select cell | Import method |
| --- | --- | --- | --- |
| `schedule_gate_import.csv` | Schedule Gate | A13 | File -> Import -> Replace data at selected cell |
| `roster_gate_import_template.csv` | Roster Gate | A13 | File -> Import -> Replace data at selected cell |
| `role_gate_import_template.csv` | Role Gate | A13 | File -> Import -> Replace data at selected cell |
| `injury_gate_import_template.csv` | Injury Gate | A13 | File -> Import -> Replace data at selected cell |
| `market_odds_gate_import_template.csv` | Market Odds Gate | A14 | File -> Import -> Replace data at selected cell |
| `live_readiness_export.csv` | Live Readiness | optional review import / do not overwrite formulas unless instructed | Review only, or import to a scratch area unless intentionally refreshing formulas |
| `forward_projection_blockers.csv` | Forward Readiness or separate blockers review tab | A1 | File -> Import -> Replace data at selected cell |
| `google_sheets_receptions_historical_test.csv` | Receptions Model Test | A1 | File -> Import -> Replace data at selected cell |
| `receptions_line_ladder.csv` | Line Ladder | A1 | replace data at selected cell |
| `receptions_line_ladder_top_by_line.csv` | Line Ladder Top | A1 | replace data at selected cell |

## How To Import

1. Open the Google Sheet control room.
2. Go to the target tab listed in `import_manifest.csv`.
3. Select the listed start cell before using File -> Import.
4. Choose the CSV from this import pack.
5. For gate/template/model CSVs, use Replace data at selected cell.
6. Do not overwrite formula or summary sections unless intentionally refreshing those formulas.

## Tabs That Need Extra Care

- `Live Readiness`: use as review data or import into a scratch area unless you intentionally want to refresh formula-backed summary sections.
- `Forward Readiness`: safe as a blockers review import, but confirm the destination area before replacing data.
- `Receptions Model Test`: historical-test board only; this is not a live betting board.
- `Line Ladder`: optional research import for `receptions_line_ladder.csv` at `Line Ladder!A1`. It is an odds-free probability ladder, not a betting edge.
- `Line Ladder Top`: optional research import for `receptions_line_ladder_top_by_line.csv` at `Line Ladder Top!A1`. It is a top-by-line review table, not a betting edge.

## Historical Test vs Forward Projection

`historical_test` validates the model on historical windows and labels rows `HISTORICAL TEST ONLY`.

`forward_projection` is for live/future use. It must not silently fall back to historical mode. It requires schedule, roster, role, injury, and current-team gates to be ready before projection use. Betting-edge use also requires market odds.

## Why Final Live Readiness Is NO-GO

The current run is blocked because the model is in historical-test mode and live gate data is incomplete. Roster, role, injury, and market odds templates still need validated data before live use.

## Required Before Live Use

- Switch to `projection_mode: forward_projection` only after gates are ready.
- Confirm schedule for the target season/week.
- Verify current roster/team for every candidate player.
- Fill role confidence and starter/route context.
- Fill injury/practice/game-status data.
- Add market odds before treating any output as a betting-edge board.

## Optional Line Ladder Imports

`receptions_line_ladder.csv` imports to `Line Ladder!A1`. `receptions_line_ladder_top_by_line.csv` imports to `Line Ladder Top!A1`. These are optional research tabs, not betting edges. Odds are still required for actual edge, and historical-test output must remain labeled `HISTORICAL TEST ONLY`.
