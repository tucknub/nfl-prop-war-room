from __future__ import annotations

import numpy as np
import pandas as pd


def _series(df: pd.DataFrame, name: str, default: object) -> pd.Series:
    if name in df.columns:
        return df[name]
    return pd.Series(default, index=df.index)


def classify_play_context(
    plays: pd.DataFrame,
    q3_threshold: int = 24,
    q4_threshold: int = 17,
) -> pd.DataFrame:
    """Add transparent play-context flags to nflverse-like play-by-play data.

    The function does not invent late-backup or injury status. Those flags are
    honored only when supplied by a trustworthy upstream source.
    """
    result = plays.copy()

    qtr = pd.to_numeric(_series(result, "qtr", 0), errors="coerce").fillna(0)
    score_diff = pd.to_numeric(
        _series(result, "score_differential", 0), errors="coerce"
    ).fillna(0)
    abs_diff = score_diff.abs()

    qb_kneel = _series(result, "qb_kneel", 0).fillna(0).astype(bool)
    qb_spike = _series(result, "qb_spike", 0).fillna(0).astype(bool)
    late_backup = _series(result, "late_backup_flag", False).fillna(False).astype(bool)

    half_seconds = pd.to_numeric(
        _series(result, "half_seconds_remaining", np.nan), errors="coerce"
    )
    two_minute = half_seconds.le(120) & qtr.le(4)

    overtime = qtr.gt(4)
    garbage = ((qtr.eq(3)) & abs_diff.ge(q3_threshold)) | (
        qtr.eq(4) & abs_diff.ge(q4_threshold)
    )
    kneel_or_spike = qb_kneel | qb_spike

    result["context_overtime"] = overtime
    result["context_garbage_time"] = garbage
    result["context_two_minute"] = two_minute
    result["context_kneel_or_spike"] = kneel_or_spike
    result["context_late_backup"] = late_backup
    result["context_normal_game"] = ~(
        overtime | garbage | kneel_or_spike | late_backup
    )

    labels = np.select(
        [
            overtime,
            kneel_or_spike,
            late_backup,
            garbage,
            two_minute,
        ],
        [
            "overtime",
            "kneel_or_spike",
            "late_backup",
            "garbage_time",
            "two_minute_competitive",
        ],
        default="normal",
    )
    result["play_context"] = labels
    return result
