# NFL Prop War Room

This is a local Streamlit dashboard for inspecting the NFL Prop War Room historical-test/control-room outputs.

Run the safe pipeline first:

```powershell
python -m src.run_receptions_pipeline
python -m src.validate_receptions_safety
python -m src.validate_forward_projection_dry_run
```

Start the dashboard:

```powershell
streamlit run dashboard/Home.py
```

Preferred Streamlit Cloud main file path: `dashboard/Home.py`.
Legacy-compatible path: `dashboard/app.py`.

The dashboard reads files from `outputs/` and does not upload anything. It is research/model review only until `Live Readiness = GO`.

This is the full NFL Prop War Room dashboard shell. Receptions, Receiving Yards, Rushing Yards, Carries, Pass Attempts, Completions, and Passing Yards V1 are active historical-test markets; the other markets remain planned. The Passing Yards page includes QB projections, a passing-volume versus efficiency view, and a no-odds research ladder. Current roster mapping is built but remains `NEEDS DATA` until real source-backed roster files are loaded.

Current expected state for the stable snapshot:

- Final readiness: `NO-GO`
- Leakage status: `PASS`
- Usage status: `HISTORICAL TEST ONLY`
- Live betting output created: `False`

Pages:

- Live Readiness
- Current Roster / Team Mapping
- Injury / Availability Mapping
- Market Odds Mapping
- Edge Preview Board
- End-to-End Edge Dry Run
- Live Data Intake
- NFL Signal Board Foundation
- Receptions Dashboard
- Line Ladder
- Market Edges

## Current Roster / Team Mapping

The roster-map page separates historical stat-team context from verified current/projection-team context. Team changes are resolved through source-backed roster inputs or approved override files, never hardcoded inside market models. Template-only inputs keep the roster map at `NEEDS DATA`, so forward live use remains blocked.

## Role / Depth Chart Mapping

The role-map page verifies projected role, starter status, depth-chart rank, workload shares, and confidence after current-team mapping. Role changes and overrides are supplied through source-backed gate files, never hardcoded in model math. Template-only inputs keep the Role Gate at `NEEDS DATA`; low or unknown roles cannot silently become live-ready.

## Injury / Availability Mapping

The injury-map page verifies player availability after current-team and role context are established. Real injury inputs belong in `data/gates/injuries/`; template files are ignored as production data. Approved injury overrides are supplied through `injury_overrides_template.csv`-shaped files, never hardcoded into projection math. Questionable, unknown, limited, out, IR, inactive, team-mismatched, and unapproved rows keep live readiness blocked until reviewed.

## Market Odds Mapping

The odds-map page normalizes sportsbook lines and American prices for active markets, then converts prices into implied probabilities for future model-versus-market comparison. Real sportsbook odds belong in `data/gates/odds/`; template files are ignored as production data. The page is not a betting board: true edge still requires verified odds, current roster, role, injury, identity, safety gates, and `Live Readiness = GO`.

## Edge Preview Board

The Edge Preview Board is a research-only decision preview. It combines line-ladder model probabilities, odds-map status, and live-context blockers so the workflow is visible before real odds are loaded. It is not a betting board, and no row can become a qualified edge while Final Readiness is `NO-GO`.

## End-to-End Edge Dry Run

The Edge Dry Run page shows two validations: production missing live data remains blocked, and isolated synthetic all-gates-ready data can produce qualified edges inside dry-run outputs only. These rows are labeled `SYNTHETIC TEST ONLY`; they are not real betting data and do not make production live.

## Live Data Intake

The Live Data Intake page is the bridge between historical testing and future forward projection. It explains which real files must be filled, where to place them, which commands to run, and what still blocks GO. It does not make the app live; real data must be loaded and validated, and Final Readiness remains `NO-GO` until every required gate passes.

## NFL Signal Board Foundation

The Signal Board Foundation page reads `outputs/signal_boards/player_week_signal_master.csv`, the one master player-week signal table. It is not an odds, CLV, or new-market page. V1 scores use sourced projection and data-quality context only; opponent fit, weather, practice trends, and detailed defensive context are planned but not faked.

## Heatmap UI V1

The main Signal Boards are the user-facing research layer:

- Slate Signal Board
- By-Game Matchup Board
- Receiving Signal Board
- Rushing Signal Board
- Passing Signal Board
- Blocked / Review Board

They read from `outputs/signal_boards/` and derive from `player_week_signal_master.csv`. They do not recompute score formulas, do not create live betting output, and do not add new markets. Existing model pages remain debug/research views, while readiness and gate pages remain admin/safety views. Odds/CLV are not the focus of these heatmaps; opponent, weather, and coverage context stays limited until real data sources are loaded.

## Signal Context Enrichment V1

The signal pages now include sourced football context when available:

- Recent L3/L5/L8 form from pre-target weekly player stats.
- Game environment from schedule spread/total fields.
- Opponent defense fit from historical allowed stats with reliability shrinkage.

Defense fit is noisy and should be read as a research signal, not certainty. Weather, route share, first-read share, shadow coverage, and CB matchup data remain unavailable until real sources are added.
- Gate Status
- Identity Warnings
- Run Reports
