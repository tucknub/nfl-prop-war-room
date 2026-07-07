# nfl_prop_projection_engine_v1

V1A/V1B builds a leakage-safe Receptions projection engine from nflverse/nflreadpy data.

The V1 formula is:

```text
projected_team_pass_attempts x projected_player_target_share x projected_catch_rate = projected_receptions
```

Only Receptions are implemented in this version. TD, rushing yards, receiving yards, QB rushing, and passing yards are intentionally out of scope until Receptions are proven.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Data

The loader uses `nflreadpy` when available and caches raw CSVs under `data/raw`. You can also place compatible CSVs there manually:

- `pbp.csv`
- `weekly.csv`
- `rosters.csv`

## V1A Outputs

```powershell
python -m src.load.load_nflverse
python -m src.features.build_receptions_feature_table
```

Creates:

- `outputs/team_week_features.csv`
- `outputs/player_week_features.csv`
- `outputs/receptions_feature_table.csv`
- `outputs/feature_quality_report.csv`
- `outputs/route_proxy_status.csv`
- `outputs/catch_rate_model_report.csv`

## V1B Outputs

```powershell
python -m src.models.receptions_model
python -m src.simulate.simulate_receptions
python -m src.backtest.backtest_receptions
python -m src.backtest.calibrate_receptions
python -m src.export.export_receptions_projection_csv
```

Creates:

- `outputs/receptions_projection_week_01.csv`
- `outputs/receptions_backtest_summary.csv`
- `outputs/receptions_calibration_report.csv`
- `outputs/receptions_simulation_distribution.csv`

## Projection Modes

The config separates history from the target week:

- `history_start_season`
- `history_end_season`
- `target_season`
- `target_week`
- `projection_mode`

`historical_test` mode is for model validation only. Outputs are labeled `HISTORICAL TEST ONLY` and must not be used as live betting boards.

`forward_projection` mode is for future/live projection work. It must not silently fall back to historical testing. If schedule, roster, role, injury, current-team verification, or other required live gates are missing, the export flow blocks live readiness.

## Leakage Rules

Walk-forward backtesting is mandatory. For Week N, training/features use only games available through Week N-1. Random train/test splits across the same season are not used.

Route participation is a proxy in V1 and every estimate is marked `ROUTE_PROXY_UNVALIDATED` until real route data is available.

## Google Sheet Control Room Exports

Run:

```powershell
python -m src.export.export_sheet_gates
```

This creates CSV imports for the Google Sheet control room:

- `outputs/google_sheets/schedule_gate_import.csv` -> `Schedule Gate`
- `outputs/google_sheets/roster_gate_import_template.csv` -> `Roster Gate`
- `outputs/google_sheets/role_gate_import_template.csv` -> `Role Gate`
- `outputs/google_sheets/injury_gate_import_template.csv` -> `Injury Gate`
- `outputs/google_sheets/market_odds_gate_import_template.csv` -> `Market Odds Gate`
- `outputs/google_sheets/live_readiness_export.csv` -> `Live Readiness`
- `outputs/google_sheets/forward_projection_blockers.csv` -> `Forward Readiness`
- `outputs/google_sheets_receptions_historical_test.csv` -> `Receptions Dashboard`

Gate behavior:

- Schedule gate uses local `data/raw/schedules.csv` when the target season/week exists. Missing target schedule becomes `NEEDS DATA`.
- Roster gate is a current-team verification template. `TEAM_VERIFY` means `DO NOT USE` for live use.
- Role gate defaults to `Unknown` and `NEEDS DATA`; unknown role prevents high-confidence live use.
- Injury gate defaults to `Unknown` and `NEEDS DATA`; unknown, out, IR, doubtful, or inactive status blocks or downgrades live use.
- Market odds gate is a Receptions odds template. No odds means no betting edge is produced.
- Live readiness stays `NO-GO` unless required gates are `READY` or `PASS` in `forward_projection` mode.

The board is not live-betting ready until `Live Readiness = GO`.

## Full Regeneration Sequence

```powershell
python -m compileall src
python -m src.features.build_receptions_feature_table
python -m src.models.receptions_model
python -m src.backtest.backtest_receptions
python -m src.backtest.calibrate_receptions
python -m src.export.export_receptions_projection_csv
python -m src.export.export_sheet_gates
```

The final command prints:

- `projection_mode`
- `target_season`
- `target_week`
- history window
- leakage status
- schedule, roster, role, injury, and market odds gate status
- final live readiness
- output file paths

## One-Command Safe Pipeline

