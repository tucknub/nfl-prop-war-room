from __future__ import annotations

import numpy as np
import pandas as pd


def _first_existing(columns: list[str], candidates: list[str]) -> str | None:
    return next((col for col in candidates if col in columns), None)


def build_player_week_features(weekly: pd.DataFrame, min_games: int = 3, strong_games: int = 6) -> pd.DataFrame:
    df = weekly.copy()
    player_col = _first_existing(list(df.columns), ["player_id", "player_gsis_id", "gsis_id"])
    name_col = _first_existing(list(df.columns), ["player_name", "full_name", "name"])
    team_col = _first_existing(list(df.columns), ["recent_team", "team", "posteam"])
    if player_col is None or team_col is None:
        raise ValueError("Weekly data must include player and team columns.")

    df["player_id"] = df[player_col]
    df["player_name"] = df[name_col] if name_col else df["player_id"]
    df["team"] = df[team_col]
    df["position"] = df.get("position", "UNK").fillna("UNK")
    for col in ["targets", "receptions", "receiving_yards", "air_yards"]:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0).astype(float)

    df["player_week_targets"] = df["targets"]
    df["player_week_receptions"] = df["receptions"]
    df["player_week_catch_rate"] = np.where(df["targets"] > 0, df["receptions"] / df["targets"], np.nan)
    df["player_week_adot"] = np.where(df["targets"] > 0, df["air_yards"] / df["targets"], np.nan)
    team_targets = df.groupby(["season", "week", "team"], dropna=False)["targets"].transform("sum")
    df["player_week_target_share"] = np.where(team_targets > 0, df["targets"] / team_targets, np.nan)

    df = df.sort_values(["player_id", "season", "week"])
    g = df.groupby("player_id", dropna=False)
    df["current_season_games_entering"] = df.groupby(["player_id", "season"], dropna=False).cumcount()
    df["career_targets_entering"] = g["targets"].cumsum().groupby(df["player_id"], dropna=False).shift(1).fillna(0)
    for col in ["player_week_target_share", "player_week_catch_rate", "player_week_adot", "targets", "receptions"]:
        shifted = g[col].shift(1)
        df[f"{col}_last_4"] = (
            shifted.groupby(df["player_id"], dropna=False)
            .rolling(4, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )
        df[f"{col}_last_8"] = (
            shifted.groupby(df["player_id"], dropna=False)
            .rolling(8, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )

    prior = (
        df.groupby(["player_id", "season"], as_index=False)
        .agg(prior_targets=("targets", "sum"), prior_receptions=("receptions", "sum"))
    )
    prior["season"] += 1
    prior["prior_season_catch_rate"] = np.where(
        prior["prior_targets"] > 0, prior["prior_receptions"] / prior["prior_targets"], np.nan
    )
    df = df.merge(prior[["player_id", "season", "prior_targets", "prior_season_catch_rate"]], on=["player_id", "season"], how="left")
    df["sample_tier"] = np.select(
        [df["current_season_games_entering"] >= strong_games, df["current_season_games_entering"] >= min_games],
        ["CURRENT_STRONG", "CURRENT_BLEND"],
        default="PRIOR_HEAVY",
    )
    return df
