from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Iterable

import numpy as np
import pandas as pd
import yaml

from role_validation.diagnostics import (
    add_diagnostic_dimensions,
    deduplicated_feed,
    summarize_metrics,
)
from role_validation.evaluation import summarize_alerts, summarize_method_comparisons
from role_validation.redevelopment import CANONICAL_KEY, EXPECTED_METHODS, ROLE_FAMILIES


FOLD2_SEASON = 2022
PRIMARY_POLICY = "PRIMARY_CONFIRMED_EXCLUDED"
PARTIAL_POLICIES = (
    PRIMARY_POLICY,
    "ALL_INCLUDED",
    "STRICT_SUSPECTED_EXCLUDED",
)
WEEK_BLOCKS = {
    "early_weeks_1_6": (1, 6),
    "middle_weeks_7_12": (7, 12),
    "late_weeks_13_18": (13, 18),
}


def file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def frozen_report_document(report_text: str) -> dict[str, Any]:
    match = re.search(
        r"## Exact candidate recommended for Fold 2\s*```yaml\s*(.*?)\s*```",
        report_text,
        flags=re.DOTALL,
    )
    if not match:
        raise AssertionError("Fold 1 report has no exact Fold 2 candidate YAML block")
    document = yaml.safe_load(match.group(1))
    if not isinstance(document, dict):
        raise AssertionError("Fold 1 candidate YAML block is not a mapping")
    return document


