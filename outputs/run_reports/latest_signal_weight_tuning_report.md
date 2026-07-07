# Signal Weight Tuning Report

Run timestamp: `2026-07-07T23:45:12+00:00`

Audit type: `RESEARCH ONLY / CHALLENGER PROFILES`

Profiles tested: `balanced_conservative, current_v1, data_quality_strict, game_script_heavy, matchup_heavy, projection_heavy, recent_form_heavy, usage_heavy`

Families tested: `receiving, rushing, passing`

Best challenger by family:

- `receiving`: `current_v1`
- `rushing`: `projection_heavy`
- `passing`: `game_script_heavy`

Recommendations rows: `48`

Production status: `current_v1 remains champion; no production weights changed`

Notes:

- Actual outcomes are used only for evaluation.
- Pregame component scores are reused from historical signal backtest rows.
- Challenger profiles are saved for review only.