Before importing anything into Google Sheets, run:

```powershell
python -m src.run_receptions_pipeline
```

This is the safest command for the Receptions V1B workflow. It runs the full feature, model, backtest, calibration, projection export, Google Sheets gate export, and import-pack build sequence. It stops on the first failed command and writes:

- `outputs/run_reports/latest_receptions_pipeline_report.md`
- `outputs/run_reports/latest_receptions_pipeline_status.csv`
- `outputs/run_reports/latest_receptions_pipeline_errors.csv`

The report confirms projection mode, target season/week, history window, leakage status, backtest metrics, calibration status, gate statuses, blocked gates, import pack location, live readiness, and whether any live betting output was created.

In `historical_test` mode the report must say `HISTORICAL TEST ONLY`, and final readiness must remain `NO-GO`. Do not treat any output as live betting-ready unless the report says `Final Live Readiness = GO`.

## Safety Validation

After running the pipeline, run:

```powershell
python -m src.validate_receptions_safety
```

Recommended pre-import workflow:

```powershell
python -m src.run_receptions_pipeline
python -m src.validate_receptions_safety
```

The first command builds all model outputs, gate exports, the Google Sheets import pack, and the pipeline report. The second command proves the generated outputs are safe: it checks projection mode, leakage status, live readiness, blocked gates, usage labels, import-pack contents, and confirms no live betting output is created while readiness is `NO-GO`.

Safety reports are written to:

- `outputs/run_reports/latest_receptions_safety_validation.md`
- `outputs/run_reports/latest_receptions_safety_validation.csv`

## Local Gate Input Loader

Real gate CSVs can be placed in:

- `data/gates/schedule/`
- `data/gates/rosters/`
- `data/gates/roles/`
- `data/gates/injuries/`
- `data/gates/odds/`

Each folder contains an input template:

- `data/gates/schedule/schedule_input_template.csv`
- `data/gates/rosters/roster_input_template.csv`
- `data/gates/roles/role_input_template.csv`
- `data/gates/injuries/injury_input_template.csv`
- `data/gates/odds/odds_input_template.csv`

Run:

```powershell
python -m src.load.load_gate_inputs
```

The loader ignores files with `_template` in the filename unless no real file exists. Templates do not count as real data and do not make the board live. If no real CSV exists for a gate, that gate remains `NEEDS DATA`.

Validated normalized gate files are written to `outputs/gate_inputs_normalized/`. The Google Sheets gate exporters use normalized real inputs only when they exist and validate to `READY` or `REVIEW`; otherwise they continue producing safe templates and blockers.

Current safest workflow:

```powershell
python -m src.run_receptions_pipeline
python -m src.validate_receptions_safety
python -m src.validate_forward_projection_dry_run
```

This rebuilds outputs, validates safety, and proves forward gate logic without creating live betting output.

## Identity Matching

Gate data must match model players safely before any gate can become live-ready. Build and validate identity files with:

```powershell
python -m src.load.build_identity_crosswalk
python -m src.load.validate_gate_identity_matches
```

The pipeline runs these commands automatically after `python -m src.load.load_gate_inputs` and before Google Sheets gate exports.

Outputs:

- `outputs/identity/player_identity_crosswalk.csv`
- `outputs/identity/team_abbreviation_crosswalk.csv`
- `outputs/identity/gate_identity_match_report.csv`
- `outputs/identity/unmatched_gate_rows.csv`
- `outputs/identity/duplicate_name_warnings.csv`
- `outputs/run_reports/latest_identity_validation.md`

Player IDs are preferred because names can collide, change formatting, or belong to multiple players. Name-only matching is allowed only when the normalized name is unique across candidates. Duplicate names and team mismatches block live use.

How to fix identity blockers:

- `UNMATCHED_PLAYER`: add or correct `Player ID`, player name, team, or source roster row.
- `DUPLICATE_PLAYER_NAME`: provide the exact `Player ID`; do not rely on name-only matching.
- `TEAM_VERIFY`: verify current team against roster data and correct stale or mismatched team values.

## Market Probability And Edge Engine

Run:

```powershell
python -m src.models.receptions_probability
python -m src.export.export_receptions_market_edges
```

V1 uses a transparent first-pass probability approximation:

- Mean = calibrated Receptions projection
- Standard deviation = candidate backtest calibrated RMSE, with a minimum floor
- Over probability = normal approximation probability that receptions exceed the sportsbook line
- Under probability = `1 - over probability`

American odds implied probability:

