from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def build_future_outcome_lookup(
    full_weekly: pd.DataFrame, metric_column: str, horizon: int = 2
) -> pd.DataFrame:
    weekly = full_weekly.sort_values(["player_id", "role_family", "season", "week"]).copy()
    weekly["_eval_metric"] = pd.to_numeric(weekly[metric_column], errors="coerce")
    eligible = (
        weekly["qualifying_game"].fillna(False).astype(bool)
        & ~weekly["partial_game_flag"].fillna(True).astype(bool)
        & weekly["data_quality_pass"].fillna(False).astype(bool)
        & weekly["_eval_metric"].notna()
    )
    eligible_weekly = weekly.loc[eligible].copy()
    grouped = eligible_weekly.groupby(["player_id", "role_family", "season"], sort=False)["_eval_metric"]
    future_columns = []
    for offset in range(1, horizon + 1):
        column = f"_future_{offset}"
        eligible_weekly[column] = grouped.shift(-offset)
        future_columns.append(column)
    eligible_weekly["future_n"] = eligible_weekly[future_columns].notna().sum(axis=1)
    eligible_weekly["next_game_value"] = eligible_weekly[future_columns[0]]
    eligible_weekly["future_mean"] = eligible_weekly[future_columns].mean(axis=1)
    keys = ["season", "week", "player_id", "team", "role_family"]
    return eligible_weekly[keys + ["future_n", "next_game_value", "future_mean"]].drop_duplicates(keys)


