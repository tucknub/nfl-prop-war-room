# Signal Data Sources

This inventory documents what NFL Prop War Room can currently source for signal boards and what remains unavailable.

V1 signal boards must use `outputs/signal_boards/player_week_signal_master.csv` as the source of truth. Future dashboard heatmaps should filter or sort that master table rather than recomputing signals independently.

## Available Now

- Projection signals from existing historical-test market outputs.
- Basic player context such as player name, team, position, season, and week.
- Some support usage projection fields such as target share, catch rate, estimated routes, carries, team pass attempts, completion rate, and yards-per-attempt where those columns already exist.
- Recent form features from `data/raw/weekly.csv`, using only pre-target player weekly rows.
- Game environment features from `data/raw/schedules.csv` where `spread_line` and `total_line` exist.
- Opponent defense fit from historical `data/raw/weekly.csv` allowed stats by defense and position, with shrinkage toward league average.
- Data quality flags, confidence buckets, and usage status from market outputs.
- Gate-level readiness statuses from roster, role, injury, odds, identity, and intake reports.

## Not Available Yet

The current project does not have true route share, snap share, first-read share, red-zone targets, goal-line carries, shadow coverage, man/zone matchup, verified weather, or practice-report progression as sourced production metrics. These must be marked `NOT_AVAILABLE`, `NEEDS SOURCE`, or `PLANNED_SOURCE` until real data exists.

## Signal Context Enrichment V1

`src.export.export_signal_context_features` writes:

- `outputs/signal_boards/recent_form_features.csv`
- `outputs/signal_boards/game_environment_features.csv`
- `outputs/signal_boards/opponent_defense_fit_features.csv`
- `outputs/signal_boards/signal_context_features.csv`

Recent form is based on L3/L5/L8 pre-target weekly averages. Game environment is sourced from schedule spread/total fields when present. Defense fit is noisy by nature, so V1 applies shrinkage:

`adjusted_metric = league_average + min(1.0, sample_games / 10) * (raw_metric - league_average)`

Defense fit should be treated as a research signal, not certainty.

## V1 Rule

Missing signal families reduce data quality and must be visible in review notes. They are not treated as neutral and are never painted green.
