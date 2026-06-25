# Stable Receptions V1 Historical-Test Snapshot

Timestamp: `2026-06-24T19:37:43.2455312-04:00`

## Current Mode

- Current projection mode: `historical_test`
- Target season/week: `2025 Week 1`
- History window: `2023-2024`
- Leakage status: `PASS`
- Leakage exists: `False`
- Usage status: `HISTORICAL TEST ONLY`

## Backtest Metrics

Candidate-only walk-forward backtest:

- Rows scored: `5,057`
- Raw MAE: `1.487326`
- Raw RMSE: `1.910588`
- Raw bias: `0.362055`
- Calibrated MAE: `1.400277`
- Calibrated RMSE: `1.865645`
- Calibrated bias: `0.000000`
- Walk-forward rule: `Week N uses features available through Week N-1`

## Calibration Method

Calibration uses candidate-only projection buckets with raw and calibrated projections preserved. Current calibration buckets are `0-1`, `1-2`, `2-3`, `3-4`, `4-6`, and `6+`, with confidence buckets retained. Thin input history without a prior baseline is skipped for calibration scoring.

## Market Probability Method

The market probability and line ladder layers use:

- Probability method: `Normal approximation: mean=calibrated_projection, sd=calibrated_RMSE`
- Calibration error used as standard deviation: `1.865645`
- Market probability rows: `0` because sportsbook odds are not loaded.
- Market edge rows: `0`
- Market edge blockers: `5`

## Line Ladder Status

- Line ladder status: `PASS`
- Line ladder rows: `6,400`
- Top-by-line rows: `250`
- Usage status: `HISTORICAL TEST ONLY`
- Purpose: Odds-free research and review only; not betting edge output.

## Gate Statuses

- History Audit: `PASS`
- Schedule Gate: `READY`
- Roster Gate: `NEEDS DATA`
- Role Gate: `NEEDS DATA`
- Injury Gate: `NEEDS DATA`
- Market Odds Gate: `NEEDS DATA`
- Receptions Dashboard: `HISTORICAL TEST ONLY`
- Model Output Mode: `NOT READY`
- Final Betting Use: `NO-GO`

Identity validation:

- Gate rows checked: `0`
- Unmatched gate rows: `0`
- TEAM_VERIFY rows: `0`
- Duplicate gate-name ambiguity rows: `0`
- Gate identity statuses: roster, role, injury, and market odds are all `NEEDS DATA` because real gate files are not loaded.

## Final Readiness

- Final readiness: `NO-GO`
- Blocked gates: `Historical test mode, Roster Gate, Role Gate, Injury Gate, Market Odds Gate`
- Live betting output created: `False`
- Safety validation result: `PASS`
- Forward dry-run result: `PASS`

## Why The System Is Still NO-GO

The build is intentionally in `historical_test` mode and cannot be treated as a live betting board. Current roster, role, injury, and market odds gates have no real validated 2026 data. Market odds are required before actual edge can be calculated.

## What Is Safe To Use Now

- Run `python -m src.run_receptions_pipeline` to rebuild historical-test outputs.
- Review the Receptions model board as historical test output.
- Review calibration, backtest, safety, and forward dry-run reports.
- Import the Google Sheets pack for control-room review.
- Use the line ladder for odds-free research and market-matching preparation.

## What Is Not Safe To Use Yet

- Do not treat any output as live 2026 projections.
- Do not treat line ladder probabilities as betting edges.
- Do not create live betting output while final readiness is `NO-GO`.
- Do not bypass roster, role, injury, identity, or market odds gates.
- Do not fabricate schedule, roster, injury, role, or odds data.
