from __future__ import annotations

import pandas as pd

from src.common import load_config, output_path
from src.features.build_carries_feature_table import build_carries_feature_table
from src.features.build_rushing_yards_feature_table import RUSHING_POSITIONS
from src.models.receptions_model import add_team_verification, get_projection_target


BUCKETS = ["0-3", "3-7", "7-12", "12-18", "18+"]
BINS = [-0.01, 3, 7, 12, 18, 99]


def assign_bucket(values: pd.Series) -> pd.Series:
    return pd.cut(values, bins=BINS, labels=BUCKETS).astype(str)


def load_multipliers(config: dict) -> dict[str, float]:
    result = {bucket: 1.0 for bucket in BUCKETS}
    path = output_path("carries_calibration_multipliers.csv", config)
    if path.exists():
        for _, row in pd.read_csv(path, low_memory=False).iterrows():
            result[str(row["calibration_bucket"])] = float(row["calibration_multiplier"])
    return result


def project_carries(features: pd.DataFrame, config: dict | None = None, multipliers: dict[str, float] | None = None) -> pd.DataFrame:
    cfg = config or load_config()
    pos = features["position"].fillna("").astype(str).str.upper()
    history = pd.to_numeric(features.get("career_carries_entering", 0), errors="coerce").fillna(0) > 0
    prior = pd.to_numeric(features.get("prior_carries", 0), errors="coerce").fillna(0) > 0
    df = features[pos.isin(RUSHING_POSITIONS) & (history | prior)].copy()
    df = add_team_verification(df, cfg)
    df["projected_team_rush_attempts"] = pd.to_numeric(df["projected_team_rush_attempts"], errors="coerce")
    df["projected_player_rush_attempt_share"] = pd.to_numeric(df["projected_player_rush_attempt_share"], errors="coerce")
    df = df.dropna(subset=["projected_team_rush_attempts", "projected_player_rush_attempt_share"])
    df["projected_carries_raw"] = df["projected_team_rush_attempts"] * df["projected_player_rush_attempt_share"]
    df["calibration_bucket"] = assign_bucket(df["projected_carries_raw"])
    mapping = multipliers or load_multipliers(cfg)
    df["calibration_multiplier"] = df["calibration_bucket"].map(mapping).fillna(1.0)
    df["projected_carries_calibrated"] = df["projected_carries_raw"] * df["calibration_multiplier"]
    df["projected_carries"] = df["projected_carries_calibrated"]
    df["is_prop_candidate"] = (df["projected_carries_calibrated"] >= 1) & df["current_team_verified"].astype(bool)
    df["usage_status"] = "HISTORICAL TEST ONLY"
    df = df.sort_values("projected_carries_calibrated", ascending=False)
    df["overall_rank"] = range(1, len(df) + 1)
    df["team_rank"] = df.groupby(["season", "week", "team"])["projected_carries_calibrated"].rank(method="first", ascending=False).astype(int)
    df["position_rank"] = df.groupby(["season", "week", "position"])["projected_carries_calibrated"].rank(method="first", ascending=False).astype(int)
    return df


def build_week_projection(config: dict | None = None, candidates_only: bool = True) -> pd.DataFrame:
    cfg = config or load_config()
    mode, season, week = get_projection_target(cfg)
    path = output_path("carries_feature_table.csv", cfg)
    features = pd.read_csv(path, low_memory=False) if path.exists() else build_carries_feature_table(cfg)
    df = project_carries(features, cfg)
    df = df[(df["season"] == season) & (df["week"] == week)].copy()
    if candidates_only:
        df = df[df["is_prop_candidate"]].copy()
    df = df.sort_values("projected_carries_calibrated", ascending=False)
    df["overall_rank"] = range(1, len(df) + 1)
    df["team_rank"] = df.groupby(["season", "week", "team"])["projected_carries_calibrated"].rank(method="first", ascending=False).astype(int)
    df["position_rank"] = df.groupby(["season", "week", "position"])["projected_carries_calibrated"].rank(method="first", ascending=False).astype(int)
    df["projection_mode"] = mode
    return df


def output_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["projection_mode", "season", "week", "team", "opponent_team", "player_id", "player_name", "position",
            "projected_team_rush_attempts", "projected_player_rush_attempt_share", "projected_carries_raw", "calibration_bucket",
            "calibration_multiplier", "projected_carries_calibrated", "projected_carries", "is_prop_candidate", "overall_rank",
            "team_rank", "position_rank", "confidence_score", "confidence_bucket", "quality_flags", "usage_status", "leakage_status"]
    return df[[c for c in cols if c in df.columns]].copy()


def main() -> None:
    cfg = load_config()
    _, _, week = get_projection_target(cfg)
    all_rows = output_columns(build_week_projection(cfg, False))
    candidates = output_columns(build_week_projection(cfg, True))
    all_rows.to_csv(output_path(f"carries_projection_week_{week:02d}_all.csv", cfg), index=False)
    candidates.to_csv(output_path(f"carries_projection_week_{week:02d}_candidates.csv", cfg), index=False)
    print(f"Wrote carries all projection with {len(all_rows):,} rows")
    print(f"Wrote carries candidates projection with {len(candidates):,} rows")


if __name__ == "__main__":
    main()
