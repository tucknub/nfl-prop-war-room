from __future__ import annotations

from collections import deque

import numpy as np
import pandas as pd


SORT_COLUMNS = ["player_id", "role_family", "season", "week", "team"]
FEATURE_COLUMNS = [
    "baseline_n", "baseline_value", "previous_metric", "two_game_value",
    "naive_score", "two_week_score", "full_score", "method_eligible",
    "detector_eligible", "current_metric",
]


def _prior_qualifying_features(
    frame: pd.DataFrame,
    metric: pd.Series,
    eligible: pd.Series,
    baseline_window: int,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Use the last N qualifying games, not the last N physical rows."""
    baseline_n = pd.Series(0, index=frame.index, dtype="int64")
    baseline_value = pd.Series(np.nan, index=frame.index, dtype="float64")
    previous_metric = pd.Series(np.nan, index=frame.index, dtype="float64")
    for _, indices in frame.groupby(["player_id", "role_family"], sort=False).groups.items():
        history: deque[float] = deque(maxlen=baseline_window)
        for index in indices:
            if history:
                baseline_n.at[index] = len(history)
                baseline_value.at[index] = float(np.mean(history))
                previous_metric.at[index] = history[-1]
            value = metric.at[index]
            if bool(eligible.at[index]) and pd.notna(value):
                history.append(float(value))
    return baseline_n, baseline_value, previous_metric


def add_detection_features(
    frame: pd.DataFrame,
    metric_column: str,
    baseline_window: int = 4,
    min_baseline_games: int = 3,
) -> pd.DataFrame:
    """Calculate causal baselines and detector features from prior qualifying games."""
    df = frame.sort_values(SORT_COLUMNS).copy().reset_index(drop=True)
    eligible = (
        df["qualifying_game"].fillna(False).astype(bool)
        & ~df["partial_game_flag"].fillna(True).astype(bool)
        & df["data_quality_pass"].fillna(False).astype(bool)
    )
    metric = pd.to_numeric(df[metric_column], errors="coerce")
    baseline_n, baseline_value, previous_metric = _prior_qualifying_features(
        df, metric, eligible, baseline_window
    )
    df["current_metric"] = metric
    df["baseline_n"] = baseline_n
    df["baseline_value"] = baseline_value
    df["previous_metric"] = previous_metric
    df["two_game_value"] = (metric + previous_metric) / 2
    df["naive_score"] = metric - baseline_value
    df["two_week_score"] = df["two_game_value"] - baseline_value

    same_direction = np.sign(df["naive_score"]) == np.sign(df["two_week_score"])
    concentration = (
        df["naive_score"].abs() / (df["two_week_score"].abs() + 1e-9)
    ).clip(lower=0, upper=3)
    sample_weight = (df["baseline_n"] / max(baseline_window, 1)).clip(0, 1) ** 0.5
    concentration_penalty = np.where(concentration > 2.0, 0.65, 1.0)
    df["full_score"] = df["two_week_score"] * sample_weight * concentration_penalty
    df["method_eligible"] = (
        eligible & metric.notna() & df["baseline_n"].ge(min_baseline_games)
    )
    df["detector_eligible"] = (
        df["method_eligible"] & df["two_game_value"].notna() & same_direction
    )
    return df


def add_comparison_features(
    frame: pd.DataFrame,
    baseline_window: int = 4,
    min_baseline_games: int = 3,
) -> pd.DataFrame:
    """Create distinct all-game and normal-game method inputs."""
    raw = add_detection_features(frame, "metric_all", baseline_window, min_baseline_games)
    normal = add_detection_features(frame, "metric_normal", baseline_window, min_baseline_games)
    result = raw.drop(columns=FEATURE_COLUMNS)
    for prefix, featured in [("raw", raw), ("normal", normal)]:
        for column in FEATURE_COLUMNS:
            result[f"{prefix}_{column}"] = featured[column].to_numpy()
    return result


def select_equal_volume_alerts(
    scored: pd.DataFrame,
    family: str,
    min_abs_delta: float,
    method_score_columns: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Select exactly N alerts per method within every family-week.

    N is the number of full-detector candidates. Baselines rank the same eligible
    family-week population, but use their own all-game or normal-game score.
    """
    if "raw_naive_score" not in scored.columns:
        # Backward-compatible smoke-test path for callers using one metric.
        method_score_columns = method_score_columns or {
            "naive_spike": "naive_score",
            "two_week_raw": "two_week_score",
            "full_propwar": "full_score",
        }
        family_df = scored.loc[scored["role_family"].eq(family)].copy()
        output = []
        for (_, _), week_df in family_df.groupby(["season", "week"], sort=True):
            propwar = week_df.loc[
                week_df["detector_eligible"] & week_df["two_week_score"].abs().ge(min_abs_delta)
            ]
            n_alerts = len(propwar)
            if not n_alerts:
                continue
            for method, score_col in method_score_columns.items():
                candidates = week_df.loc[week_df["method_eligible"] & week_df[score_col].notna()].copy()
                candidates["method"] = method
                candidates["method_score"] = candidates[score_col]
                candidates["detected_value"] = (
                    candidates["current_metric"] if method == "naive_spike" else candidates["two_game_value"]
                )
                candidates["detected_delta"] = candidates["detected_value"] - candidates["baseline_value"]
                candidates["_abs_score"] = candidates[score_col].abs()
                output.append(candidates.nlargest(n_alerts, "_abs_score").drop(columns="_abs_score"))
        return pd.concat(output, ignore_index=True) if output else pd.DataFrame()

    methods = {
        "naive_spike": {
            "score": "raw_naive_score", "detected": "raw_current_metric",
            "baseline": "raw_baseline_value", "eligible": "raw_method_eligible",
        },
        "two_week_raw": {
            "score": "raw_two_week_score", "detected": "raw_two_game_value",
            "baseline": "raw_baseline_value", "eligible": "raw_method_eligible",
        },
        "normal_game_trend": {
            "score": "normal_two_week_score", "detected": "normal_two_game_value",
            "baseline": "normal_baseline_value", "eligible": "normal_method_eligible",
        },
        "full_propwar": {
            "score": "normal_full_score", "detected": "normal_two_game_value",
            "baseline": "normal_baseline_value", "eligible": "normal_detector_eligible",
        },
    }
    family_df = scored.loc[scored["role_family"].eq(family)].copy()
    propwar_mask = (
        family_df["normal_detector_eligible"].fillna(False)
        & family_df["normal_two_week_score"].abs().ge(min_abs_delta)
    )
    propwar = family_df.loc[propwar_mask].copy()
    if propwar.empty:
        return pd.DataFrame()
    weekly_n = (
        propwar.groupby(["season", "week"]).size().rename("_n_alerts").reset_index()
    )
    output: list[pd.DataFrame] = []
    for method, spec in methods.items():
        if method == "full_propwar":
            selected = propwar.copy()
        else:
            candidates = family_df.loc[
                family_df[spec["eligible"]].fillna(False)
                & family_df[spec["score"]].notna()
            ].copy()
            candidates["_abs_score"] = candidates[spec["score"]].abs()
            candidates = candidates.sort_values(
                ["season", "week", "_abs_score", "player_id", "team"],
                ascending=[True, True, False, True, True],
            )
            candidates["_rank"] = candidates.groupby(["season", "week"]).cumcount() + 1
            candidates = candidates.merge(weekly_n, on=["season", "week"], how="inner")
            selected = candidates.loc[candidates["_rank"].le(candidates["_n_alerts"])].copy()
            if not selected.groupby(["season", "week"]).size().eq(
                weekly_n.set_index(["season", "week"])["_n_alerts"]
            ).all():
                raise RuntimeError(f"Equal-volume selection impossible for {family} {method}.")
            selected = selected.drop(columns=["_abs_score", "_rank", "_n_alerts"])
        selected["method"] = method
        selected["method_score"] = selected[spec["score"]]
        selected["baseline_value"] = selected[spec["baseline"]]
        selected["detected_value"] = selected[spec["detected"]]
        selected["detected_delta"] = selected["detected_value"] - selected["baseline_value"]
        selected["candidate_min_abs_delta"] = min_abs_delta
        output.append(selected)
    return pd.concat(output, ignore_index=True) if output else pd.DataFrame()


def verify_equal_volume(alerts: pd.DataFrame) -> pd.DataFrame:
    if alerts.empty:
        return pd.DataFrame(columns=["role_family", "season", "week", "min_count", "max_count", "equal_volume"])
    counts = alerts.groupby(["role_family", "season", "week", "method"]).size().rename("alerts").reset_index()
    check = counts.groupby(["role_family", "season", "week"])["alerts"].agg(min_count="min", max_count="max").reset_index()
    check["equal_volume"] = check["min_count"].eq(check["max_count"])
    return check
