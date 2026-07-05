from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.features.build_rushing_yards_feature_table import RUSHING_POSITIONS, build_rushing_yards_feature_table


def build_carries_feature_table(config: dict | None = None) -> pd.DataFrame:
    cfg = config or load_config()
    path = output_path("rushing_yards_feature_table.csv", cfg)
    base = pd.read_csv(path, low_memory=False) if path.exists() else build_rushing_yards_feature_table(cfg)
    df = base.copy()
    pos = df["position"].fillna("").astype(str).str.upper()
    history = pd.to_numeric(df.get("career_carries_entering", 0), errors="coerce").fillna(0)
    prior = pd.to_numeric(df.get("prior_carries", 0), errors="coerce").fillna(0)
    eligible = pos.isin(RUSHING_POSITIONS) & ((history > 0) | (prior > 0))
    baseline = pd.to_numeric(df.get("projected_carries", 0), errors="coerce").fillna(0).clip(lower=0)
    df["rush_volume_baseline"] = np.where(eligible, baseline, 0.0)
    denominator = df.groupby(["season", "week", "team"])["rush_volume_baseline"].transform("sum").replace(0, np.nan)
    df["projected_player_rush_attempt_share"] = (df["rush_volume_baseline"] / denominator).fillna(0).clip(0, 1)
    low = history < 20
    existing = df.get("quality_flags", pd.Series("", index=df.index)).fillna("").astype(str)
    needs = eligible & low & ~existing.str.contains("LOW_CARRY_SAMPLE", regex=False)
    df.loc[needs, "quality_flags"] = existing.loc[needs].where(existing.loc[needs] == "", existing.loc[needs] + "|") + "LOW_CARRY_SAMPLE"
    df["carries_sample_flag"] = np.where(eligible & low, "LOW_CARRY_SAMPLE", "")
    df.to_csv(output_path("carries_feature_table.csv", cfg), index=False)
    print(f"Built carries feature table: {len(df):,} rows")
    return df


def main() -> None:
    build_carries_feature_table()


if __name__ == "__main__":
    main()
