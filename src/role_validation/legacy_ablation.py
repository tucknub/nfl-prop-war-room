from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np
import pandas as pd

from role_validation.evaluation import attach_future_outcomes, build_future_outcome_lookup
from role_validation.redevelopment import EXPECTED_METHODS, ROLE_FAMILIES, partial_exclusion_mask


LEGACY_SORT = ["player_id", "role_family", "season", "week", "team"]


def legacy_ablation_specs() -> list[dict[str, Any]]:
    """Every safeguard represented by the checkpoint full detector."""
    return [
        {"name": "original_full_detector", "safeguard": "none", "change": "checkpoint logic"},
        {"name": "no_normal_game_filter", "safeguard": "normal_game_filter", "use_normal_metric": False},
        {"name": "min_one_baseline_game", "safeguard": "minimum_baseline_sample", "minimum_baseline_override": 1},
        {"name": "no_two_game_persistence", "safeguard": "two_game_persistence", "use_two_game": False},
        {"name": "no_direction_consistency", "safeguard": "direction_consistency", "require_same_direction": False},
        {"name": "no_sample_weight", "safeguard": "sample_weight", "use_sample_weight": False},
        {"name": "no_concentration_penalty", "safeguard": "concentration_penalty", "use_concentration_penalty": False},
        {
            "name": "no_score_weights",
            "safeguard": "sample_and_concentration_weights",
            "use_sample_weight": False,
            "use_concentration_penalty": False,
        },
        {"name": "no_minimum_absolute_delta", "safeguard": "minimum_absolute_delta", "require_min_delta": False},
        {"name": "no_data_quality_gate_only", "safeguard": "data_quality_pass", "require_data_quality": False},
        {"name": "no_qualifying_gate_only", "safeguard": "qualifying_game", "require_qualifying": False},
        {
            "name": "no_current_quality_or_qualifying",
            "safeguard": "combined_current_quality",
            "require_data_quality": False,
            "require_qualifying": False,
        },
        {"name": "no_partial_game_exclusion", "safeguard": "partial_game_exclusion", "exclude_legacy_partial": False},
        {"name": "no_history_quality_filter", "safeguard": "history_quality", "history_unfiltered": True},
        {"name": "no_identity_component", "safeguard": "identity_resolution", "component_quality": "without_identity"},
        {"name": "no_partition_component", "safeguard": "game_partition", "component_quality": "without_partition"},
        {"name": "no_denominator_component", "safeguard": "team_denominator", "component_quality": "without_denominator"},
        {"name": "no_late_backup_exclusion", "safeguard": "late_backup_exclusion", "exclude_late_backup": False},
    ]


def _bool(frame: pd.DataFrame, column: str, default: bool) -> pd.Series:
    if column not in frame:
        return pd.Series(default, index=frame.index, dtype=bool)
    return frame[column].fillna(default).astype(bool)


def _component_quality(frame: pd.DataFrame, mode: str) -> pd.Series:
    identity = _bool(frame, "identity_resolved", False)
    partition = _bool(frame, "game_partition_complete", False)
    all_denominator = pd.to_numeric(frame["team_opportunities_all"], errors="coerce").gt(0)
    normal_denominator = pd.to_numeric(frame["team_opportunities_normal"], errors="coerce").gt(0)
    valid_shares = (
        pd.to_numeric(frame["metric_all"], errors="coerce").between(0, 1)
        & pd.to_numeric(frame["metric_normal"], errors="coerce").between(0, 1)
    )
    if mode == "without_identity":
        identity = pd.Series(True, index=frame.index)
    elif mode == "without_partition":
        partition = pd.Series(True, index=frame.index)
    elif mode == "without_denominator":
        all_denominator = pd.Series(True, index=frame.index)
        normal_denominator = pd.Series(True, index=frame.index)
    return identity & partition & all_denominator & normal_denominator & valid_shares


