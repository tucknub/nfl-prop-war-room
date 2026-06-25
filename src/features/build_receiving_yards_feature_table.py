from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.features.build_receptions_feature_table import build_receptions_feature_table


RECEIVING_POSITIONS = {"WR", "TE", "RB"}


def _safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = pd.to_numeric(denominator, errors="coerce").replace(0, np.nan)
    return pd.to_numeric(numerator, errors="coerce") / denominator


def _shifted_rolling_sum(group: pd.DataFrame, column: str, window: int) -> pd.Series:
    return (
        pd.to_numeric(group[column], errors="coerce")
        .fillna(0)
        .shift(1)
        .rolling(window, min_periods=1)
        .sum()
    )


def build_receiving_yards_feature_table(config: dict | None = None) -> pd.DataFrame:
    cfg = config or load_config()
    path = output_path("receptions_feature_table.csv", cfg)
    base = pd.read_csv(path, low_memory=False) if path.exists() else build_receptions_feature_table(cfg)
    df = base.copy().sort_values(["player_id", "season", "week"])

    for col in ["receptions", "targets", "receiving_yards"]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)

    df["game_yards_per_reception"] = _safe_divide(df["receiving_yards"], df["receptions"])
    df["game_yards_per_target"] = _safe_divide(df["receiving_yards"], df["targets"])
    grouped = df.groupby("player_id", group_keys=False)
    df["career_receiving_yards_entering"] = grouped["receiving_yards"].cumsum() - df["receiving_yards"]
    df["career_receptions_entering"] = grouped["receptions"].cumsum() - df["receptions"]
    df["career_targets_entering_yards"] = grouped["targets"].cumsum() - df["targets"]
    df["career_ypr_entering"] = _safe_divide(df["career_receiving_yards_entering"], df["career_receptions_entering"])
    df["career_ypt_entering"] = _safe_divide(df["career_receiving_yards_entering"], df["career_targets_entering_yards"])
    df["receiving_yards_last_4"] = grouped.apply(lambda g: _shifted_rolling_sum(g, "receiving_yards", 4)).reset_index(level=0, drop=True)
    df["receptions_yards_last_4"] = grouped.apply(lambda g: _shifted_rolling_sum(g, "receptions", 4)).reset_index(level=0, drop=True)
    df["targets_yards_last_4"] = grouped.apply(lambda g: _shifted_rolling_sum(g, "targets", 4)).reset_index(level=0, drop=True)
    df["recent_ypr_last_4"] = _safe_divide(df["receiving_yards_last_4"], df["receptions_yards_last_4"])
    df["recent_ypt_last_4"] = _safe_divide(df["receiving_yards_last_4"], df["targets_yards_last_4"])

    season_stats = (
        df.groupby(["player_id", "season"], as_index=False)
        .agg(prior_season_receiving_yards=("receiving_yards", "sum"), prior_season_receptions=("receptions", "sum"), prior_season_targets_yards=("targets", "sum"))
    )
    season_stats["season"] = season_stats["season"] + 1
    season_stats["prior_season_ypr"] = _safe_divide(
        season_stats["prior_season_receiving_yards"], season_stats["prior_season_receptions"]
    )
    season_stats["prior_season_ypt"] = _safe_divide(
        season_stats["prior_season_receiving_yards"], season_stats["prior_season_targets_yards"]
    )
    df = df.merge(
        season_stats[["player_id", "season", "prior_season_ypr", "prior_season_ypt", "prior_season_receptions"]],
        on=["player_id", "season"],
        how="left",
    )

    pos_stats = (
        df[df["position"].astype(str).str.upper().isin(RECEIVING_POSITIONS)]
        .groupby("position", as_index=False)
        .agg(position_receiving_yards=("receiving_yards", "sum"), position_receptions=("receptions", "sum"), position_targets=("targets", "sum"))
    )
    pos_stats["position_avg_ypr"] = _safe_divide(pos_stats["position_receiving_yards"], pos_stats["position_receptions"])
    pos_stats["position_avg_ypt"] = _safe_divide(pos_stats["position_receiving_yards"], pos_stats["position_targets"])
    df = df.merge(pos_stats[["position", "position_avg_ypr", "position_avg_ypt"]], on="position", how="left")

    ypr_sources = ["recent_ypr_last_4", "prior_season_ypr", "career_ypr_entering", "position_avg_ypr"]
    for col in ypr_sources:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    pos_fallback = df["position_avg_ypr"].fillna(10.0)
    recent = df["recent_ypr_last_4"].fillna(pos_fallback)
    prior = df["prior_season_ypr"].fillna(pos_fallback)
    career = df["career_ypr_entering"].fillna(prior).fillna(pos_fallback)
    position = pos_fallback
    games = pd.to_numeric(df.get("current_season_games_entering", 0), errors="coerce").fillna(0)
    df["projected_yards_per_reception"] = np.select(
        [games >= 6, games >= 3],
        [recent * 0.55 + prior * 0.25 + career * 0.10 + position * 0.10, recent * 0.40 + prior * 0.35 + career * 0.10 + position * 0.15],
        default=prior * 0.45 + position * 0.35 + career * 0.20,
    )
    df["projected_yards_per_reception"] = pd.to_numeric(df["projected_yards_per_reception"], errors="coerce").fillna(10.0).clip(4, 22)
    sample = pd.to_numeric(df["career_receptions_entering"], errors="coerce").fillna(0)
    df["receiving_yards_sample_flag"] = np.where(sample < 10, "LOW_YARDAGE_SAMPLE", "")
    existing_flags = df.get("quality_flags", pd.Series("", index=df.index)).fillna("").astype(str)
    needs_flag = df["receiving_yards_sample_flag"].eq("LOW_YARDAGE_SAMPLE") & ~existing_flags.str.contains("LOW_YARDAGE_SAMPLE", regex=False)
    df.loc[needs_flag, "quality_flags"] = existing_flags.where(~needs_flag, existing_flags.where(existing_flags == "", existing_flags + "|") + "LOW_YARDAGE_SAMPLE")

    out = output_path("receiving_yards_feature_table.csv", cfg)
    df.to_csv(out, index=False)
    print(f"Built receiving yards feature table: {len(df):,} rows")
    return df


def main() -> None:
    build_receiving_yards_feature_table()


if __name__ == "__main__":
    main()