- Negative odds: `abs(odds) / (abs(odds) + 100)`
- Positive odds: `100 / (odds + 100)`

Edge formula:

- Over edge = `model_over_probability - implied_over_probability`
- Under edge = `model_under_probability - implied_under_probability`
- Best edge is the larger side.

V1 price grades:

- `PASS` when best edge is at least `0.05`, odds are valid, and identity is clean
- `REVIEW` when best edge is between `0.02` and `0.05`
- `BAD PRICE` when best edge is below `0.02`
- `NEEDS DATA` when odds or model probabilities are missing

Market edge outputs are written to `outputs/market_edges/`, but they are not betting-ready until `Live Readiness = GO`. In `historical_test`, positive edges are research-only and remain labeled `HISTORICAL TEST ONLY`.

## Odds-Free Line Ladder

Run:

```powershell
python -m src.export.export_receptions_line_ladder
```

The line ladder calculates model over/under probabilities for common reception lines before sportsbook odds are loaded:

```text
0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5
```

It uses the same normal approximation as the market probability engine: calibrated projection as the mean and calibrated RMSE as the standard deviation. The ladder is useful for research, review, and future market matching because it shows which players project above or below common lines before odds are available.

Outputs:

- `outputs/market_edges/receptions_line_ladder.csv`
- `outputs/market_edges/receptions_line_ladder_top_by_line.csv`
- `outputs/run_reports/latest_line_ladder_report.md`

Google Sheets optional research imports:

- `receptions_line_ladder.csv` imports to `Line Ladder!A1`
- `receptions_line_ladder_top_by_line.csv` imports to `Line Ladder Top!A1`

The line ladder does not calculate edge, does not include betting recommendations, and is research-only until `Live Readiness = GO` and sportsbook odds are matched. Odds are still required for actual edge, and historical-test output must remain labeled `HISTORICAL TEST ONLY`.

## Forward Projection Dry Run

To prove the forward gate logic without using production future data, run:

```powershell
python -m src.validate_forward_projection_dry_run
```

This is not a betting run. It does not upload to Google Sheets, does not create live betting output, and does not permanently change `config.yaml`.

The dry-run validates two cases:

- Real forward mode with missing gate data remains `NO-GO`.
- Synthetic fixtures under `tests/fixtures` can satisfy the gate logic only when every required condition is marked `READY`.

All fixture rows are marked `SYNTHETIC TEST ONLY`. Real 2026 schedule, roster, role, injury, and market odds data are still required before live use.

Dry-run reports are written to:

- `outputs/run_reports/latest_forward_projection_dry_run.md`
- `outputs/run_reports/latest_forward_projection_dry_run.csv`

## Stable V1 Historical-Test Snapshot

The stable Receptions V1 historical-test/control-room snapshot is the rollback point before real 2026 data integration. Recreate and verify this state with:

```powershell
python -m compileall src
python -m src.run_receptions_pipeline
python -m src.validate_receptions_safety
python -m src.validate_forward_projection_dry_run
```

Snapshot files:

- `outputs/run_reports/STABLE_RECEPTIONS_V1_HISTORICAL_TEST_SNAPSHOT.md`
- `outputs/run_reports/STABLE_RECEPTIONS_V1_FILE_INDEX.csv`
- `outputs/run_reports/STABLE_RECEPTIONS_V1_NEXT_STEPS.md`

This snapshot is historical-test only. Final readiness must remain `NO-GO`, leakage must remain `PASS`, and live betting output must remain uncreated until real forward schedule, roster, role, injury, identity, and market odds gates are loaded and validated.

## Local Streamlit Dashboard

Run the safe pipeline and validators before opening the local dashboard:

```powershell
python -m src.run_receptions_pipeline
python -m src.validate_receptions_safety
python -m src.validate_forward_projection_dry_run
streamlit run dashboard/Home.py
```

The dashboard reads the existing files under `outputs/` and is local only. It is for research and model review until `Live Readiness = GO`. In historical-test mode, dashboard rows must remain labeled `HISTORICAL TEST ONLY`, no live betting output should be created, and market edges remain blocked until real odds and gates are loaded.

The dashboard is now organized as the NFL Prop War Room multi-market framework. Seven active built historical-test markets exist: Receptions V1, Receiving Yards V1, Rushing Yards V1, Carries V1, Pass Attempts V1, Completions V1, and Passing Yards V1. Targets, anytime TD, longest reception, and longest rush remain planned. Passing Yards uses projected pass attempts multiplied by a leakage-safe projected yards per attempt; its board and no-odds line ladder are research-only.