def _eligibility(
    frame: pd.DataFrame,
    metric_column: str,
    spec: dict[str, Any],
    *,
    for_history: bool,
) -> pd.Series:
    metric_present = pd.to_numeric(frame[metric_column], errors="coerce").notna()
    if for_history and spec.get("history_unfiltered", False):
        return metric_present
    if spec.get("component_quality"):
        quality = _component_quality(frame, str(spec["component_quality"]))
        qualifying = quality
    else:
        quality = (
            _bool(frame, "data_quality_pass", False)
            if spec.get("require_data_quality", True)
            else pd.Series(True, index=frame.index)
        )
        qualifying = (
            _bool(frame, "qualifying_game", False)
            if spec.get("require_qualifying", True)
            else pd.Series(True, index=frame.index)
        )
    partial = (
        _bool(frame, "partial_game_flag", True)
        if spec.get("exclude_legacy_partial", True)
        else pd.Series(False, index=frame.index)
    )
    late_backup = (
        _bool(frame, "late_backup_flag", False)
        if spec.get("exclude_late_backup", True)
        and _bool(frame, "late_backup_flag_reliable", False).any()
        else pd.Series(False, index=frame.index)
    )
    return metric_present & quality & qualifying & ~partial & ~late_backup


def _legacy_features(
    frame: pd.DataFrame,
    *,
    metric_column: str,
    baseline_window: int,
    minimum_baseline: int,
    spec: dict[str, Any],
) -> pd.DataFrame:
    df = frame.sort_values(LEGACY_SORT).copy().reset_index(drop=True)
    metric = pd.to_numeric(df[metric_column], errors="coerce")
    current_eligible = _eligibility(df, metric_column, spec, for_history=False)
    history_eligible = _eligibility(df, metric_column, spec, for_history=True)
    baseline_n = np.zeros(len(df), dtype=int)
    baseline_value = np.full(len(df), np.nan)
    previous_metric = np.full(len(df), np.nan)
    for _, indices in df.groupby(["player_id", "role_family"], sort=False).groups.items():
        history: deque[float] = deque(maxlen=baseline_window)
        for index_value in indices:
            index = int(index_value)
            if history:
                baseline_n[index] = len(history)
                baseline_value[index] = float(np.mean(history))
                previous_metric[index] = history[-1]
            if bool(history_eligible.iat[index]) and pd.notna(metric.iat[index]):
                history.append(float(metric.iat[index]))
    df["baseline_n"] = baseline_n
    df["baseline_value"] = baseline_value
    df["previous_metric"] = previous_metric
    df["current_metric"] = metric
    df["naive_score"] = metric - df["baseline_value"]
    use_two_game = spec.get("use_two_game", True)
    df["detected_value"] = (
        (metric + df["previous_metric"]) / 2 if use_two_game else metric
    )
    df["detected_delta"] = df["detected_value"] - df["baseline_value"]
    same_direction = np.sign(df["naive_score"]) == np.sign(df["detected_delta"])
    concentration = (
        df["naive_score"].abs() / (df["detected_delta"].abs() + 1e-9)
    ).clip(lower=0, upper=3)
    sample_weight = (df["baseline_n"] / max(baseline_window, 1)).clip(0, 1) ** 0.5
    if not spec.get("use_sample_weight", True):
        sample_weight = pd.Series(1.0, index=df.index)
    concentration_penalty = pd.Series(
        np.where(concentration > 2.0, 0.65, 1.0), index=df.index
    )
    if not spec.get("use_concentration_penalty", True):
        concentration_penalty = pd.Series(1.0, index=df.index)
    df["full_score"] = df["detected_delta"] * sample_weight * concentration_penalty
    effective_minimum = int(spec.get("minimum_baseline_override", minimum_baseline))
    df["method_eligible"] = (
        current_eligible
        & df["baseline_n"].ge(effective_minimum)
        & df["baseline_value"].notna()
    )
    df["detector_eligible"] = df["method_eligible"] & df["detected_value"].notna()
    if spec.get("require_same_direction", True):
        df["detector_eligible"] &= same_direction
    return df


