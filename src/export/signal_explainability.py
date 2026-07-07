from __future__ import annotations

import pandas as pd


SCORE_FAMILY_COLUMNS = [
    "projection_score",
    "usage_foundation_score",
    "recent_form_score",
    "opponent_fit_score",
    "game_script_score",
    "weather_score",
    "role_availability_score",
    "volatility_score",
    "data_quality_score",
]

DISPLAY_NAMES = {
    "projection_score": "projection strength",
    "usage_foundation_score": "usage foundation",
    "recent_form_score": "recent form",
    "opponent_fit_score": "opponent defense fit",
    "game_script_score": "game environment",
    "weather_score": "weather",
    "role_availability_score": "role and availability context",
    "volatility_score": "volatility profile",
    "data_quality_score": "data quality",
}


def _num(value: object) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else float(number)


def _driver_label(column: str, value: object) -> str:
    number = _num(value)
    label = DISPLAY_NAMES.get(column, column.replace("_", " "))
    return f"{label}: {number:.1f}" if number is not None else f"{label}: missing"


def market_family(row: pd.Series) -> str:
    families = []
    if str(row.get("receiving_market_available", "")).lower() == "true":
        families.append("receiving")
    if str(row.get("rushing_market_available", "")).lower() == "true":
        families.append("rushing")
    if str(row.get("passing_market_available", "")).lower() == "true":
        families.append("passing")
    return ", ".join(families) if families else "unknown"


def top_positive_drivers(row: pd.Series, limit: int = 3) -> list[str]:
    values = []
    for column in SCORE_FAMILY_COLUMNS:
        number = _num(row.get(column))
        if number is not None and number >= 60:
            values.append((number, _driver_label(column, number)))
    values.sort(reverse=True, key=lambda item: item[0])
    return [label for _, label in values[:limit]]


def top_negative_drivers(row: pd.Series, limit: int = 3) -> list[str]:
    values = []
    for column in SCORE_FAMILY_COLUMNS:
        number = _num(row.get(column))
        if number is not None and number <= 45:
            values.append((number, _driver_label(column, number)))
    values.sort(key=lambda item: item[0])
    negatives = [label for _, label in values[:limit]]
    red_flags = int(_num(row.get("red_flag_count")) or 0)
    missing = int(_num(row.get("missing_signal_count")) or 0)
    if red_flags > 0:
        negatives.append(f"red flags: {red_flags}")
    if missing > 0:
        negatives.append(f"missing signal count: {missing}")
    review = str(row.get("review_reason", "") or "").strip()
    blocked = str(row.get("blocked_reason", "") or "").strip()
    if blocked:
        negatives.append(f"blocked context: {blocked[:90]}")
    elif review:
        negatives.append(f"review context: {review[:90]}")
    return negatives[:limit]


def data_limitations(row: pd.Series) -> str:
    limitations = []
    if pd.isna(row.get("weather_score")):
        limitations.append("weather not sourced")
    if str(row.get("role_status", "")).upper() != "READY" or str(row.get("injury_status", "")).upper() != "READY":
        limitations.append("live role/injury gates not ready")
    if str(row.get("defense_fit_reliability", "")).upper() in {"LOW", "MISSING", "", "NAN"}:
        limitations.append("defense fit limited")
    if str(row.get("recent_form_reliability", "")).upper() in {"LOW", "MISSING", "", "NAN"}:
        limitations.append("recent form limited")
    if str(row.get("game_environment_reliability", "")).upper() in {"LOW", "MISSING", "", "NAN"}:
        limitations.append("game environment limited")
    return "; ".join(dict.fromkeys(limitations)) if limitations else "context fields available for V1"


