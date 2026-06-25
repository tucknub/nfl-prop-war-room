from __future__ import annotations

import numpy as np
import pandas as pd


def _team_offense_from_pbp(pbp: pd.DataFrame) -> pd.DataFrame:
    df = pbp.copy()
    if "posteam" not in df.columns:
        raise ValueError("PBP data must include posteam.")
    df = df[df["posteam"].notna()].copy()
    df["is_pass"] = df.get("pass_attempt", 0).fillna(0).astype(float)
    df["is_rush"] = df.get("rush_attempt", 0).fillna(0).astype(float)
    df["is_play"] = np.where((df["is_pass"] + df["is_rush"]) > 0, 1.0, 0.0)
    df["is_td"] = df.get("touchdown", 0).fillna(0).astype(float)
    return (
        df.groupby(["season", "week", "posteam"], as_index=False)
        .agg(
            team_plays=("is_play", "sum"),
            team_pass_attempts=("is_pass", "sum"),
            team_rush_attempts=("is_rush", "sum"),
            team_tds=("is_td", "sum"),
        )
        .rename(columns={"posteam": "team"})
    )


def build_team_week_features(pbp: pd.DataFrame, recent_window: int = 4) -> pd.DataFrame:
    team_week = _team_offense_from_pbp(pbp).sort_values(["team", "season", "week"])
    group = team_week.groupby("team", dropna=False)
    for col in ["team_plays", "team_pass_attempts", "team_rush_attempts", "team_tds"]:
        shifted = group[col].shift(1)
        team_week[f"projected_{col}"] = (
            shifted.groupby(team_week["team"], dropna=False)
            .rolling(recent_window, min_periods=1)
            .mean()
            .reset_index(level=0, drop=True)
        )
        fallback = {
            "team_plays": 62.0,
            "team_pass_attempts": 34.0,
            "team_rush_attempts": 27.0,
            "team_tds": 2.4,
        }[col]
        team_week[f"projected_{col}"] = team_week[f"projected_{col}"].fillna(fallback)

    total_attempts = team_week["projected_team_pass_attempts"] + team_week["projected_team_rush_attempts"]
    team_week["projected_pass_rate"] = (team_week["projected_team_pass_attempts"] / total_attempts).fillna(0.58)
    team_week["projected_rush_rate"] = (team_week["projected_team_rush_attempts"] / total_attempts).fillna(0.42)
    team_week["projected_team_tds_placeholder"] = team_week["projected_team_tds"].fillna(0.0)
    return team_week
