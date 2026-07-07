# Signal Data Sources

This inventory documents what NFL Prop War Room can currently source for signal boards and what remains unavailable.

V1 signal boards must use `outputs/signal_boards/player_week_signal_master.csv` as the source of truth. Future dashboard heatmaps should filter or sort that master table rather than recomputing signals independently.

## Available Now

- Projection signals from existing historical-test market outputs.
- Basic player context such as player name, team, position, season, and week.
- Some support usage projection fields such as target share, catch rate, estimated routes, carries, team pass attempts, completion rate, and yards-per-attempt where those columns already exist.
- Data quality flags, confidence buckets, and usage status from market outputs.
- Gate-level readiness statuses from roster, role, injury, odds, identity, and intake reports.

## Not Available Yet

The current project does not have true route share, snap share, first-read share, red-zone targets, goal-line carries, shadow coverage, man/zone matchup, verified weather, or practice-report progression as sourced production metrics. These must be marked `NOT_AVAILABLE`, `NEEDS SOURCE`, or `PLANNED_SOURCE` until real data exists.

## V1 Rule

Missing signal families reduce data quality and must be visible in review notes. They are not treated as neutral and are never painted green.