def recommended_action(row: pd.Series) -> str:
    tier = str(row.get("signal_tier", "")).upper()
    red_flags = int(_num(row.get("red_flag_count")) or 0)
    missing = int(_num(row.get("missing_signal_count")) or 0)
    if tier == "BLOCKED" or str(row.get("blocked_reason", "") or "").strip():
        return "BLOCKED_DATA"
    if red_flags > 0:
        return "REVIEW_CONTEXT"
    if tier in {"ELITE_SIGNAL", "STRONG_SIGNAL"}:
        return "STRONG_SIGNAL"
    if tier == "GOOD_SIGNAL":
        return "GOOD_SIGNAL"
    if tier == "WATCH":
        return "WATCHLIST"
    if missing >= 5 or tier in {"REVIEW", "INSUFFICIENT_DATA"}:
        return "PRIORITY_REVIEW"
    return "LOW_PRIORITY"


def plain_english_summary(row: pd.Series) -> str:
    positives = top_positive_drivers(row, 2)
    negatives = top_negative_drivers(row, 2)
    tier = str(row.get("signal_tier", "UNKNOWN"))
    score = _num(row.get("overall_signal_score"))
    score_text = f"{score:.1f}" if score is not None else "missing"
    pos_text = "; ".join(positives) if positives else "no strong positive score family"
    neg_text = "; ".join(negatives) if negatives else "no major negative driver"
    return f"{tier} at {score_text}. Main support: {pos_text}. Main caution: {neg_text}."


def why_green(row: pd.Series) -> str:
    if str(row.get("signal_tier", "")).upper() not in {"ELITE_SIGNAL", "STRONG_SIGNAL", "GOOD_SIGNAL"}:
        return ""
    drivers = top_positive_drivers(row, 3)
    return "; ".join(drivers) if drivers else "positive tier from available composite score"


def why_yellow_or_review(row: pd.Series) -> str:
    tier = str(row.get("signal_tier", "")).upper()
    if tier not in {"WATCH", "REVIEW", "INSUFFICIENT_DATA"}:
        return ""
    return "; ".join(top_negative_drivers(row, 3)) or str(row.get("review_reason", "") or "")


def why_red_or_blocked(row: pd.Series) -> str:
    tier = str(row.get("signal_tier", "")).upper()
    blocked = str(row.get("blocked_reason", "") or "").strip()
    if tier != "BLOCKED" and not blocked:
        return ""
    return blocked or "; ".join(top_negative_drivers(row, 3))


def explanation_fields(row: pd.Series) -> dict[str, str]:
    positives = top_positive_drivers(row, 3)
    negatives = top_negative_drivers(row, 3)
    limitations = data_limitations(row)
    action = recommended_action(row)
    return {
        "market_family": market_family(row),
        "plain_english_summary": plain_english_summary(row),
        "why_green": why_green(row),
        "why_yellow_or_review": why_yellow_or_review(row),
        "why_red_or_blocked": why_red_or_blocked(row),
        "data_limitations": limitations,
        "recommended_user_action": action,
        "signal_explanation": plain_english_summary(row),
        "top_signal_reason": "; ".join(positives[:2]) if positives else str(row.get("top_signal_reason", "") or "available signal context is limited"),
        "review_reason": str(row.get("review_reason", "") or limitations),
        "blocked_reason": str(row.get("blocked_reason", "") or ""),
        "top_positive_driver_1": positives[0] if len(positives) > 0 else "",
        "top_positive_driver_2": positives[1] if len(positives) > 1 else "",
        "top_positive_driver_3": positives[2] if len(positives) > 2 else "",
        "top_negative_driver_1": negatives[0] if len(negatives) > 0 else "",
        "top_negative_driver_2": negatives[1] if len(negatives) > 1 else "",
        "top_negative_driver_3": negatives[2] if len(negatives) > 2 else "",
        "driver_notes": f"Research-only driver summary. Limitations: {limitations}",
    }


def add_explainability_columns(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    rows = frame.apply(explanation_fields, axis=1, result_type="expand")
    result = frame.copy()
    for column in rows.columns:
        result[column] = rows[column]
    return result
