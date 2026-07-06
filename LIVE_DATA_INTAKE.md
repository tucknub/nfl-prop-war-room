# Live Data Intake Workflow

This workflow is the bridge from historical testing to future live-readiness. It does not make the app live by itself, does not switch `projection_mode`, and does not create live betting output.

## Files To Fill

Use the templates as column guides, then save real non-template CSVs in the matching folders:

- Current roster/team data: `data/gates/rosters/`
  - Template: `data/gates/rosters/current_roster_input_template.csv`
  - Required columns: `player_id`, `player_name`, `position`, `current_team`, `roster_status`, `depth_chart_role`, `source`, `source_url`, `updated_at`, `manual_override`, `notes`
- Role/depth-chart data: `data/gates/roles/`
  - Template: `data/gates/roles/current_role_input_template.csv`
  - Required columns: `player_id`, `player_name`, `team`, `position`, `projected_role`, `starter_status`, `depth_chart_rank`, `projected_snap_share`, `projected_route_share`, `projected_carry_share`, `projected_target_share`, `role_confidence`, `source`, `source_url`, `updated_at`, `manual_override`, `notes`
- Injury/availability data: `data/gates/injuries/`
  - Template: `data/gates/injuries/current_injury_input_template.csv`
  - Required columns: `player_id`, `player_name`, `team`, `position`, `injury_status`, `injury_detail`, `practice_status`, `game_status`, `availability_risk`, `projection_action`, `source`, `source_url`, `updated_at`, `manual_override`, `notes`
- Sportsbook market odds: `data/gates/odds/`
  - Template: `data/gates/odds/current_market_odds_input_template.csv`
  - Required columns: `player_id`, `player_name`, `team`, `opponent`, `market_key`, `market_display_name`, `sportsbook`, `line`, `over_odds`, `under_odds`, `odds_timestamp`, `source`, `source_url`, `manual_override`, `notes`

## What Counts As Real Data

A real data file is a non-template CSV placed in the correct gate folder. Template files and files with `template` in the filename do not count as real data. Synthetic dry-run fixtures under `tests/fixtures/` do not count as production data.

## READY Conditions

- Current Roster Map: every real row must match identity, verify current team, and avoid unresolved team conflicts.
- Role / Depth Chart Map: every real row must match identity/current team and have usable role confidence.
- Injury / Availability Map: every real row must match identity/current team/role and avoid unclear or unavailable status.
- Market Odds Map: every real row must have supported market key, valid line, valid American odds, matched identity, and no live gate blocker.
- Identity Validation: no unmatched, duplicate-name, or team-verify rows for real gate data.
- Edge Preview Board: true edge remains blocked until odds and every live-context gate are ready.
- Safety Validator: all safety assertions must pass.
- Forward Dry Run: fixture-only forward-readiness logic must pass.

## Validation Commands

Run these after filling data:

```powershell
python -m src.run_prop_war_room_pipeline
python -m src.validate_receptions_safety
python -m src.validate_forward_projection_dry_run
python -m src.load.validate_current_roster_map
python -m src.load.validate_current_role_map
python -m src.load.validate_current_injury_map
python -m src.load.validate_market_odds_map
python -m src.export.validate_edge_preview_board
python -m src.validate_edge_dry_run
```

Final Readiness remains `NO-GO` until all required gates pass in a true forward-ready setup. Historical-test outputs must remain `HISTORICAL TEST ONLY`.
