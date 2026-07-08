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

The main user-facing entry point is `Signal Command Center`. Use it before the legacy model output pages. The dashboard sections are:

- Main Signal Workflow
- Research / Audit Lab
- Readiness / Data Admin
- Legacy Model Outputs

Signal pages are the main workflow. Research/audit pages validate the signal system. Readiness/admin pages explain data quality and safety blockers. Odds and CLV are not the current product focus.

## Kasper-Style Signal Board UX Polish V1

The main signal workflow now uses a cleaner command-center style: polished KPI cards, top-player cards, compact by-game summaries, green/yellow/orange/red score cells, tier/action badges, reliability chips, and a shared legend. Signal Command Center is the first page to use.

Colors are intentionally simple: dark green for elite, green for strong, yellow for watch, orange for review/risk, red for blocked/weak, and gray for missing or unavailable. Debug/audit/admin pages remain secondary to visual signal scanning.

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

## Signal Score Audit V1

The Signal Score Audit page reviews score distributions, component correlations, possible double-counting risk, player-level drivers, and plain-English explanations. It is research-only and does not prove profitability. Outcome audit data appears only when safe historical signal actuals are available; otherwise the page labels the outcome section as not yet available.

## Historical Signal Backtest V1

The Historical Signal Backtest page checks whether higher historical signal scores and tiers align with actual past player production. It shows tier lift, score-bucket monotonicity, component usefulness, and market-family strength. This is research-only, does not use pricing/line movement, and should guide future score review rather than live use.

## Signal Weight Tuning Lab V1

The Signal Weight Tuning Lab page compares `current_v1` against challenger score-weight profiles using historical signal backtest outputs. It shows champion-versus-challenger comparisons, market-family tier lift, component demotion/increase suggestions, and a research-only recommended challenger YAML preview.

The page does not automatically promote challengers, does not create live betting output, and does not build a new market. It is meant to help decide whether receiving, rushing, and passing eventually need different score formulas while keeping `current_v1` as the production champion for now.

## Champion vs Challenger Signal Preview V1

The Champion vs Challenger Signal Preview page shows side-by-side production and challenger signal behavior without replacing the main boards. It displays family comparison, top movers, tier changes, action changes, and champion/challenger/delta board views.

`current_v1` remains the production champion. Rushing and passing challenger profiles are preview-only, and promotion requires explicit user approval after review.

## Player Signal Drilldown V1

The Player Signal Drilldown page lets the user inspect one player at a time. It shows summary cards, positive and negative drivers, review/block reasons, market-family rows, sourced context, prior-game history, and research-only champion/challenger comparison rows when available.

The page explains signal strength only. It does not use odds or CLV, does not create betting output, and leaves missing data visible instead of filling unsupported assumptions.

## Dashboard Product Reset V1

The normal visible sidebar is intentionally small:

- Home
- Signal Command Center
- By-Game Matchup Board
- Position Signal Boards
- Player Signal Drilldown
- Blocked / Review
- Research Lab
- Admin / Readiness

Old build, debug, audit, gate, and single-market pages live in `dashboard/archived_pages/`. They are recoverable for maintenance but are not visible in Streamlit's normal sidebar. Use Research Lab for validation/backtest/tuning work and Admin / Readiness for data quality, gates, identity, current maps, and safety status.
