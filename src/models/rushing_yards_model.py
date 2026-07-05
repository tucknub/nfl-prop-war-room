from __future__ import annotations

import pandas as pd

from src.common import load_config, output_path
from src.features.build_rushing_yards_feature_table import RUSHING_POSITIONS, build_rushing_yards_feature_table
from src.models.receptions_model import add_team_verification, get_projection_target


YARD_BUCKETS = ["0-15", "15-25", "25-40", "40-60", "60+"]
YARD_BINS = [-0.01, 15, 25, 40, 60, 999]


def assign_bucket(values: pd.Series) -> pd.Series:
    return pd.cut(values, bins=YARD_BINS, labels=YARD_BUCKETS).astype(str)


def load_multipliers(config: dict) -> dict[str, float]:
    result = {bucket: 1.0 for bucket in YARD_BUCKETS}
    path = output_path("rushing_yards_calibration_multipliers.csv", config)
    if path.exists():
        for _, row in pd.read_csv(path, low_memory=False).iterrows():
            result[str(row["calibration_bucket"])] = float(row["calibration_multiplier"])
    return result


def project_rushing_yards(features: pd.DataFrame, config: dict | None = None, multipliers: dict[str, float] | None = None) -> pd.DataFrame:
    cfg = config or load_config()
    pos = features["position"].fillna("").astype(str).str.upper()
    history = pd.to_numeric(features.get("career_carries_entering", 0), errors="coerce").fillna(0) > 0
    prior = pd.to_numeric(features.get("prior_carries", 0), errors="coerce").fillna(0) > 0
    df = features[pos.isin(RUSHING_POSITIONS) & (history | prior)].copy()
    df = add_team_verification(df, cfg)
    df = df[df["confidence_bucket"].astype(str).str.lower().ne("unusable")].copy()
    df["projected_carries"] = pd.to_numeric(df["projected_carries"], errors="coerce")
    df["projected_yards_per_carry"] = pd.to_numeric(df["projected_yards_per_carry"], errors="coerce")
    df = df.dropna(subset=["projected_carries", "projected_yards_per_carry"])
    df["projected_rushing_yards_raw"] = df["projected_carries"] * df["projected_yards_per_carry"]
    df["calibration_bucket"] = assign_bucket(df["projected_rushing_yards_raw"])
    mapping = multipliers or load_multipliers(cfg)
    df["calibration_multiplier"] = df["calibration_bucket"].map(mapping).fillna(1.0).astype(float)
    df["projected_rushing_yards_calibrated"] = df["projected_rushing_yards_raw"] * df["calibration_multiplier"]
    df["projected_rushing_yards"] = df["projected_rushing_yards_calibrated"]
    df["is_prop_candidate"] = (df["projected_carries"] >= 1) & (df["projected_rushing_yards_calibrated"] >= 3) & df["current_team_verified"].astype(bool)
    df["usage_status"] = "HISTORICAL TEST ONLY"
    df = df.sort_values("projected_rushing_yards_calibrated", ascending=False)
    df["overall_rank"] = range(1, len(df) + 1)
    df["team_rank"] = df.groupby(["season", "week", "team"])["projected_rushing_yards_calibrated"].rank(method="first", ascending=False).astype(int)
    df["position_rank"] = df.groupby(["season", "week", "position"])["projected_rushing_yards_calibrated"].rank(method="first", ascending=False).astype(int)
    return df


def build_week_projection(config: dict | None = None, candidates_only: bool = True) -> pd.DataFrame:
    cfg = config or load_config()
    mode, season, week = get_projection_target(cfg)
    path = output_path("rushing_yards_feature_table.csv", cfg)
    features = pd.read_csv(path, low_memory=False) if path.exists() else build_rushing_yards_feature_table(cfg)
    df = project_rushing_yards(features, cfg)
    df = df[(df["season"] == season) & (df["week"] == week)].copy()
    if candidates_only:
        df = df[df["is_prop_candidate"]].copy()
    df = df.sort_values("projected_rushing_yards_calibrated", ascending=False)
    df["overall_rank"] = range(1, len(df) + 1)
    df["team_rank"] = df.groupby(["season", "week", "team"])["projected_rushing_yards_calibrated"].rank(method="first", ascending=False).astype(int)
    df["position_rank"] = df.groupby(["season", "week", "position"])["projected_rushing_yards_calibrated"].rank(method="first", ascending=False).astype(int)
    df["projection_mode"] = mode
    return df


def output_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["projection_mode", "season", "week", "team", "opponent_team", "player_id", "player_name", "position",
            "projected_carries", "projected_yards_per_carry", "projected_rushing_yards_raw", "calibration_bucket",
            "calibration_multiplier", "projected_rushing_yards_calibrated", "projected_rushing_yards", "is_prop_candidate",
            "overall_rank", "team_rank", "position_rank", "confidence_score", "confidence_bucket", "quality_flags",
            "usage_status", "leakage_status"]
    return df[[c for c in cols if c in df.columns]].copy()


def main() -> None:
    cfg = load_config()
    _, _, week = get_projection_target(cfg)
    all_rows = output_columns(build_week_projection(cfg, False))
    candidates = output_columns(build_week_projection(cfg, True))
    all_rows.to_csv(output_path(f"rushing_yards_projection_week_{week:02d}_all.csv", cfg), index=False)
    candidates.to_csv(output_path(f"rushing_yards_projection_week_{week:02d}_candidates.csv", cfg), index=False)
    print(f"Wrote rushing yards all projection with {len(all_rows):,} rows")
    print(f"Wrote rushing yards candidates projection with {len(candidates):,} rows")


if __name__ == "__main__":
    main()
