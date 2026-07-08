# Historical Signal Backtest Report

Run timestamp: `2026-07-08T18:53:43+00:00`

Audit type: `RESEARCH ONLY / HISTORICAL SIGNAL BACKTEST`

## Source Inspection

- `data/raw/weekly.csv`: `57045` rows; columns used include player/team/week identifiers and actual receptions, receiving yards, carries, rushing yards, attempts, completions, and passing yards.
- `data/raw/schedules.csv`: `855` rows; columns used when present include game_id, home_team, away_team, spread_line, and total_line.

## Coverage

- Backtest rows: `15191`
- Seasons tested: `2023, 2024`
- Weeks tested: `1-22`
- Market families: `passing, receiving, rushing`

## Outputs

- Tier lift rows: `15`
- Score bucket rows: `15`
- Component audit rows: `24`
- Market-family audit rows: `3`

## Limitations

Pregame scores use shifted historical player rows and do not use target-week actuals. This is a proxy signal backtest, not a sportsbook profitability test, and it does not change production weights.
