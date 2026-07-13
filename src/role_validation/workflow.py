from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from role_validation.detector import (
    add_comparison_features,
    select_equal_volume_alerts,
    verify_equal_volume,
)
from role_validation.evaluation import (
    attach_future_outcomes,
    build_future_outcome_lookup,
    summarize_alerts,
    summarize_method_comparisons,
)


@dataclass
class FoldResult:
    tuning_results: pd.DataFrame
    selected_parameters: pd.DataFrame
    alerts: pd.DataFrame
    summary: pd.DataFrame
    comparisons: pd.DataFrame
    weekly_counts: pd.DataFrame
    equal_volume: pd.DataFrame


def _evaluate(
    alerts: pd.DataFrame,
    weekly: pd.DataFrame,
    config: dict,
    future_lookup: pd.DataFrame | None = None,
) -> pd.DataFrame:
    return attach_future_outcomes(
        alerts,
        full_weekly=weekly,
        metric_column="metric_normal",
        horizon=int(config["primary_outcome"]["horizon_qualifying_games"]),
        retention_threshold=float(config["primary_outcome"]["retention_threshold"]),
        reversion_threshold=float(config["primary_outcome"]["immediate_reversion_threshold"]),
        future_lookup=future_lookup,
    )


def _development_row(
    family: str,
    baseline_window: int,
    min_baseline_games: int,
    min_abs_delta: float,
    evaluated: pd.DataFrame,
    config: dict,
) -> dict:
    if evaluated.empty:
        return {
            "role_family": family,
            "baseline_window": baseline_window,
            "min_baseline_games": min_baseline_games,
            "min_abs_delta": min_abs_delta,
            "full_alerts": 0,
            "full_evaluable_alerts": 0,
            "full_precision": np.nan,
            "naive_precision": np.nan,
            "precision_improvement": np.nan,
            "full_reversion_rate": np.nan,
            "reversion_improvement": np.nan,
            "full_median_retention": np.nan,
        }
    full = evaluated.loc[evaluated["method"].eq("full_propwar")]
    naive = evaluated.loc[evaluated["method"].eq("naive_spike")]
    full_valid = full.loc[full["persistent"].notna()]
    naive_valid = naive.loc[naive["persistent"].notna()]
    full_precision = pd.to_numeric(full_valid["persistent"], errors="coerce").mean()
    naive_precision = pd.to_numeric(naive_valid["persistent"], errors="coerce").mean()
    full_reversion = pd.to_numeric(full["immediate_reversion"], errors="coerce").mean()
    naive_reversion = pd.to_numeric(naive["immediate_reversion"], errors="coerce").mean()
    return {
        "role_family": family,
        "baseline_window": baseline_window,
        "min_baseline_games": min_baseline_games,
        "min_abs_delta": min_abs_delta,
        "full_alerts": len(full),
        "full_evaluable_alerts": len(full_valid),
        "full_precision": float(full_precision) if pd.notna(full_precision) else np.nan,
        "naive_precision": float(naive_precision) if pd.notna(naive_precision) else np.nan,
        "precision_improvement": float(full_precision - naive_precision)
        if pd.notna(full_precision) and pd.notna(naive_precision) else np.nan,
        "full_reversion_rate": float(full_reversion) if pd.notna(full_reversion) else np.nan,
        "reversion_improvement": float(naive_reversion - full_reversion)
        if pd.notna(full_reversion) and pd.notna(naive_reversion) else np.nan,
        "full_median_retention": float(full_valid["retention"].median()) if len(full_valid) else np.nan,
    }


def _select_development_parameters(results: pd.DataFrame, minimum_evaluable: int) -> pd.Series:
    eligible = results.loc[results["full_evaluable_alerts"].ge(minimum_evaluable)].copy()
    if eligible.empty:
        eligible = results.copy()
    eligible["rank_precision_improvement"] = eligible["precision_improvement"].fillna(-np.inf)
    eligible["rank_full_precision"] = eligible["full_precision"].fillna(-np.inf)
    eligible["rank_reversion"] = -eligible["full_reversion_rate"].fillna(np.inf)
    eligible["rank_retention"] = eligible["full_median_retention"].fillna(-np.inf)
    return eligible.sort_values(
        [
            "rank_precision_improvement", "rank_full_precision", "rank_reversion",
            "rank_retention", "full_evaluable_alerts", "min_abs_delta",
        ],
        ascending=[False, False, False, False, False, False],
    ).iloc[0]