def _method_frame(
    family_data: pd.DataFrame,
    *,
    method: str,
    baseline_window: int,
    minimum_baseline: int,
    spec: dict[str, Any],
) -> pd.DataFrame:
    method_spec = dict(spec)
    if method == "naive_spike":
        method_spec["use_two_game"] = False
        metric = "metric_all"
        score_column = "naive_score"
    elif method == "two_week_raw":
        method_spec["use_two_game"] = True
        metric = "metric_all"
        score_column = "detected_delta"
    elif method == "normal_game_trend":
        method_spec["use_two_game"] = True
        metric = "metric_normal"
        score_column = "detected_delta"
    else:
        raise ValueError(method)
    featured = _legacy_features(
        family_data,
        metric_column=metric,
        baseline_window=baseline_window,
        minimum_baseline=minimum_baseline,
        spec=method_spec,
    )
    featured["method"] = method
    featured["method_score"] = featured[score_column]
    return featured


def _select_variant_full(
    featured: pd.DataFrame,
    *,
    family: str,
    min_delta: float,
    spec: dict[str, Any],
    mode: str,
    original_counts: dict[tuple[str, int, int], int],
) -> pd.DataFrame:
    mask = featured["detector_eligible"].copy()
    if spec.get("require_min_delta", True):
        mask &= featured["detected_delta"].abs().ge(min_delta)
    pool = featured.loc[mask].copy()
    if mode == "operational":
        selected = pool
        selected["fixed_volume_backfill_below_threshold"] = False
    elif mode == "fixed_volume":
        pieces: list[pd.DataFrame] = []
        pool["_abs_rank_score"] = pool["full_score"].abs()
        pool = pool.sort_values(
            ["season", "week", "_abs_rank_score", "player_id", "team"],
            ascending=[True, True, False, True, True],
        )
        family_targets = sorted(
            (season, week, int(n))
            for (target_family, season, week), n in original_counts.items()
            if target_family == family and int(n) > 0
        )
        for season, week, n in family_targets:
            group = pool.loc[
                pool["season"].eq(season) & pool["week"].eq(week)
            ].copy()
            selected_group = group.head(n).copy()
            selected_group["fixed_volume_backfill_below_threshold"] = False
            if len(selected_group) < n:
                selected_keys = set(selected_group.index)
                eligible = featured.loc[
                    featured["detector_eligible"]
                    & featured["season"].eq(season)
                    & featured["week"].eq(week)
                    & ~featured.index.isin(selected_keys)
                ].copy()
                eligible["_abs_rank_score"] = eligible["full_score"].abs()
                eligible = eligible.sort_values(
                    ["_abs_rank_score", "player_id", "team"],
                    ascending=[False, True, True],
                )
                needed = n - len(selected_group)
                if len(eligible) < needed:
                    raise RuntimeError(
                        f"Fixed-volume ablation has {len(selected_group) + len(eligible)} "
                        f"eligible rows but needs {n}: {family} {season} week {week} "
                        f"{spec['name']}"
                    )
                backfill = eligible.head(needed).copy()
                backfill["fixed_volume_backfill_below_threshold"] = True
                selected_group = pd.concat([selected_group, backfill], ignore_index=False)
            pieces.append(selected_group)
        selected = pd.concat(pieces, ignore_index=True) if pieces else pool.head(0)
        selected = selected.drop(columns="_abs_rank_score", errors="ignore")
    else:
        raise ValueError(mode)
    selected = selected.copy()
    selected["method"] = "full_propwar"
    selected["method_score"] = selected["full_score"]
    selected["role_family"] = family
    return selected


