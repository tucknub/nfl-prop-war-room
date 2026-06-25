from __future__ import annotations

import pandas as pd


def add_opponent_adjustments(features: pd.DataFrame) -> pd.DataFrame:
    df = features.copy()
    df["opponent_receptions_allowed_adjustment"] = 0.0
    df["opponent_adjustment_status"] = "PLACEHOLDER_NEUTRAL_V1"
    return df
