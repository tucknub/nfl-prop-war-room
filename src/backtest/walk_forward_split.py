from __future__ import annotations

import pandas as pd


def walk_forward_weeks(features: pd.DataFrame, season: int | None = None):
    df = features.copy()
    if season is not None:
        df = df[df["season"] == season]
    for week in sorted(df["week"].dropna().unique()):
        train = features[(features["season"] < df["season"].max()) | ((features["season"] == df["season"].max()) & (features["week"] < week))]
        test = df[df["week"] == week]
        if not test.empty:
            yield int(week), train.copy(), test.copy()
