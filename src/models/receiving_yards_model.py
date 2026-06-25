from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.features.build_receiving_yards_feature_table import RECEIVING_POSITIONS, build_receiving_yards_feature_table
from src.models.receptions_model import get_projection_target, project_receptions


YARD_BUCKETS = ["0-15", "15-25", "25-40", "40-60", "60+"]
YARD_BINS = [-0.01, 15, 25, 40, 60, 999]


def assign_calibration_bucket(raw_projection: pd.Series) -> pd.Series:
    return pd.cut(raw_projection, bins=YARD_BINS, labels=YARD_BUCKETS).astype(str)


def load_calibration_multipliers(config: dict) -> dict[str, float]:
    multipliers = {bucket: 1.0 for bucket in YARD_BUCKETS}
    path = output_path("receiving_yards_calibration_multipliers.csv", config)
    if path.exists():
        df = pd.read_csv(path, low_memory=False)
        for _, row in df.iterrows():
            multipliers[str(row["calibration_bucket"])] = float(row["calibration_multiplier"])
    return multipliers


def project_receiving_yards(features: pd.DataFrame, config: dict | None = None, multipliers: dict[str, float] | None = None) -> pd.DataFrame:
    cfg = config or load_config()
    rec = project_receptions(features, cfg)
    df = rec[rec["position"].fillna("").astype(str).str.upper().isin(RECEIVING_POSITIONS)].copy()
    df["projected_yards_per_reception"] = pd.to_numeric(df.get("projected_yards_per_reception"), errors="coerce").fillna(10.0).clip(4, 22)
    df["projected_receiving_yards_raw"] = df["projected_receptions_calibrated"] * df["projected_yards_per_reception"]
    df["calibration_bucket"] = assign_calibration_bucket(df["projected_receiving_yards_raw"])
    multiplier_map = multipliers or load_calibration_multipliers(cfg)
    df["calibration_multiplier"] = df["calibration_bucket"].map(multiplier_map).fillna(1.0).astype(float)
    df["projected_receiving_yards_calibrated"] = df["projected_receiving_yards_raw"] * df["calibration_multiplier"]
    df["projected_receiving_yards"] = df["projected_receiving_yards_calibrated"]
    df["is_prop_candidate"] = (
        (df["projected_receiving_yards_calibrated"] >= 5)
        & df["projected_yards_per_reception"].notna()
        & df["projected_receptions_calibrated"].notna()
        & df["current_team_verified"].astype(bool)
    )
    df["usage_status"] = "HISTORICAL TEST ONLY"
    df["quality_flags"] = df.get("quality_flags", "").fillna("").astype(str)
    low = pd.to_numeric(df.get("career_receptions_entering", 0), errors="coerce").fillna(0) < 10
    df.loc[low & ~df["quality_flags"].str.contains("LOW_YARDAGE_SAMPLE", regex=False), "quality_flags"] = (
        df.loc[low & ~df["quality_flags"].str.contains("LOW_YARDAGE_SAMPLE", regex=False), "quality_flags"].where(lambda s: s == "", lambda s: s + "|")
        + "LOW_YARDAGE_SAMPLE"
    )
    df = df.sort_values("projected_receiving_yards_calibrated", ascending=False)
    df["overall_rank"] = range(1, len(df) + 1)
    df["team_rank"] = df.groupby(["season", "week", "team"])["projected_receiving_yards_calibrated"].rank(
        method="first", ascending=False
    ).astype(int)
    df["position_rank"] = df.groupby(["season", "week", "position"])["projected_receiving_yards_calibrated"].rank(
        method="first", ascending=False
    ).astype(int)
    return df.sort_values("projected_receiving_yards_calibrated", ascending=False)


def build_week_projection(config: dict | None = None, candidates_only: bool = True) -> pd.DataFrame:
    cfg = config or load_config()
    mode, season, week = get_projection_target(cfg)
    path = output_path("receiving_yards_feature_table.csv", cfg)
    features = pd.read_csv(path, low_memory=False) if path.exists() else build_receiving_yards_feature_table(cfg)
    projection = project_receiving_yards(features, cfg)
    projection = projection[(projection["season"] == season) & (projection["week"] == week)].copy()
    if candidates_only:
        projection = projection[projection["is_prop_candidate"]].copy()
    projection = projection.sort_values("projected_receiving_yards_calibrated", ascending=False)
    projection["overall_rank"] = range(1, len(projection) + 1)
    projection["team_rank"] = projection.groupby(["season", "week", "team"])["projected_receiving_yards_calibrated"].rank(
        method="first", ascending=False
    ).astype(int)
    projection["position_rank"] = projection.groupby(["season", "week", "position"])[
        "projected_receiving_yards_calibrated"
    ].rank(method="first", ascending=False).astype(int)
    projection["projection_mode"] = mode
    projection["target_season"] = season
    projection["target_week"] = week
    return projection


def output_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "projection_mode", "season", "week", "team", "player_id", "player_name", "position",
        "projected_receptions_calibrated", "projected_yards_per_reception",
        "projected_receiving_yards_raw", "calibration_bucket", "calibration_multiplier",
        "projected_receiving_yards_calibrated", "projected_receiving_yards", "estimated_routes",
        "is_prop_candidate", "overall_rank", "team_rank", "position_rank", "confidence_score",
        "confidence_bucket", "quality_flags", "usage_status", "leakage_status",
    ]
    return df[[c for c in cols if c in df.columns]].copy()


def main() -> None:
    cfg = load_config()
    _, _, week = get_projection_target(cfg)
    all_rows = output_columns(build_week_projection(cfg, candidates_only=False))
    candidates = output_columns(build_week_projection(cfg, candidates_only=True))
    all_rows.to_csv(output_path(f"receiving_yards_projection_week_{week:02d}_all.csv", cfg), index=False)
    candidates.to_csv(output_path(f"receiving_yards_projection_week_{week:02d}_candidates.csv", cfg), index=False)
    print(f"Wrote receiving yards all projection with {len(all_rows):,} rows")
    print(f"Wrote receiving yards candidates projection with {len(candidates):,} rows")


if __name__ == "__main__":
    main()
