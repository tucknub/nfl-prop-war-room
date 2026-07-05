# Receiving Yards Line Ladder Report

Run timestamp: `2026-07-05T15:24:37+00:00`

Formula: `projected_receptions_calibrated x projected_yards_per_reception = projected_receiving_yards`

Formula choice: Receptions V1 already provides leakage-safe projected reception volume, while Receiving Yards V1 adds historical yards-per-reception efficiency from entering-week receiving yards/receptions.

Probability method: `Normal approximation: mean=calibrated_projection, sd=receiving_yards_backtest_calibrated_RMSE`

Calibration/error SD used: `25.308094`

## Backtest Metrics

Rows scored: `4902`

Raw MAE/RMSE/bias: `19.181155` / `25.875580` / `3.976463`

Calibrated MAE/RMSE/bias: `18.168193` / `25.308094` / `-0.000000`

Line ladder rows: `10980`

Top-by-line rows: `450`

Usage status: `HISTORICAL TEST ONLY`
