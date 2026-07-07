# Signal Score Audit Report

Run timestamp: `2026-07-07T15:16:12+00:00`

Audit type: `HISTORICAL TEST / RESEARCH ONLY`

Master/context rows: `762`

Distribution boards audited: `4`

High-correlation risk pairs: `2`

Driver audit rows: `762`

Explainability rows: `762`

Outcome audit status: `NEEDS HISTORICAL SIGNAL BACKTEST DATA`

Forbidden action language hits in audit outputs: `None`

Outcome source files inspected:

- `outputs\carries_backtest_rows_candidates.csv`
- `outputs\carries_backtest_summary_candidates.csv`
- `outputs\completions_backtest_rows_candidates.csv`
- `outputs\completions_backtest_summary_candidates.csv`
- `outputs\pass_attempts_backtest_rows_candidates.csv`
- `outputs\pass_attempts_backtest_summary_candidates.csv`
- `outputs\passing_yards_backtest_rows_candidates.csv`
- `outputs\passing_yards_backtest_summary_candidates.csv`
- `outputs\receiving_yards_backtest_rows_candidates.csv`
- `outputs\receiving_yards_backtest_summary_candidates.csv`
- `outputs\receptions_backtest_rows.csv`
- `outputs\receptions_backtest_rows_candidates.csv`
- `outputs\receptions_backtest_summary.csv`
- `outputs\receptions_backtest_summary_all.csv`
- `outputs\receptions_backtest_summary_candidates.csv`
- `outputs\rushing_yards_backtest_rows_candidates.csv`
- `outputs\rushing_yards_backtest_summary_candidates.csv`
- `outputs\signal_boards\signal_score_outcome_audit.csv`
- `src\backtest\__pycache__\backtest_carries.cpython-313.pyc`
- `src\backtest\__pycache__\backtest_completions.cpython-313.pyc`
- `src\backtest\__pycache__\backtest_pass_attempts.cpython-313.pyc`
- `src\backtest\__pycache__\backtest_passing_yards.cpython-313.pyc`
- `src\backtest\__pycache__\backtest_receiving_yards.cpython-313.pyc`
- `src\backtest\__pycache__\backtest_receptions.cpython-313.pyc`
- `src\backtest\__pycache__\backtest_rushing_yards.cpython-313.pyc`
- `src\backtest\backtest_carries.py`
- `src\backtest\backtest_completions.py`
- `src\backtest\backtest_pass_attempts.py`
- `src\backtest\backtest_passing_yards.py`
- `src\backtest\backtest_receiving_yards.py`
- `src\backtest\backtest_receptions.py`
- `src\backtest\backtest_rushing_yards.py`

Notes:

- This audit checks score structure, component behavior, driver labels, and explanation quality.
- It does not prove profitability.
- It does not change projection math or signal score weights.
- Outcome validation requires a historical signal table with actual outcome columns.
