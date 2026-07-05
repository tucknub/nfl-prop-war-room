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

The dashboard is now organized as the NFL Prop War Room multi-market framework. Four active built historical-test markets exist: Receptions V1, Receiving Yards V1, Rushing Yards V1, and Carries V1. Passing yards, completions, pass attempts, targets, anytime TD, longest reception, and longest rush remain planned.

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

Receptions V1, Receiving Yards V1, Rushing Yards V1, and Carries V1 are active historical-test markets. All remain `NO-GO` until real roster, role, injury, identity, and market odds gates pass. Planned markets are clearly labeled `Planned / Not Built Yet`.
