from __future__ import annotations

import pandas as pd


def score_percentile_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().sum() <= 1:
        return pd.Series([pd.NA] * len(series), index=series.index)
    return (numeric.rank(pct=True) * 100).round(2)


def score_recent_form(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    available = [column for column in columns if column in frame.columns]
    if not available:
        return pd.Series([pd.NA] * len(frame), index=frame.index)
    scores = [score_percentile_series(frame[column]) for column in available]
    return pd.to_numeric(pd.concat(scores, axis=1).max(axis=1), errors="coerce").round(2)


def score_game_script(frame: pd.DataFrame) -> pd.Series:
    if "total_line" not in frame.columns or "spread_line" not in frame.columns:
        return pd.Series([pd.NA] * len(frame), index=frame.index)
    total = pd.to_numeric(frame["total_line"], errors="coerce")
    spread = pd.to_numeric(frame["spread_line"], errors="coerce").abs()
    score = 50 + (total - 43).clip(-8, 10) * 2 - spread.clip(0, 10)
    return score.clip(lower=20, upper=85).round(2)


def score_opponent_fit(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    available = [column for column in columns if column in frame.columns]
    if not available:
        return pd.Series([pd.NA] * len(frame), index=frame.index)
    scores = [score_percentile_series(frame[column]) for column in available]
    return pd.to_numeric(pd.concat(scores, axis=1).max(axis=1), errors="coerce").round(2)


def score_data_quality(frame: pd.DataFrame) -> pd.Series:
    missing = pd.to_numeric(frame.get("missing_signal_count", pd.Series([0] * len(frame), index=frame.index)), errors="coerce").fillna(0)
    return (100 - missing * 8).clip(lower=20, upper=95).round(2)


def count_signal_colors(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["green_signal_count"] = (
        (pd.to_numeric(result.get("projection_score"), errors="coerce") >= 75).astype(int)
        + (pd.to_numeric(result.get("usage_foundation_score"), errors="coerce") >= 60).astype(int)
        + (pd.to_numeric(result.get("recent_form_score"), errors="coerce") >= 65).astype(int)
        + (pd.to_numeric(result.get("opponent_fit_score"), errors="coerce") >= 65).astype(int)
    )
    result["red_flag_count"] = (
        (pd.to_numeric(result.get("data_quality_score"), errors="coerce") < 45).astype(int)
        + (pd.to_numeric(result.get("projection_score"), errors="coerce") < 35).astype(int)
    )
    return result


def assign_signal_tier(row: pd.Series) -> str:
    red_flags = int(pd.to_numeric(row.get("red_flag_count", 0), errors="coerce") or 0)
    score = pd.to_numeric(row.get("overall_signal_score"), errors="coerce")
    if red_flags > 0:
        return "REVIEW"
    if pd.isna(score):
        return "INSUFFICIENT_DATA"
    if score >= 85:
        return "ELITE_SIGNAL"
    if score >= 72:
        return "STRONG_SIGNAL"
    if score >= 58:
        return "GOOD_SIGNAL"
    if score >= 40:
        return "WATCH"
    return "REVIEW"
