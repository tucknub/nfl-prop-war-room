# Live Data Intake Report

Run timestamp: `2026-07-07T14:56:35+00:00`

Can forward projection be considered? `No`

Can true betting edge be considered? `No`

Final readiness: `NO-GO`

Why not? `Current Roster Map: NEEDS DATA; Role / Depth Chart Map: NEEDS DATA; Injury / Availability Map: NEEDS DATA; Market Odds Map: NEEDS DATA; Identity Validation: NEEDS DATA; Edge Preview Board: BLOCKED`

Files needing real data:
- `data/gates/rosters/` using `data/gates/rosters/current_roster_input_template.csv`
- `data/gates/roles/` using `data/gates/roles/current_role_input_template.csv`
- `data/gates/injuries/` using `data/gates/injuries/current_injury_input_template.csv`
- `data/gates/odds/` using `data/gates/odds/current_market_odds_input_template.csv`

Validation commands to run next:
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

Templates do not count as real data. Synthetic dry-run fixtures do not count as production data.
