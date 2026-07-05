from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.features.build_rushing_yards_feature_table import build_rushing_yards_feature_table
from src.features.history_window import get_history_config
from src.models.rushing_yards_model import YARD_BUCKETS, assign_bucket, project_rushing_yards


def _scoreable(df: pd.DataFrame) -> pd.Series:
    return (pd.to_numeric(df.get("career_carries_entering", 0), errors="coerce").fillna(0) >= 20) | (pd.to_numeric(df.get("prior_carries", 0), errors="coerce").fillna(0) >= 10)


def build_multipliers(scored: pd.DataFrame) -> pd.DataFrame:
    df = scored[scored["scoreable"]].copy() if not scored.empty else pd.DataFrame()
    if not df.empty:
        df["calibration_bucket"] = assign_bucket(df["projected_rushing_yards_raw"])
    rows = []
    for bucket in YARD_BUCKETS:
        b = df[df["calibration_bucket"] == bucket] if not df.empty else pd.DataFrame()
        projected = b["projected_rushing_yards_raw"].sum() if not b.empty else 0.0
        actual = b["actual_rushing_yards"].sum() if not b.empty else 0.0
        rows.append({"calibration_bucket": bucket, "rows": len(b), "raw_projected_total": projected, "actual_total": actual,
                     "calibration_multiplier": float(actual / projected) if projected > 0 else 1.0})
    return pd.DataFrame(rows)


def apply_multipliers(scored: pd.DataFrame, multipliers: pd.DataFrame) -> pd.DataFrame:
    if scored.empty:
        return scored
    df = scored.copy()
    mapping = dict(zip(multipliers["calibration_bucket"], multipliers["calibration_multiplier"]))
    df["calibration_bucket"] = assign_bucket(df["projected_rushing_yards_raw"])
    df["calibration_multiplier"] = df["calibration_bucket"].map(mapping).fillna(1.0)
    df["projected_rushing_yards_calibrated"] = df["projected_rushing_yards_raw"] * df["calibration_multiplier"]
    return df


def summarize(scored: pd.DataFrame) -> pd.DataFrame:
    df = scored[scored["scoreable"]].copy() if not scored.empty else pd.DataFrame()
    if df.empty:
        return pd.DataFrame()
    raw = df["projected_rushing_yards_raw"] - df["actual_rushing_yards"]
    cal = df["projected_rushing_yards_calibrated"] - df["actual_rushing_yards"]
    return pd.DataFrame({"rows_scored": [len(df)], "raw_mae": [raw.abs().mean()], "raw_rmse": [np.sqrt((raw ** 2).mean())],
                         "raw_bias": [raw.mean()], "calibrated_mae": [cal.abs().mean()], "calibrated_rmse": [np.sqrt((cal ** 2).mean())],
                         "calibrated_bias": [cal.mean()], "walk_forward_rule": ["Week N uses features available through Week N-1"]})


def run_backtest(features: pd.DataFrame, season: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    cfg = load_config()
    season_df = features[features["season"] == season]
    for week in sorted(season_df["week"].dropna().unique()):
        test = season_df[season_df["week"] == week].copy()
        proj = project_rushing_yards(test, cfg, {bucket: 1.0 for bucket in YARD_BUCKETS})
        if proj.empty:
            continue
        proj["actual_rushing_yards"] = pd.to_numeric(proj["rushing_yards"], errors="coerce").fillna(0)
        proj["scoreable"] = _scoreable(proj)
        rows.append(proj)
    raw = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    multipliers = build_multipliers(raw)
    scored = apply_multipliers(raw, multipliers)
    return scored, summarize(scored), multipliers


def main() -> None:
    cfg = load_config()
    _, history_end, _, _, _ = get_history_config(cfg)
    path = output_path("rushing_yards_feature_table.csv", cfg)
    features = pd.read_csv(path, low_memory=False) if path.exists() else build_rushing_yards_feature_table(cfg)
    scored, summary, multipliers = run_backtest(features, history_end)
    scored.to_csv(output_path("rushing_yards_backtest_rows_candidates.csv", cfg), index=False)
    summary.to_csv(output_path("rushing_yards_backtest_summary_candidates.csv", cfg), index=False)
    multipliers.to_csv(output_path("rushing_yards_calibration_multipliers.csv", cfg), index=False)
    print(f"Wrote rushing yards backtest with {0 if summary.empty else int(summary['rows_scored'].iloc[0])} scored rows")


if __name__ == "__main__":
    main()
