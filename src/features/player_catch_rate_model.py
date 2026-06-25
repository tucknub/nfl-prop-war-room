from __future__ import annotations

import numpy as np
import pandas as pd


def build_catch_rate_projection(player_features: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = player_features.copy()
    model_cfg = config["model"]
    feat_cfg = config["features"]
    pos_avg = (
        df.groupby(["season", "week", "position"], dropna=False)
        .apply(lambda x: x["player_week_receptions"].sum() / x["player_week_targets"].sum() if x["player_week_targets"].sum() else np.nan)
        .rename("position_avg_catch_rate")
        .reset_index()
    )
    pos_avg["week"] += 1
    df = df.merge(pos_avg, on=["season", "week", "position"], how="left")
    league_avg = df["player_week_catch_rate"].mean()
    df["position_avg_catch_rate"] = df["position_avg_catch_rate"].fillna(league_avg).fillna(0.65)

    recent = df["player_week_catch_rate_last_4"]
    prior = df["prior_season_catch_rate"]
    position = df["position_avg_catch_rate"]
    games = df["current_season_games_entering"].fillna(0)
    weights = np.select(
        [games >= 6, games >= 3],
        [0.60, 0.40],
        default=0.20,
    )
    prior_weight = np.select([games >= 6, games >= 3], [0.25, 0.35], default=0.50)
    pos_weight = 1 - weights - prior_weight
    df["base_catch_rate_blend"] = (
        recent.fillna(position) * weights
        + prior.fillna(position) * prior_weight
        + position * pos_weight
    )

    adot = df["player_week_adot_last_4"].fillna(df["player_week_adot_last_8"]).fillna(8.0).clip(0, 18)
    adot_adj = (adot - 8.0) * float(feat_cfg["adot_adjustment_per_yard"])
    qb_adj = df.get("qb_catch_rate_adjustment", 0)
    if not isinstance(qb_adj, pd.Series):
        qb_adj = pd.Series(qb_adj, index=df.index)
    qb_adj = qb_adj.fillna(0).clip(-feat_cfg["qb_adjustment_cap"], feat_cfg["qb_adjustment_cap"])

    raw = df["base_catch_rate_blend"] + adot_adj + qb_adj
    cap = float(feat_cfg["catch_rate_adjustment_cap"])
    lower = df["base_catch_rate_blend"] * (1 - cap)
    upper = df["base_catch_rate_blend"] * (1 + cap)
    df["projected_catch_rate"] = raw.clip(lower=lower, upper=upper)
    df["projected_catch_rate"] = df["projected_catch_rate"].clip(model_cfg["catch_rate_floor"], model_cfg["catch_rate_ceiling"])

    report = df[
        [
            "season",
            "week",
            "player_id",
            "player_name",
            "position",
            "base_catch_rate_blend",
            "projected_catch_rate",
            "sample_tier",
        ]
    ].copy()
    return df, report
