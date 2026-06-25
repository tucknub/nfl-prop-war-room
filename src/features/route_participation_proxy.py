from __future__ import annotations

import numpy as np
import pandas as pd


def build_route_proxy(player_features: pd.DataFrame, team_features: pd.DataFrame, config: dict) -> pd.DataFrame:
    df = player_features.merge(
        team_features[["season", "week", "team", "projected_team_pass_attempts"]],
        on=["season", "week", "team"],
        how="left",
    )
    proxy_cfg = config["features"]["route_proxy"]
    factors = {
        "WR": proxy_cfg["slot_wr_factor"],
        "TE": proxy_cfg["te_factor"],
        "RB": proxy_cfg["rb_factor"],
    }
    df["route_position_factor"] = df["position"].map(factors).fillna(proxy_cfg["other_factor"])
    share = df["player_week_target_share_last_4"].fillna(df["player_week_target_share_last_8"]).fillna(0.03)
    df["estimated_routes"] = (
        df["projected_team_pass_attempts"].fillna(32.0)
        * proxy_cfg["base_routes_per_team_attempt"]
        * df["route_position_factor"]
        * np.sqrt((share.clip(0.005, 0.45) / 0.10))
    ).clip(lower=0)
    df["route_proxy_status"] = "ROUTE_PROXY_UNVALIDATED"
    df = df.drop(columns=["projected_team_pass_attempts"])
    return df
