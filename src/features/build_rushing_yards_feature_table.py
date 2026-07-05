from __future__ import annotations

import numpy as np
import pandas as pd

from src.common import load_config, output_path
from src.features.build_receptions_feature_table import build_receptions_feature_table


RUSHING_POSITIONS = {"RB", "QB", "WR"}


def _divide(a: pd.Series, b: pd.Series) -> pd.Series:
    return pd.to_numeric(a, errors="coerce") / pd.to_numeric(b, errors="coerce").replace(0, np.nan)


def build_rushing_yards_feature_table(config: dict | None = None) -> pd.DataFrame:
    cfg = config or load_config()
    source = output_path("receptions_feature_table.csv", cfg)
    base = pd.read_csv(source, low_memory=False) if source.exists() else build_receptions_feature_table(cfg)
    df = base.copy().sort_values(["player_id", "season", "week"])
    for col in ["carries", "rushing_yards", "rushing_tds"]:
        df[col] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)

    player = df.groupby("player_id", group_keys=False)
    df["career_carries_entering"] = player["carries"].cumsum() - df["carries"]
    df["career_rushing_yards_entering"] = player["rushing_yards"].cumsum() - df["rushing_yards"]
    df["career_games_entering_rush"] = player.cumcount()
    df["career_ypc_entering"] = _divide(df["career_rushing_yards_entering"], df["career_carries_entering"])
    df["career_carries_per_game_entering"] = _divide(df["career_carries_entering"], df["career_games_entering_rush"])
    df["carries_last_4"] = player["carries"].transform(lambda s: s.shift(1).rolling(4, min_periods=1).sum())
    df["rushing_yards_last_4"] = player["rushing_yards"].transform(lambda s: s.shift(1).rolling(4, min_periods=1).sum())
    df["rush_games_last_4"] = player["carries"].transform(lambda s: s.shift(1).rolling(4, min_periods=1).count())
    df["recent_carries_per_game"] = _divide(df["carries_last_4"], df["rush_games_last_4"])
    df["recent_ypc_last_4"] = _divide(df["rushing_yards_last_4"], df["carries_last_4"])

    prior = df.groupby(["player_id", "season"], as_index=False).agg(
        prior_rushing_yards=("rushing_yards", "sum"),
        prior_carries=("carries", "sum"),
        prior_rush_games=("week", "size"),
    )
    prior["season"] += 1
    prior["prior_season_ypc"] = _divide(prior["prior_rushing_yards"], prior["prior_carries"])
    prior["prior_season_carries_per_game"] = _divide(prior["prior_carries"], prior["prior_rush_games"])
    df = df.merge(
        prior[["player_id", "season", "prior_carries", "prior_season_ypc", "prior_season_carries_per_game"]],
        on=["player_id", "season"], how="left",
    )

    eligible_history = df[df["position"].fillna("").astype(str).str.upper().isin(RUSHING_POSITIONS)]
    pos = eligible_history.groupby("position", as_index=False).agg(
        position_rushing_yards=("rushing_yards", "sum"), position_carries=("carries", "sum"), position_games=("week", "size")
    )
    pos["position_avg_ypc"] = _divide(pos["position_rushing_yards"], pos["position_carries"])
    pos["position_avg_carries_per_game"] = _divide(pos["position_carries"], pos["position_games"])
    df = df.merge(pos[["position", "position_avg_ypc", "position_avg_carries_per_game"]], on="position", how="left")

    games = pd.to_numeric(df.get("current_season_games_entering", 0), errors="coerce").fillna(0)
    pos_cpg = df["position_avg_carries_per_game"].fillna(1.0)
    recent_cpg = df["recent_carries_per_game"].fillna(pos_cpg)
    prior_cpg = df["prior_season_carries_per_game"].fillna(pos_cpg)
    career_cpg = df["career_carries_per_game_entering"].fillna(prior_cpg).fillna(pos_cpg)
    df["projected_carries"] = np.select(
        [games >= 6, games >= 3],
        [recent_cpg * .55 + prior_cpg * .25 + career_cpg * .15 + pos_cpg * .05,
         recent_cpg * .40 + prior_cpg * .35 + career_cpg * .15 + pos_cpg * .10],
        default=prior_cpg * .50 + career_cpg * .25 + pos_cpg * .25,
    )
    df["projected_carries"] = pd.to_numeric(df["projected_carries"], errors="coerce").fillna(0).clip(0, 30)

    pos_ypc = df["position_avg_ypc"].fillna(4.2)
    recent_ypc = df["recent_ypc_last_4"].fillna(pos_ypc)
    prior_ypc = df["prior_season_ypc"].fillna(pos_ypc)
    career_ypc = df["career_ypc_entering"].fillna(prior_ypc).fillna(pos_ypc)
    df["projected_yards_per_carry"] = np.select(
        [games >= 6, games >= 3],
        [recent_ypc * .45 + prior_ypc * .25 + career_ypc * .20 + pos_ypc * .10,
         recent_ypc * .30 + prior_ypc * .35 + career_ypc * .20 + pos_ypc * .15],
        default=prior_ypc * .40 + career_ypc * .25 + pos_ypc * .35,
    )
    df["projected_yards_per_carry"] = pd.to_numeric(df["projected_yards_per_carry"], errors="coerce").fillna(4.2).clip(1.5, 8.0)
    low = df["career_carries_entering"].fillna(0) < 20
    existing = df.get("quality_flags", pd.Series("", index=df.index)).fillna("").astype(str)
    needs = low & ~existing.str.contains("LOW_RUSH_SAMPLE", regex=False)
    df.loc[needs, "quality_flags"] = existing.loc[needs].where(existing.loc[needs] == "", existing.loc[needs] + "|") + "LOW_RUSH_SAMPLE"
    df["rushing_yards_sample_flag"] = np.where(low, "LOW_RUSH_SAMPLE", "")
    df.to_csv(output_path("rushing_yards_feature_table.csv", cfg), index=False)
    print(f"Built rushing yards feature table: {len(df):,} rows")
    return df


def main() -> None:
    build_rushing_yards_feature_table()


if __name__ == "__main__":
    main()