def attach_future_outcomes(
    alerts: pd.DataFrame,
    full_weekly: pd.DataFrame,
    metric_column: str,
    horizon: int = 2,
    retention_threshold: float = 0.50,
    reversion_threshold: float = 0.25,
    future_lookup: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Attach next-game and next-N-game leakage-safe role outcomes."""
    if alerts.empty:
        return alerts.copy()

    # Fold outcomes must remain inside the test season. Build one causal lookup
    # for all qualifying rows instead of rescanning the table per alert.
    lookup_keys = ["season", "week", "player_id", "team", "role_family"]
    lookup = future_lookup if future_lookup is not None else build_future_outcome_lookup(full_weekly, metric_column, horizon)
    result = alerts.merge(lookup, on=lookup_keys, how="left")
    result["future_n"] = result["future_n"].fillna(0).astype(int)

    baseline = pd.to_numeric(result["baseline_value"], errors="coerce")
    detected_value = pd.to_numeric(result.get("detected_value"), errors="coerce")
    fallback = baseline + pd.to_numeric(result["method_score"], errors="coerce")
    detected_value = detected_value.fillna(fallback)
    detected = detected_value - baseline
    denominator = detected.abs().replace(0, np.nan)
    direction = np.sign(detected)
    result["next_game_retention"] = (
        (pd.to_numeric(result["next_game_value"], errors="coerce") - baseline)
        * direction / denominator
    )
    result["retention"] = (
        (pd.to_numeric(result["future_mean"], errors="coerce") - baseline)
        * direction / denominator
    )
    evaluable = result["retention"].notna() & result["future_n"].ge(horizon)
    result["persistent"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    result.loc[evaluable, "persistent"] = result.loc[evaluable, "retention"].ge(
        retention_threshold
    )
    reversion_evaluable = result["next_game_retention"].notna()
    result["immediate_reversion"] = pd.Series(pd.NA, index=result.index, dtype="boolean")
    result.loc[reversion_evaluable, "immediate_reversion"] = result.loc[
        reversion_evaluable, "next_game_retention"
    ].lt(reversion_threshold)
    return result


def bootstrap_rate_interval(
    values: Iterable[bool],
    iterations: int = 2000,
    confidence_level: float = 0.95,
    seed: int = 850,
) -> tuple[float, float]:
    series = pd.Series(values).dropna().astype(float).to_numpy()
    if len(series) == 0:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    samples = rng.choice(series, size=(iterations, len(series)), replace=True).mean(axis=1)
    alpha = (1 - confidence_level) / 2
    return (
        float(np.quantile(samples, alpha)),
        float(np.quantile(samples, 1 - alpha)),
    )


def summarize_alerts(alerts: pd.DataFrame, bootstrap_iterations: int = 2000) -> pd.DataFrame:
    if alerts.empty:
        return pd.DataFrame(
            columns=[
                "role_family",
                "method",
                "alerts",
                "precision",
                "precision_ci_low",
                "precision_ci_high",
                "reversion_rate",
                "median_retention",
            ]
        )

    rows = []
    for (family, method), group in alerts.groupby(["role_family", "method"], dropna=False):
        valid = group.loc[group["persistent"].notna()]
        precision = float(valid["persistent"].astype(float).mean()) if len(valid) else np.nan
        ci_low, ci_high = bootstrap_rate_interval(
            valid["persistent"],
            iterations=bootstrap_iterations,
        )
        reversion = (
            float(group["immediate_reversion"].dropna().astype(float).mean())
            if group["immediate_reversion"].notna().any()
            else np.nan
        )
        rows.append(
            {
                "role_family": family,
                "method": method,
                "alerts": len(group),
                "evaluable_alerts": len(valid),
                "precision": precision,
                "precision_ci_low": ci_low,
                "precision_ci_high": ci_high,
                "reversion_rate": reversion,
                "median_retention": float(valid["retention"].median()) if len(valid) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _cluster_bootstrap_difference(
    alerts: pd.DataFrame,
    value_column: str,
    full_method: str = "full_propwar",
    comparator: str = "naive_spike",
    iterations: int = 2000,
    confidence_level: float = 0.95,
    seed: int = 850,
) -> tuple[float, float]:
    data = alerts.loc[
        alerts["method"].isin([full_method, comparator])
        & alerts[value_column].notna()
    ].copy()
    if data.empty:
        return (np.nan, np.nan)
    data["cluster"] = data["season"].astype(str) + "-" + data["week"].astype(str)
    clusters = sorted(data["cluster"].unique())
    if not clusters:
        return (np.nan, np.nan)
    rng = np.random.default_rng(seed)
    aggregated = (
        data.groupby(["cluster", "method"])[value_column]
        .agg(["sum", "count"]).reset_index()
    )
    sums = aggregated.pivot(index="cluster", columns="method", values="sum").reindex(clusters).fillna(0)
    counts = aggregated.pivot(index="cluster", columns="method", values="count").reindex(clusters).fillna(0)
    if full_method not in sums or comparator not in sums:
        return (np.nan, np.nan)
    sampled_indices = rng.integers(0, len(clusters), size=(iterations, len(clusters)))
    full_denominator = counts[full_method].to_numpy()[sampled_indices].sum(axis=1)
    comparator_denominator = counts[comparator].to_numpy()[sampled_indices].sum(axis=1)
    valid = (full_denominator > 0) & (comparator_denominator > 0)
    differences = (
        sums[full_method].to_numpy()[sampled_indices].sum(axis=1) / full_denominator
        - sums[comparator].to_numpy()[sampled_indices].sum(axis=1) / comparator_denominator
    )[valid]
    if len(differences) == 0:
        return (np.nan, np.nan)
    alpha = (1 - confidence_level) / 2
    return (
        float(np.quantile(differences, alpha)),
        float(np.quantile(differences, 1 - alpha)),
    )


def summarize_method_comparisons(
    alerts: pd.DataFrame,
    bootstrap_iterations: int = 2000,
    confidence_level: float = 0.95,
    seed: int = 850,
) -> pd.DataFrame:
    """Compare full PropWar with the equal-volume naive method by family."""
    if alerts.empty:
        return pd.DataFrame()
    rows = []
    for family, group in alerts.groupby("role_family"):
        full = group.loc[group["method"].eq("full_propwar")]
        naive = group.loc[group["method"].eq("naive_spike")]
        full_valid = full.loc[full["persistent"].notna()]
        naive_valid = naive.loc[naive["persistent"].notna()]
        full_precision = float(full_valid["persistent"].astype(float).mean()) if len(full_valid) else np.nan
        naive_precision = float(naive_valid["persistent"].astype(float).mean()) if len(naive_valid) else np.nan
        precision_improvement = full_precision - naive_precision
        ci_low, ci_high = _cluster_bootstrap_difference(
            group.assign(persistent_numeric=pd.to_numeric(group["persistent"], errors="coerce")),
            "persistent_numeric",
            iterations=bootstrap_iterations,
            confidence_level=confidence_level,
            seed=seed,
        )
        full_reversion = pd.to_numeric(full["immediate_reversion"], errors="coerce").mean()
        naive_reversion = pd.to_numeric(naive["immediate_reversion"], errors="coerce").mean()
        rows.append(
            {
                "role_family": family,
                "full_alerts": len(full),
                "naive_alerts": len(naive),
                "full_evaluable_alerts": len(full_valid),
                "naive_evaluable_alerts": len(naive_valid),
                "full_precision": full_precision,
                "naive_precision": naive_precision,
                "precision_improvement": precision_improvement,
                "relative_precision_improvement": (
                    precision_improvement / naive_precision
                    if pd.notna(naive_precision) and naive_precision != 0 else np.nan
                ),
                "precision_improvement_ci_low": ci_low,
                "precision_improvement_ci_high": ci_high,
                "full_reversion_rate": float(full_reversion) if pd.notna(full_reversion) else np.nan,
                "naive_reversion_rate": float(naive_reversion) if pd.notna(naive_reversion) else np.nan,
                "reversion_improvement": (
                    float(naive_reversion - full_reversion)
                    if pd.notna(full_reversion) and pd.notna(naive_reversion) else np.nan
                ),
                "full_median_retention": float(full_valid["retention"].median()) if len(full_valid) else np.nan,
                "naive_median_retention": float(naive_valid["retention"].median()) if len(naive_valid) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def release_decision(
    family_summary: pd.DataFrame,
    gates: dict,
    nfl_weeks: int = 18,
) -> pd.DataFrame:
    """Apply release gates using equal-volume naive_spike as comparator."""
    rows = []
    for family, group in family_summary.groupby("role_family"):
        full = group.loc[group["method"].eq("full_propwar")]
        naive = group.loc[group["method"].eq("naive_spike")]
        if full.empty or naive.empty:
            rows.append(
                {"role_family": family, "status": "INSUFFICIENT", "reason": "Missing method comparison."}
            )
            continue
        f = full.iloc[0]
        n = naive.iloc[0]
        improvement = f["precision"] - n["precision"]
        reversion_improvement = n["reversion_rate"] - f["reversion_rate"]
        alerts_per_week = f["alerts"] / nfl_weeks

        checks = {
            "min_holdout_alerts": f["alerts"] >= gates["min_holdout_alerts"],
            "min_persistence_precision": f["precision"] >= gates["min_persistence_precision"],
            "min_absolute_improvement_vs_naive": improvement >= gates["min_absolute_improvement_vs_naive"],
            "max_immediate_reversion_rate": f["reversion_rate"] <= gates["max_immediate_reversion_rate"],
            "min_reversion_improvement_vs_naive": reversion_improvement >= gates["min_reversion_improvement_vs_naive"],
            "min_median_retention": f["median_retention"] >= gates["min_median_retention"],
            "min_alerts_per_week": alerts_per_week >= gates["min_alerts_per_week"],
        }
        status = "FULL_RELEASE" if all(checks.values()) else "FAIL"
        rows.append(
            {
                "role_family": family,
                "status": status,
                "alerts": int(f["alerts"]),
                "precision": f["precision"],
                "naive_precision": n["precision"],
                "precision_improvement": improvement,
                "reversion_rate": f["reversion_rate"],
                "reversion_improvement": reversion_improvement,
                "median_retention": f["median_retention"],
                "alerts_per_week": alerts_per_week,
                "failed_checks": ", ".join(k for k, ok in checks.items() if not ok),
            }
        )
    return pd.DataFrame(rows)