## Streamlit Cloud Deployment

Before deploying or redeploying, run:

```powershell
python -m src.run_receptions_pipeline
python -m src.validate_receptions_safety
python -m src.validate_forward_projection_dry_run
python -m streamlit run dashboard/Home.py
```

For Streamlit Community Cloud, set the preferred main file path to `dashboard/Home.py`.
Legacy-compatible path: `dashboard/app.py`.

This dashboard is research-only unless `Live Readiness = GO`. Do not use it for live betting while final readiness is `NO-GO`, do not commit secrets, and do not upload `.env`. Streamlit secrets belong in `.streamlit/secrets.toml`, which is ignored by git.

Receptions V1, Receiving Yards V1, Rushing Yards V1, Carries V1, Pass Attempts V1, Completions V1, and Passing Yards V1 are active historical-test markets. Current Roster / Team Mapping V1 is built but production status remains `NEEDS DATA`. All remain `NO-GO` until real roster, role, injury, identity, and market odds gates pass.

## Current Roster / Team Mapping

Current-team mapping is a separate data and gate layer. Historical team identifies where a stat row was earned; current team is the latest verified roster team; projection team is the team context permitted for a forward projection. Model math does not contain one-off team fixes.

Place real source-backed roster CSVs in `data/gates/rosters/` using `current_roster_input_template.csv`. Template files are ignored as real data. Team changes require a source URL or an approved row based on `roster_team_overrides_template.csv`; missing IDs, ambiguous identities, and unsafe team conflicts remain review blockers.

```powershell
python -m src.load.build_current_roster_map
python -m src.load.validate_current_roster_map
```

Live forward mode remains blocked until `outputs/roster/current_roster_map_status.csv` is `READY` and every other required gate passes.

## Role / Depth Chart Mapping

Role mapping is a separate data and gate layer that verifies expected workload after current-team identity is established. Source-backed role inputs belong in `data/gates/roles/` using `current_role_input_template.csv`; template files never count as production data. Approved adjustments use `role_overrides_template.csv`, rather than hardcoded player exceptions in market models.

```powershell
python -m src.load.build_current_role_map
python -m src.load.validate_current_role_map
```

Low-confidence roles, unknown starter status, identity/team conflicts, missing IDs, and unapproved overrides remain review or blocking conditions. Live forward mode remains blocked until both current roster and current role maps are verified.

## Injury / Availability Mapping

Injury mapping is a separate data and gate layer that verifies whether a projected workload is actually available. Roster tells us where a player is. Role tells us expected workload. Injury mapping tells us whether that workload is available. A player can have a strong projection and still be blocked if availability is unclear.

Place real source-backed injury CSVs in `data/gates/injuries/` using `current_injury_input_template.csv`. Template files never count as production data. Approved availability adjustments use `injury_overrides_template.csv`; do not hardcode player-specific injury fixes in market models.

```powershell
python -m src.load.build_current_injury_map
python -m src.load.validate_current_injury_map
```

Questionable, unknown, limited-practice, missing-ID, identity-conflict, team-mismatch, and unapproved override rows require review. Out, IR, PUP, suspended, inactive, or explicit block rows remain blockers unless a source-backed approved override is present. Live forward mode remains blocked until current roster, current role, and current injury maps are verified.

## Market Odds Mapping

Market odds mapping is a separate data and gate layer for sportsbook lines and prices. It normalizes active-market odds, converts American prices into implied probabilities, and prepares future edge comparison against model probabilities. It does not change projection math and does not create live betting output while final readiness is `NO-GO`.

Place real source-backed odds CSVs in `data/gates/odds/` using `current_market_odds_input_template.csv`. Template files never count as production data. Approved odds corrections use `market_odds_overrides_template.csv`; do not hardcode sportsbook, player, or line fixes inside market models.

```powershell
python -m src.load.build_market_odds_map
python -m src.load.validate_market_odds_map
```

True edge requires both sides of the equation: model probability plus sportsbook implied probability. Missing odds, invalid market keys, invalid American odds, unmatched players, stale odds, missing sides, or roster/role/injury blockers keep the Market Odds Gate from becoming live-ready. Live forward/betting mode remains blocked until odds and every live gate are verified.

## Edge Preview Board

The Edge Preview Board is a unified research-only board that shows how qualified prop edges will be evaluated later. It is not a betting board. While final readiness is `NO-GO`, it can show no-odds watchlists and blockers only.

```powershell
python -m src.export.export_edge_preview_board
python -m src.export.validate_edge_preview_board
```

