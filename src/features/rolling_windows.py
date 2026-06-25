from __future__ import annotations

import pandas as pd


def add_shifted_rolling_mean(
    df: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
    windows: list[int],
    min_periods: int = 1,
) -> pd.DataFrame:
    out = df.copy()
    out = out.sort_values(group_cols + ["season", "week"])
    shifted = out.groupby(group_cols, dropna=False)[value_col].shift(1)
    for window in windows:
        out[f"{value_col}_last_{window}"] = (
            shifted.groupby([out[col] for col in group_cols], dropna=False)
            .rolling(window, min_periods=min_periods)
            .mean()
            .reset_index(level=group_cols, drop=True)
        )
    return out


def available_games_before_week(df: pd.DataFrame, group_cols: list[str]) -> pd.Series:
    ordered = df.sort_values(group_cols + ["season", "week"])
    return ordered.groupby(group_cols, dropna=False).cumcount()
