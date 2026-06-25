from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.features.build_receiving_yards_feature_table import build_receiving_yards_feature_table
from src.features.history_window import get_history_config
from src.models.receiving_yards_model import YARD_BUCKETS, assign_calibration_bucket, project_receiving_yards


def _scoreable(df: pd.DataFrame) -> pd.Series:
    prior = pd.to_numeric(df.get("prior_season_receptions", 0), errors="coerce").fillna(0) >= 5
    career = pd.to_numeric(df.get("career_receptions_entering", 0), errors="coerce").fillna(0) >= 10
    current = pd.to_numeric(df.get("current_season_games_entering", 0), errors="coerce").fillna(0) >= 3
    return prior | career | current


def build_calibration_multipliers(scored: pd.DataFrame) -> pd.DataFrame:
    df = scored[scored["scoreable"]].copy() if not scored.empty else pd.DataFrame()
    rows = []
    if not df.empty:
        df["calibration_bucket"] = assign_calibration_bucket(df["projected_receiving_yards_raw"])
    for bucket in YARD_BUCKETS:
        b = df[df["calibration_bucket"] == bucket] if not df.empty else pd.DataFrame()
        projected = b["projected_receiving_yards_raw"].sum() if not b.empty else 0.0
        actual = b["actual_receiving_yards"].sum() if not b.empty else 0.0
        rows.append(
            {
                "calibration_bucket": bucket,
                "rows": len(b),
                "raw_projected_total": projected,
                "actual_total": actual,
                "calibration_multiplier": float(actual / projected) if projected > 0 else 1.0,
            }
        )
    return pd.DataFrame(rows)


def apply_multipliers(scored: pd.DataFrame, multipliers: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return scored
    df = scored.copy()
    mapping = dict(zip(multipliers["calibration_bucket"], multipliers["calibration_multiplier"]))
    df["calibration_bucket"] = assign_calibration_bucket(df["projected_receiving_yards_raw"])
    df["calibration_multiplier"] = df["calibration_bucket"].map(mapping).fillna(1.0).astype(float)
    df["projected_receiving_yards_calibrated"] = df["projected_receiving_yards_raw"] * df["calibration_multiplier"]
    df["projected_receiving_yards"] = df["projected_receiving_yards_calibrated"]
    return df


def summarize(scored: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return pd.DataFrame()
    df = scored[scored["scoreable"]].copy()
    if df.empty:
        return pd.DataFrame()
    raw_error = df["projected_receiving_yards_raw"] - df["actual_receiving_yards"]
    cal_error = df["projected_receiving_yards_calibrated"] - df["actual_receiving_yards"]
    return pd.DataFrame(
        {
            "rows_scored": [len(df)],
            "raw_mae": [raw_error.abs().mean()],
            "raw_rmse": [np.sqrt((raw_error**2).mean())],
            "raw_bias": [raw_error.mean()],
            "calibrated_mae": [cal_error.abs().mean()],
            "calibrated_rmse": [np.sqrt((cal_error**2).mean())],
            "calibrated_bias": [cal_error.mean()],
            "walk_forward_rule": ["Week N uses features available through Week N-1"],
        }
    )


def run_backtest(features: pd.DataFrame, season: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    cfg = load_config()
    season_df = features[features["season"] == season]
    for week in sorted(season_df["week"].dropna().unique()):
        test = season_df[season_df["week"] == week].copy()
        if test.empty:
            continue
        proj = project_receiving_yards(test, cfg, multipliers={bucket: 1.0 for bucket in YARD_BUCKETS})
        proj["actual_receiving_yards"] = pd.to_numeric(proj["receiving_yards"], errors="coerce").fillna(0)
        proj["scoreable"] = _scoreable(proj)
        rows.append(proj)
    raw_scored = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    multipliers = build_calibration_multipliers(raw_scored)
    scored = apply_multipliers(raw_scored, multipliers)
    return scored, summarize(scored), multipliers


def main() -> None:
    cfg = load_config()
    _, history_end, _, _, _ = get_history_config(cfg)
    path = output_path("receiving_yards_feature_table.csv", cfg)
    features = pd.read_csv(path, low_memory=False) if path.exists() else build_receiving_yards_feature_table(cfg)
    scored, summary, multipliers = run_backtest(features, history_end)
    scored.to_csv(output_path("receiving_yards_backtest_rows_candidates.csv", cfg), index=False)
    summary.to_csv(output_path("receiving_yards_backtest_summary_candidates.csv", cfg), index=False)
    multipliers.to_csv(output_path("receiving_yards_calibration_multipliers.csv", cfg), index=False)
    print(f"Wrote receiving yards backtest with {0 if summary.empty else int(summary['rows_scored'].iloc[0])} scored rows")


if __name__ == "__main__":
    main()
