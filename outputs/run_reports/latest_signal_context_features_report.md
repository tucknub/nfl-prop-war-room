# Signal Context Features Report

Run timestamp: `2026-07-07T23:25:52+00:00`

Target season/week: `2025 Week 1`

Allowed history window: `2023-2024` and no target-week player results.

## Source Inspection

- `data/raw/weekly.csv`: `37624` pre-target rows used; columns used: `player_id, player_name, team, opponent_team, position, season, week, targets, receptions, receiving_yards, carries, rushing_yards, attempts, completions, passing_yards`
- `data/raw/schedules.csv`: `855` rows inspected; columns used: `game_id, season, week, home_team, away_team, spread_line, total_line`
- `outputs/signal_boards/player_week_signal_master.csv`: context keys and player rows used as the safe join base.

## Outputs

- Recent form rows: `762`
- Game environment rows: `762`
- Opponent defense fit rows: `762`
- Combined context rows: `762`

## Notes

Recent form uses only pre-target weekly player stats. Game environment uses `schedules.csv` spread and total columns when present. Opponent defense fit uses historical allowed stats by opponent/position with shrinkage toward league average via `min(1.0, sample_games / 10)`.

Weather, route share, first-read share, shadow coverage, and CB matchup data remain unavailable because they are not sourced by current project files.
