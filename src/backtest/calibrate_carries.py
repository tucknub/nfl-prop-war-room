from __future__ import annotations

import pandas as pd
from src.common import load_config, output_path


def main() -> None:
    cfg = load_config()
    path = output_path("carries_backtest_rows_candidates.csv", cfg)
    if not path.exists():
        from src.backtest.backtest_carries import main as backtest_main
        backtest_main()
    rows = pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()
    if rows.empty: report = pd.DataFrame()
    else:
        df = rows[rows["scoreable"]].copy()
        df["abs_error"] = (df["projected_carries_calibrated"] - df["actual_carries"]).abs()
        report = df.groupby(["calibration_bucket", "confidence_bucket"], dropna=False).agg(rows=("player_id", "size"),
            avg_projected_carries=("projected_carries_raw", "mean"), avg_actual_carries=("actual_carries", "mean"), mae=("abs_error", "mean")).reset_index()
        report["calibration_note"] = "Candidate-only walk-forward calibration; historical-test only."
    report.to_csv(output_path("carries_calibration_report_candidates.csv", cfg), index=False)
    print(f"Wrote carries calibration report with {len(report):,} rows")


if __name__ == "__main__": main()
