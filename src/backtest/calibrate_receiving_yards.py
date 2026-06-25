from __future__ import annotations

import pandas as pd

from src.common import load_config, output_path


def main() -> None:
    cfg = load_config()
    rows_path = output_path("receiving_yards_backtest_rows_candidates.csv", cfg)
    if not rows_path.exists():
        from src.backtest.backtest_receiving_yards import main as backtest_main

        backtest_main()
    rows = pd.read_csv(rows_path, low_memory=False) if rows_path.exists() else pd.DataFrame()
    if rows.empty:
        report = pd.DataFrame()
    else:
        df = rows[rows.get("scoreable", False)].copy()
        report = (
            df.groupby(["calibration_bucket", "confidence_bucket"], dropna=False)
            .agg(
                rows=("player_id", "size"),
                avg_projected_receiving_yards=("projected_receiving_yards_raw", "mean"),
                avg_actual_receiving_yards=("actual_receiving_yards", "mean"),
                mae=("projected_receiving_yards_calibrated", lambda s: (s - df.loc[s.index, "actual_receiving_yards"]).abs().mean()),
            )
            .reset_index()
        )
        report["calibration_note"] = "Uses candidate-only walk-forward RMSE/multipliers; historical-test only."
    report.to_csv(output_path("receiving_yards_calibration_report_candidates.csv", cfg), index=False)
    print(f"Wrote receiving yards calibration report with {len(report):,} rows")


if __name__ == "__main__":
    main()