def run_fold(
    data: pd.DataFrame,
    config: dict,
    development_seasons: list[int],
    test_season: int,
    minimum_development_evaluable_alerts: int = 25,
) -> FoldResult:
    """Tune only on development seasons, then execute the untouched test season."""
    fold_data = data.loc[data["season"].isin([*development_seasons, test_season])].copy()
    tuning_rows = []
    selected_rows = []
    test_alerts = []

    parameter_pairs = sorted(
        {
            (int(window), int(minimum))
            for family_config in config["role_families"].values()
            for window in family_config["baseline_window_games"]
            for minimum in family_config["min_baseline_games"]
        }
    )
    scored_cache = {
        pair: add_comparison_features(
            fold_data, baseline_window=pair[0], min_baseline_games=pair[1]
        )
        for pair in parameter_pairs
    }
    future_lookup = build_future_outcome_lookup(
        fold_data,
        "metric_normal",
        int(config["primary_outcome"]["horizon_qualifying_games"]),
    )

    for family, family_config in config["role_families"].items():
        family_tuning = []
        for baseline_window in family_config["baseline_window_games"]:
            for min_baseline_games in family_config["min_baseline_games"]:
                cache_key = (int(baseline_window), int(min_baseline_games))
                scored = scored_cache[cache_key]
                for min_abs_delta in family_config["candidate_min_abs_delta"]:
                    selected = select_equal_volume_alerts(
                        scored, family=family, min_abs_delta=float(min_abs_delta)
                    )
                    development_alerts = (
                        selected.loc[selected["season"].isin(development_seasons)].copy()
                        if not selected.empty else selected.copy()
                    )
                    evaluated = _evaluate(development_alerts, fold_data, config, future_lookup)
                    row = _development_row(
                        family, cache_key[0], cache_key[1], float(min_abs_delta),
                        evaluated, config,
                    )
                    family_tuning.append(row)
                    tuning_rows.append(row)

        family_results = pd.DataFrame(family_tuning)
        chosen = _select_development_parameters(
            family_results, minimum_development_evaluable_alerts
        )
        selected_rows.append(
            {
                "role_family": family,
                "baseline_window": int(chosen["baseline_window"]),
                "min_baseline_games": int(chosen["min_baseline_games"]),
                "min_abs_delta": float(chosen["min_abs_delta"]),
                "development_alerts": int(chosen["full_alerts"]),
                "development_evaluable_alerts": int(chosen["full_evaluable_alerts"]),
                "development_precision": float(chosen["full_precision"]),
                "development_naive_precision": float(chosen["naive_precision"]),
                "development_precision_improvement": float(chosen["precision_improvement"]),
                "selection_minimum_evaluable_alerts": minimum_development_evaluable_alerts,
            }
        )
        chosen_scored = scored_cache[(int(chosen["baseline_window"]), int(chosen["min_baseline_games"]))]
        selected = select_equal_volume_alerts(
            chosen_scored, family=family, min_abs_delta=float(chosen["min_abs_delta"])
        )
        selected = (
            selected.loc[selected["season"].eq(test_season)].copy()
            if not selected.empty else selected.copy()
        )
        test_alerts.append(_evaluate(selected, fold_data, config, future_lookup))

    alerts = pd.concat(test_alerts, ignore_index=True) if test_alerts else pd.DataFrame()
    summary = summarize_alerts(
        alerts, bootstrap_iterations=int(config["bootstrap"]["iterations"])
    )
    comparisons = summarize_method_comparisons(
        alerts,
        bootstrap_iterations=int(config["bootstrap"]["iterations"]),
        confidence_level=float(config["bootstrap"]["confidence_level"]),
        seed=int(config["bootstrap"]["random_seed"]),
    )
    weekly_counts = (
        alerts.groupby(["role_family", "season", "week", "method"]).size()
        .rename("alerts").reset_index()
        if len(alerts) else pd.DataFrame(columns=["role_family", "season", "week", "method", "alerts"])
    )
    equal_volume = verify_equal_volume(alerts)
    return FoldResult(
        tuning_results=pd.DataFrame(tuning_rows),
        selected_parameters=pd.DataFrame(selected_rows),
        alerts=alerts,
        summary=summary,
        comparisons=comparisons,
        weekly_counts=weekly_counts,
        equal_volume=equal_volume,
    )
