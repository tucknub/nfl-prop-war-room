from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.backtest.backtest_receptions import apply_candidate_calibration_to_backtests, run_walk_forward_backtest
from src.features.build_receptions_feature_table import build_receptions_feature_table
from src.features.history_window import get_history_config
from src.models.receptions_model import CALIBRATION_BINS, CALIBRATION_BUCKETS, get_projection_target


def build_calibration_report(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    df = scored[scored["scoreable"]].copy()
    if df.empty:
        return pd.DataFrame()
    projection_col = "projected_receptions_raw" if "projected_receptions_raw" in df.columns else "projected_receptions"
    df["projection_bucket"] = pd.cut(
        df[projection_col],
        bins=CALIBRATION_BINS,
        labels=CALIBRATION_BUCKETS,
    )
    report = (
        df.groupby(["projection_bucket", "confidence_bucket"], observed=True)
        .agg(
            rows=("player_id", "size"),
            avg_projected_receptions=(projection_col, "mean"),
            avg_actual_receptions=("actual_receptions", "mean"),
            mae=(projection_col, lambda s: np.nan),
        )
        .reset_index()
    )
    errors = (
        df.assign(abs_error=(df[projection_col] - df["actual_receptions"]).abs())
        .groupby(["projection_bucket", "confidence_bucket"], observed=True)["abs_error"]
        .mean()
        .reset_index(name="mae")
    )
    report = report.drop(columns=["mae"]).merge(errors, on=["projection_bucket", "confidence_bucket"], how="left")
    report["calibration_note"] = "Skipped rows with thin input history and no prior baseline."
    return report


def main() -> None:
    cfg = load_config()
    _, history_end, _, _, _ = get_history_config(cfg)
    feature_path = output_path("receptions_feature_table.csv", cfg)
    features = pd.read_csv(feature_path, low_memory=False) if feature_path.exists() else build_receptions_feature_table(cfg)
    scored, _ = run_walk_forward_backtest(features, history_end)
    scored_candidates, _ = run_walk_forward_backtest(
        features,
        history_end,
        candidates_only=True,
    )
    _, scored_candidates_calibrated, multipliers = apply_candidate_calibration_to_backtests(scored, scored_candidates)
    report = build_calibration_report(scored)
    report_candidates = build_calibration_report(scored_candidates)
    report.to_csv(output_path("receptions_calibration_report.csv", cfg), index=False)
    report.to_csv(output_path("receptions_calibration_report_all.csv", cfg), index=False)
    report_candidates.to_csv(output_path("receptions_calibration_report_candidates.csv", cfg), index=False)
    multipliers.to_csv(output_path("receptions_calibration_multipliers.csv", cfg), index=False)
    scored_candidates_calibrated.to_csv(output_path("receptions_backtest_rows_candidates.csv", cfg), index=False)
    print(f"Wrote all calibration report with {len(report):,} rows")
    print(f"Wrote candidate calibration report with {len(report_candidates):,} rows")


if __name__ == "__main__":
    main()