Future true edge is `model_probability - sportsbook_implied_probability`. A row can become a `Qualified Edge` only after real odds are matched, roster/role/injury/identity gates pass, leakage and safety validation pass, projection mode is live-ready, and `Final Readiness = GO`. Current historical-test output remains `Research Only`, `No Odds`, `Historical Test Only`, and `Not Betting Ready`.

## End-to-End Edge Dry Run

The Edge Dry Run validates the full edge decision pipeline without making production live. Scenario A confirms production remains blocked while live gate data is missing. Scenario B uses isolated synthetic fixtures to prove that roster, role, injury, odds, implied probability, and edge calculation can produce `Qualified Edge` rows only inside dry-run outputs.

```powershell
python -m src.validate_edge_dry_run
```

Dry-run outputs are labeled `SYNTHETIC TEST ONLY` and are written under `outputs/edge_preview_dry_run/`. They do not use real betting data, do not change production `projection_mode`, do not create live betting output, and do not make the app live. Production remains `NO-GO` until real live-context gates and safety checks pass.

## Live Data Intake Workflow

The Live Data Intake Workflow explains exactly which real roster, role, injury, and odds files must be filled before future forward projection can be considered. It is the bridge between historical testing and future live-readiness, but it does not itself make the app live.

```powershell
python -m src.export.export_live_data_intake_status
python -m src.export.validate_live_data_intake_status
```

Use [LIVE_DATA_INTAKE.md](LIVE_DATA_INTAKE.md) for the plain-English intake guide. Real data must be placed in the appropriate `data/gates/` folders as non-template CSVs, then the full validation command block must pass. Final Readiness remains `NO-GO` until every required gate passes.

## NFL Signal Board Foundation V1

NFL Signal Board Foundation V1 creates one canonical player-week signal table at `outputs/signal_boards/player_week_signal_master.csv`. Future slate, game, receiving, rushing, passing, blocked/review, heatmap, and drilldown boards should derive from this table instead of recomputing scores independently.

This is not an odds, CLV, or new-market build. Scores are limited to sourced data only. Projection and existing data-quality context are available now; opponent fit, weather, practice trends, detailed defense context, and live role/injury data are planned but not faked.

```powershell
python -m src.export.export_signal_data_inventory
python -m src.export.export_player_week_signal_master
python -m src.export.export_signal_board_views
python -m src.export.validate_player_week_signal_master
```

## Heatmap UI V1

Heatmap UI V1 adds user-facing signal boards to the Streamlit dashboard:

- Slate Signal Board
- By-Game Matchup Board
- Receiving Signal Board
- Rushing Signal Board
- Passing Signal Board
- Blocked / Review Board

These pages read existing CSVs from `outputs/signal_boards/`, which are derived from `player_week_signal_master.csv`. They use green-to-red styling for review, filtering, and ranking, but they do not change model math, do not recompute signal definitions, do not create live betting output, and do not add Targets V1 or any new market. Existing model pages remain debug/research views; the Signal Boards are the main user-facing research layer. Opponent, weather, and coverage context remains limited until real sources are loaded.

```powershell
python -m src.export.validate_signal_heatmap_ui
streamlit run dashboard/Home.py
```

## Signal Context Enrichment V1

Signal Context Enrichment V1 adds football context to the existing signal boards without creating a new market or changing projection math.

- Recent form comes from pre-target `data/raw/weekly.csv` L3/L5/L8 player averages.
- Game environment comes from `data/raw/schedules.csv` spread and total fields when present.
- Opponent defense fit comes from historical allowed stats by defense and position, then shrinks noisy values toward league average.
- Weather, route share, first-read share, shadow coverage, and CB matchup data remain unavailable until real source columns exist.

```powershell
python -m src.export.export_signal_context_features
python -m src.export.validate_signal_context_features
```

The signal boards remain historical-test research views while Final Readiness is `NO-GO`.

## Signal Score Audit V1

Signal Score Audit V1 adds research-only audit outputs for score behavior and explainability:

- Score distribution summaries by board.
- Component correlations with high-correlation pairs flagged as possible double-counting risk.
- Per-player top positive and negative drivers.
- Plain-English signal explanations and recommended review actions.

It does not prove profitability, does not use pricing/line-movement logic, and does not create a new market. Historical outcome validation is generated only if safe historical signal actuals exist; otherwise it is clearly labeled `NEEDS HISTORICAL SIGNAL BACKTEST DATA`.

```powershell
python -m src.export.export_signal_score_audit
python -m src.export.validate_signal_score_audit
```