def run_legacy_ablation(
    data: pd.DataFrame,
    selected_parameters: pd.DataFrame,
    original_alerts: pd.DataFrame,
    *,
    test_season: int = 2021,
    partial_policy: str = "PRIMARY_CONFIRMED_EXCLUDED",
) -> dict[str, pd.DataFrame]:
    """Execute operational and fixed-volume ablations for every legacy safeguard."""
    original_full = original_alerts.loc[original_alerts["method"].eq("full_propwar")]
    original_counts = (
        original_full.groupby(["role_family", "season", "week"]).size().to_dict()
    )
    evaluation_data = data.copy()
    evaluation_data["partial_game_flag"] = partial_exclusion_mask(
        evaluation_data, partial_policy
    )
    future_lookup = build_future_outcome_lookup(evaluation_data, "metric_normal", 2)
    all_alerts: list[pd.DataFrame] = []
    verification_rows: list[dict[str, Any]] = []
    membership_rows: list[dict[str, Any]] = []
    feature_cache: dict[tuple[Any, ...], pd.DataFrame] = {}

    def cached_features(
        family_data: pd.DataFrame,
        family: str,
        metric_column: str,
        baseline_window: int,
        minimum_baseline: int,
        feature_spec: dict[str, Any],
    ) -> pd.DataFrame:
        relevant = (
            feature_spec.get("use_two_game", True),
            feature_spec.get("use_sample_weight", True),
            feature_spec.get("use_concentration_penalty", True),
            feature_spec.get("minimum_baseline_override"),
            feature_spec.get("require_same_direction", True),
            feature_spec.get("require_data_quality", True),
            feature_spec.get("require_qualifying", True),
            feature_spec.get("exclude_legacy_partial", True),
            feature_spec.get("history_unfiltered", False),
            feature_spec.get("component_quality"),
            feature_spec.get("exclude_late_backup", True),
        )
        key = (
            family,
            metric_column,
            baseline_window,
            minimum_baseline,
            *relevant,
        )
        if key not in feature_cache:
            feature_cache[key] = _legacy_features(
                family_data,
                metric_column=metric_column,
                baseline_window=baseline_window,
                minimum_baseline=minimum_baseline,
                spec=feature_spec,
            )
        return feature_cache[key]

    parameters = selected_parameters.set_index("role_family")
    season_weeks = sorted(
        (int(s), int(w))
        for s, w in data.loc[data["season"].eq(test_season), ["season", "week"]]
        .drop_duplicates()
        .itertuples(index=False, name=None)
    )
    original_keys = set(
        map(
            tuple,
            original_full[
                ["season", "week", "player_id", "team", "role_family"]
            ].itertuples(index=False, name=None),
        )
    )
    for spec in legacy_ablation_specs():
        spec = {**spec, "name": spec["name"]}
        for mode in ("operational", "fixed_volume"):
            variant_full_parts: list[pd.DataFrame] = []
            comparator_cache: dict[tuple[str, str], pd.DataFrame] = {}
            for family in ROLE_FAMILIES:
                family_data = data.loc[data["role_family"].eq(family)].copy()
                params = parameters.loc[family]
                metric = "metric_normal" if spec.get("use_normal_metric", True) else "metric_all"
                featured = cached_features(
                    family_data,
                    family,
                    metric,
                    int(params["baseline_window"]),
                    int(params["min_baseline_games"]),
                    spec,
                )
                full = _select_variant_full(
                    featured,
                    family=family,
                    min_delta=float(params["min_abs_delta"]),
                    spec=spec,
                    mode=mode,
                    original_counts=original_counts,
                )
                full = full.loc[full["season"].eq(test_season)].copy()
                full["ablation"] = spec["name"]
                full["ablated_safeguard"] = spec["safeguard"]
                full["ablation_mode"] = mode
                variant_full_parts.append(full)
                for method in EXPECTED_METHODS:
                    if method == "full_propwar":
                        continue
                    method_spec = dict(spec)
                    if method == "naive_spike":
                        method_spec["use_two_game"] = False
                        method_metric = "metric_all"
                        score_column = "naive_score"
                    elif method == "two_week_raw":
                        method_spec["use_two_game"] = True
                        method_metric = "metric_all"
                        score_column = "detected_delta"
                    else:
                        method_spec["use_two_game"] = True
                        method_metric = "metric_normal"
                        score_column = "detected_delta"
                    method_featured = cached_features(
                        family_data,
                        family,
                        method_metric,
                        int(params["baseline_window"]),
                        int(params["min_baseline_games"]),
                        method_spec,
                    ).copy()
                    method_featured["method"] = method
                    method_featured["method_score"] = method_featured[score_column]
                    comparator_cache[(family, method)] = method_featured
            variant_full = pd.concat(variant_full_parts, ignore_index=True)
            variant_keys = set(
                map(
                    tuple,
                    variant_full[
                        ["season", "week", "player_id", "team", "role_family"]
                    ].itertuples(index=False, name=None),
                )
            )
            membership_rows.append(
                {
                    "ablation": spec["name"],
                    "ablated_safeguard": spec["safeguard"],
                    "ablation_mode": mode,
                    "full_alerts": len(variant_full),
                    "overlap_with_original": len(variant_keys & original_keys),
                    "added_vs_original": len(variant_keys - original_keys),
                    "removed_vs_original": len(original_keys - variant_keys),
                    "identical_membership": variant_keys == original_keys,
                    "fixed_volume_backfill_rows": int(
                        variant_full.get(
                            "fixed_volume_backfill_below_threshold",
                            pd.Series(False, index=variant_full.index),
                        ).sum()
                    ),
                }
            )
            selected_methods: list[pd.DataFrame] = [variant_full]
            full_counts = variant_full.groupby(["role_family", "season", "week"]).size().to_dict()
            for family in ROLE_FAMILIES:
                for method in EXPECTED_METHODS:
                    if method == "full_propwar":
                        continue
                    candidates = comparator_cache[(family, method)]
                    candidates = candidates.loc[
                        candidates["method_eligible"] & candidates["season"].eq(test_season)
                    ].copy()
                    candidates["_abs_score"] = candidates["method_score"].abs()
                    candidates = candidates.sort_values(
                        ["season", "week", "_abs_score", "player_id", "team"],
                        ascending=[True, True, False, True, True],
                    )
                    for season, week in season_weeks:
                        n = int(full_counts.get((family, season, week), 0))
                        pool = candidates.loc[
                            candidates["season"].eq(season) & candidates["week"].eq(week)
                        ]
                        if len(pool) < n:
                            raise RuntimeError(
                                f"Ablation comparator cannot match volume: {spec['name']} "
                                f"{mode} {family} {season}-{week} {method}"
                            )
                        if n:
                            chosen = pool.head(n).drop(columns="_abs_score")
                            chosen["ablation"] = spec["name"]
                            chosen["ablated_safeguard"] = spec["safeguard"]
                            chosen["ablation_mode"] = mode
                            selected_methods.append(chosen)
                for season, week in season_weeks:
                    n = int(full_counts.get((family, season, week), 0))
                    verification_rows.append(
                        {
                            "ablation": spec["name"],
                            "ablation_mode": mode,
                            "role_family": family,
                            "season": season,
                            "week": week,
                            **{f"{method}_count": n for method in EXPECTED_METHODS},
                            "equal_volume": True,
                            "observed_method_count": len(EXPECTED_METHODS),
                        }
                    )
            selected = pd.concat(selected_methods, ignore_index=True)
            evaluated = attach_future_outcomes(
                selected,
                full_weekly=evaluation_data,
                metric_column="metric_normal",
                horizon=2,
                retention_threshold=0.50,
                reversion_threshold=0.25,
                future_lookup=future_lookup,
            )
            all_alerts.append(evaluated)

    return {
        "alerts": pd.concat(all_alerts, ignore_index=True),
        "equal_volume": pd.DataFrame(verification_rows),
        "membership": pd.DataFrame(membership_rows),
    }