def assert_frozen_config_integrity(
    config_path: Path,
    report_path: Path,
    *,
    expected_sha256: str,
) -> dict[str, Any]:
    digest = file_sha256(config_path)
    config_document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    report_document = frozen_report_document(report_path.read_text(encoding="utf-8"))
    checks = {
        "sha256_matches_precommitted_fingerprint": digest == expected_sha256,
        "document_matches_fold1_report": config_document == report_document,
        "fold2_test_season_is_2022": (
            config_document.get("analysis_contract", {}).get("fold_2_test_season")
            == FOLD2_SEASON
        ),
        "fold2_was_unexecuted_when_frozen": not bool(
            config_document.get("analysis_contract", {}).get("fold_2_executed")
        ),
        "post_2021_results_were_unused_when_frozen": not bool(
            config_document.get("analysis_contract", {}).get("post_2021_results_used")
        ),
        "release_gates_unchanged": not bool(
            config_document.get("analysis_contract", {}).get("release_gates_changed")
        ),
        "baseline_resets_each_season": bool(
            config_document.get("candidate", {})
            .get("baseline", {})
            .get("reset_each_season")
        ),
        "baseline_excludes_confirmation_games": bool(
            config_document.get("candidate", {})
            .get("baseline", {})
            .get("exclude_confirmation_games")
        ),
        "equal_volume_within_family_season_week": (
            config_document.get("candidate", {})
            .get("comparison", {})
            .get("equal_volume_within")
            == ["role_family", "season", "week"]
        ),
        "primary_partial_policy_is_confirmed_excluded": (
            config_document.get("candidate", {})
            .get("partial_game_policy", {})
            .get("primary")
            == PRIMARY_POLICY
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]
    if failed:
        raise AssertionError(f"Frozen configuration integrity failed: {failed}")
    return {
        "path": str(config_path),
        "sha256": digest,
        "expected_sha256": expected_sha256,
        "checks": checks,
        "config_document": config_document,
    }


def canonical_audit(
    canonical: pd.DataFrame,
    required_columns: Iterable[str],
    expected_season: int = FOLD2_SEASON,
) -> pd.DataFrame:
    required = list(required_columns)
    missing_columns = sorted(set(required) - set(canonical.columns))
    if missing_columns:
        raise AssertionError(f"Canonical data lacks required columns: {missing_columns}")
    seasons = set(pd.to_numeric(canonical["season"], errors="raise").astype(int).unique())
    if seasons != {expected_season}:
        raise AssertionError(
            f"Expected canonical season {expected_season}; found {sorted(seasons)}"
        )
    duplicate_rows = int(canonical.duplicated(CANONICAL_KEY, keep=False).sum())
    required_null_cells = int(canonical[required].isna().sum().sum())
    required_null_rows = int(canonical[required].isna().any(axis=1).sum())
    identity = canonical["identity_resolved"].fillna(False).astype(bool)
    quality = canonical["data_quality_pass"].fillna(False).astype(bool)
    qualifying = canonical["qualifying_game"].fillna(False).astype(bool)
    audit = pd.DataFrame(
        [
            {
                "season": expected_season,
                "canonical_rows": len(canonical),
                "unique_players": canonical["player_id"].nunique(),
                "played_games": canonical["game_id"].nunique(),
                "observed_weeks": canonical["week"].nunique(),
                "duplicate_key_rows": duplicate_rows,
                "duplicate_key_rate": duplicate_rows / len(canonical) if len(canonical) else np.nan,
                "required_null_cells": required_null_cells,
                "required_null_rows": required_null_rows,
                "identity_resolved_rows": int(identity.sum()),
                "identity_coverage": float(identity.mean()) if len(identity) else np.nan,
                "quality_pass_rows": int(quality.sum()),
                "quality_pass_rate": float(quality.mean()) if len(quality) else np.nan,
                "qualifying_rows": int(qualifying.sum()),
                "qualifying_rate": float(qualifying.mean()) if len(qualifying) else np.nan,
            }
        ]
    )
    if duplicate_rows or required_null_cells:
        raise AssertionError("Fold 2 canonical grain or required completeness failed")
    if not identity.all() or not quality.all() or not qualifying.all():
        raise AssertionError("Fold 2 identity, quality, or qualifying coverage is incomplete")
    if int(audit.at[0, "observed_weeks"]) != 18:
        raise AssertionError("Fold 2 canonical data does not cover all 18 regular-season weeks")
    return audit


def missingness_table(
    canonical: pd.DataFrame,
    expected_season: int = FOLD2_SEASON,
) -> pd.DataFrame:
    rows = []
    for column in canonical.columns:
        missing = int(canonical[column].isna().sum())
        rows.append(
            {
                "season": expected_season,
                "column": column,
                "rows": len(canonical),
                "missing_count": missing,
                "missing_rate": missing / len(canonical) if len(canonical) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def assert_temporal_integrity(
    alerts: pd.DataFrame,
    expected_season: int = FOLD2_SEASON,
) -> pd.DataFrame:
    full = alerts.loc[alerts["method"].eq("full_propwar")].copy()
    evaluable = full.loc[full["future_n"].ge(2)].copy()
    checks = {
        f"only_{expected_season}_alerts": (
            set(full["season"].astype(int).unique()) == {expected_season}
        ),
        "minimum_four_game_baseline": bool(full["baseline_n"].ge(4).all()),
        "confirmation_window_complete": bool(
            full["confirmation_n"].eq(full["confirmation_games"]).all()
        ),
        "baseline_strictly_before_confirmation": bool(
            full["baseline_max_week"].lt(full["confirmation_start_week"]).all()
        ),
        "confirmation_ends_on_alert_week": bool(
            full["confirmation_end_week"].eq(full["week"]).all()
        ),
        "first_outcome_strictly_after_alert": bool(
            evaluable["future_week_1"].gt(evaluable["week"]).all()
        ),
        "second_outcome_strictly_after_first": bool(
            evaluable["future_week_2"].gt(evaluable["future_week_1"]).all()
        ),
        "same_season_grouping_enabled_by_frozen_config": True,
    }
    failed = [name for name, value in checks.items() if not value]
    if failed:
        raise AssertionError(f"Fold 2 temporal checks failed: {failed}")
    return pd.DataFrame([{"check": key, "passed": value} for key, value in checks.items()])


def method_results(alerts: pd.DataFrame) -> pd.DataFrame:
    summary = summarize_metrics(alerts, ["partial_policy", "role_family", "method"])
    ci_parts = []
    for policy, group in alerts.groupby("partial_policy", sort=True):
        ci = summarize_alerts(group, bootstrap_iterations=2000)
        ci.insert(0, "partial_policy", policy)
        ci_parts.append(ci)
    ci = pd.concat(ci_parts, ignore_index=True)
    result = summary.merge(
        ci[["partial_policy", "role_family", "method", "precision_ci_low", "precision_ci_high"]],
        on=["partial_policy", "role_family", "method"],
        how="left",
        validate="one_to_one",
    )
    dedup = (
        alerts.drop_duplicates(["partial_policy", "role_family", "method", *CANONICAL_KEY[:-1]])
        .groupby(["partial_policy", "role_family", "method"])
        .size()
        .rename("deduplicated_player_week_team_alerts")
        .reset_index()
    )
    return result.merge(
        dedup,
        on=["partial_policy", "role_family", "method"],
        how="left",
        validate="one_to_one",
    )


def comparison_results(alerts: pd.DataFrame) -> pd.DataFrame:
    parts = []
    for policy, group in alerts.groupby("partial_policy", sort=True):
        result = summarize_method_comparisons(
            group,
            bootstrap_iterations=2000,
            confidence_level=0.95,
            seed=850,
        )
        result.insert(0, "partial_policy", policy)
        parts.append(result)
    return pd.concat(parts, ignore_index=True)


def direction_results(alerts: pd.DataFrame) -> pd.DataFrame:
    work = add_diagnostic_dimensions(alerts)
    return summarize_metrics(
        work,
        ["partial_policy", "role_family", "method", "direction"],
    )


def block_results(alerts: pd.DataFrame) -> pd.DataFrame:
    work = add_diagnostic_dimensions(alerts)
    return summarize_metrics(
        work,
        ["partial_policy", "role_family", "method", "week_block"],
    )


def weekly_stability(
    alerts: pd.DataFrame,
    season: int = FOLD2_SEASON,
) -> pd.DataFrame:
    weeks = pd.DataFrame({"season": season, "week": range(1, 19)})
    rows = []
    for (policy, family, method), group in alerts.groupby(
        ["partial_policy", "role_family", "method"], sort=True
    ):
        counts = (
            group.groupby(["season", "week"]).size().rename("alerts").reset_index()
        )
        counts = weeks.merge(counts, on=["season", "week"], how="left")
        counts["alerts"] = counts["alerts"].fillna(0).astype(int)
        rows.append(
            {
                "partial_policy": policy,
                "role_family": family,
                "method": method,
                "weekly_median": float(counts["alerts"].median()),
                "weekly_maximum": int(counts["alerts"].max()),
                "zero_alert_weeks": int(counts["alerts"].eq(0).sum()),
                "active_weeks": int(counts["alerts"].gt(0).sum()),
                "weekly_mean": float(counts["alerts"].mean()),
            }
        )
    return pd.DataFrame(rows)


def feed_summary(
    alerts: pd.DataFrame,
    season: int = FOLD2_SEASON,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    weekly_rows = []
    for (policy, method), group in alerts.groupby(["partial_policy", "method"], sort=True):
        feed = deduplicated_feed(group)
        counts = pd.DataFrame({"season": season, "week": range(1, 19)})
        weekly = feed.groupby(["season", "week"]).size().rename("deduplicated_alerts").reset_index()
        counts = counts.merge(weekly, on=["season", "week"], how="left")
        counts["deduplicated_alerts"] = counts["deduplicated_alerts"].fillna(0).astype(int)
        counts.insert(0, "method", method)
        counts.insert(0, "partial_policy", policy)
        weekly_rows.append(counts)
        summary_rows.append(
            {
                "partial_policy": policy,
                "method": method,
                "family_alert_rows": len(group),
                "deduplicated_player_week_team_alerts": len(feed),
                "duplicate_family_rows_removed": len(group) - len(feed),
                "weekly_median": float(counts["deduplicated_alerts"].median()),
                "weekly_maximum": int(counts["deduplicated_alerts"].max()),
                "zero_alert_weeks": int(counts["deduplicated_alerts"].eq(0).sum()),
            }
        )
    return pd.DataFrame(summary_rows), pd.concat(weekly_rows, ignore_index=True)


def repeat_rates(alerts: pd.DataFrame) -> pd.DataFrame:
    work = add_diagnostic_dimensions(alerts)
    ordered = work.sort_values(["partial_policy", "method", "role_family", "player_id", "week"])
    prior = ordered.groupby(
        ["partial_policy", "method", "role_family", "player_id"], sort=False
    )["week"].shift()
    ordered["consecutive_repeat"] = ordered["week"].eq(prior + 1)
    return (
        ordered.groupby(["partial_policy", "role_family", "method"], as_index=False)
        .agg(
            alerts=("player_id", "size"),
            repeat_alerts=("consecutive_repeat", "sum"),
            repeat_players=("player_id", lambda values: values[ordered.loc[values.index, "consecutive_repeat"]].nunique()),
        )
        .assign(repeat_rate=lambda frame: frame["repeat_alerts"] / frame["alerts"])
    )


def rb_overlap(alerts: pd.DataFrame) -> pd.DataFrame:
    rows = []
    key = ["season", "week", "player_id", "team"]
    for (policy, method), group in alerts.groupby(["partial_policy", "method"], sort=True):
        carry = set(map(tuple, group.loc[group["role_family"].eq("rb_carry_share"), key].itertuples(index=False, name=None)))
        opportunity = set(map(tuple, group.loc[group["role_family"].eq("rb_opportunity_share"), key].itertuples(index=False, name=None)))
        union = carry | opportunity
        rows.append(
            {
                "partial_policy": policy,
                "method": method,
                "carry_alerts": len(carry),
                "opportunity_alerts": len(opportunity),
                "overlap_alerts": len(carry & opportunity),
                "union_alerts": len(union),
                "jaccard_overlap": len(carry & opportunity) / len(union) if union else np.nan,
            }
        )
    return pd.DataFrame(rows)


def _family_comparison_for_period(alerts: pd.DataFrame, period: str) -> pd.DataFrame:
    method = summarize_alerts(alerts, bootstrap_iterations=2000)
    comparison = summarize_method_comparisons(
        alerts,
        bootstrap_iterations=2000,
        confidence_level=0.95,
        seed=850,
    )
    full_ci = method.loc[method["method"].eq("full_propwar"), [
        "role_family", "precision_ci_low", "precision_ci_high"
    ]]
    result = comparison.merge(full_ci, on="role_family", how="left", validate="one_to_one")
    result.insert(0, "period", period)
    return result


def generalization_table(alerts_2021: pd.DataFrame, alerts_2022: pd.DataFrame) -> pd.DataFrame:
    prior = _family_comparison_for_period(alerts_2021, "redeveloped_2021")
    current = _family_comparison_for_period(alerts_2022, "untouched_2022")
    metrics = [
        "full_alerts", "full_evaluable_alerts", "full_precision", "naive_precision",
        "precision_improvement", "precision_improvement_ci_low",
        "precision_improvement_ci_high", "full_reversion_rate",
        "reversion_improvement", "full_median_retention", "precision_ci_low",
        "precision_ci_high",
    ]
    left = prior[["role_family", *metrics]].rename(columns={name: f"development_2021_{name}" for name in metrics})
    right = current[["role_family", *metrics]].rename(columns={name: f"untouched_2022_{name}" for name in metrics})
    result = left.merge(right, on="role_family", how="outer", validate="one_to_one")
    for metric in [
        "full_alerts", "full_evaluable_alerts", "full_precision",
        "precision_improvement", "full_reversion_rate", "reversion_improvement",
        "full_median_retention",
    ]:
        result[f"delta_2022_minus_2021_{metric}"] = (
            result[f"untouched_2022_{metric}"] - result[f"development_2021_{metric}"]
        )

    def classify(row: pd.Series) -> str:
        if row["untouched_2022_full_evaluable_alerts"] < 25:
            return "INSUFFICIENT_SAMPLE"
        precision_delta = row["delta_2022_minus_2021_full_precision"]
        lift_delta = row["delta_2022_minus_2021_precision_improvement"]
        reversion_delta = row["delta_2022_minus_2021_full_reversion_rate"]
        retention_delta = row["delta_2022_minus_2021_full_median_retention"]
        if (
            precision_delta <= -0.10
            or lift_delta <= -0.10
            or reversion_delta >= 0.10
            or retention_delta <= -0.20
            or row["untouched_2022_precision_improvement"] < 0
        ):
            return "MATERIAL_DETERIORATION"
        if (
            abs(precision_delta) <= 0.10
            and abs(lift_delta) <= 0.10
            and reversion_delta < 0.10
            and retention_delta > -0.20
            and row["untouched_2022_precision_improvement"] >= 0
        ):
            return "STABLE_GENERALIZATION"
        return "MIXED_OR_UNCERTAIN"

    result["generalization_classification"] = result.apply(classify, axis=1)
    return result


def generalization_direction_table(
    alerts_2021: pd.DataFrame,
    alerts_2022: pd.DataFrame,
) -> pd.DataFrame:
    frames = []
    for period, data in (("redeveloped_2021", alerts_2021), ("untouched_2022", alerts_2022)):
        work = add_diagnostic_dimensions(data)
        summary = summarize_metrics(work, ["role_family", "method", "direction"])
        summary.insert(0, "period", period)
        frames.append(summary)
    return pd.concat(frames, ignore_index=True)


def release_gate_table(
    family_methods: pd.DataFrame,
    gates: dict[str, float],
    direction_generalization: pd.DataFrame,
) -> pd.DataFrame:
    primary = family_methods.loc[family_methods["partial_policy"].eq(PRIMARY_POLICY)]
    rows = []
    for family in ROLE_FAMILIES:
        full = primary.loc[
            primary["role_family"].eq(family) & primary["method"].eq("full_propwar")
        ].iloc[0]
        naive = primary.loc[
            primary["role_family"].eq(family) & primary["method"].eq("naive_spike")
        ].iloc[0]
        precision_improvement = full["precision"] - naive["precision"]
        reversion_improvement = naive["reversion_rate"] - full["reversion_rate"]
        direction_rows = direction_generalization.loc[
            direction_generalization["role_family"].eq(family)
            & direction_generalization["method"].isin(["full_propwar", "naive_spike"])
        ]
        direction_pivot = direction_rows.pivot_table(
            index=["period", "direction"], columns="method", values="precision"
        ).reindex(columns=["full_propwar", "naive_spike"])
        comparable = direction_pivot.dropna(subset=["full_propwar", "naive_spike"])
        direction_consistent = bool(
            len(comparable)
            and (comparable["full_propwar"] - comparable["naive_spike"]).ge(0).all()
        )
        checks = {
            "min_holdout_alerts": full["alerts"] >= gates["min_holdout_alerts"],
            "min_persistence_precision": full["precision"] >= gates["min_persistence_precision"],
            "min_absolute_improvement_vs_naive": precision_improvement >= gates["min_absolute_improvement_vs_naive"],
            "max_immediate_reversion_rate": full["reversion_rate"] <= gates["max_immediate_reversion_rate"],
            "min_reversion_improvement_vs_naive": reversion_improvement >= gates["min_reversion_improvement_vs_naive"],
            "min_median_retention": full["median_retention"] >= gates["min_median_retention"],
            "min_alerts_per_week": full["alerts"] / 18 >= gates["min_alerts_per_week"],
            "direction_consistent_across_periods": direction_consistent,
            "frozen_before_holdout": True,
        }
        if full["alerts"] < 25:
            status = "INSUFFICIENT_EVIDENCE"
        elif all(checks.values()):
            status = "PASSES_FOLD_2_POINT_GATES"
        else:
            status = "FAILS_FOLD_2_POINT_GATES"
        rows.append(
            {
                "role_family": family,
                "status": status,
                "alerts": int(full["alerts"]),
                "evaluable_alerts": int(full["evaluable_alerts"]),
                "precision": full["precision"],
                "naive_precision": naive["precision"],
                "precision_improvement": precision_improvement,
                "reversion_rate": full["reversion_rate"],
                "naive_reversion_rate": naive["reversion_rate"],
                "reversion_improvement": reversion_improvement,
                "median_retention": full["median_retention"],
                "alerts_per_week": full["alerts"] / 18,
                **{f"check_{name}": bool(value) for name, value in checks.items()},
                "failed_checks": " | ".join(name for name, value in checks.items() if not value),
            }
        )
    return pd.DataFrame(rows)
