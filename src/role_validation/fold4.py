from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from role_validation.diagnostics import add_diagnostic_dimensions, summarize_metrics
from role_validation.fold2 import PRIMARY_POLICY, file_sha256
from role_validation.fold3 import (
    assert_fold3_config_integrity,
    cross_season_direction_results,
    cross_season_family_results,
    cross_season_weekly_stability,
)
from role_validation.redevelopment import FEED_KEY


FOLD4_SEASON = 2024
EXPECTED_CONFIG_SHA256 = "4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7"
ACTIVE_FAMILIES = ("rb_carry_share", "rb_opportunity_share")
RETIRED_FAMILIES = ("wr_target_share", "te_target_share")
FOLD4_CANDIDATE_DISPOSITION = {
    "rb_carry_share": "PRIMARY_CANDIDATE",
    "rb_opportunity_share": "SHADOW_CANDIDATE",
    "wr_target_share": "RETIRED_DESCRIPTIVE_ONLY",
    "te_target_share": "RETIRED_DESCRIPTIVE_ONLY",
}


def assert_fold4_config_integrity(
    config_path: Path,
    fold1_report_path: Path,
    fold2_frozen_copy: Path,
    fold2_fingerprint_path: Path,
    fold3_frozen_copy: Path,
    fold3_fingerprint_path: Path,
) -> dict[str, Any]:
    base = assert_fold3_config_integrity(
        config_path,
        fold1_report_path,
        fold2_frozen_copy,
        fold2_fingerprint_path,
    )
    fold3_fingerprint = json.loads(fold3_fingerprint_path.read_text(encoding="utf-8"))
    checks = {
        **base["checks"],
        "byte_identical_to_fold3_frozen_copy": (
            config_path.read_bytes() == fold3_frozen_copy.read_bytes()
        ),
        "fold3_fingerprint_matches": (
            fold3_fingerprint.get("config_sha256") == EXPECTED_CONFIG_SHA256
            and fold3_fingerprint.get("frozen_copy_sha256") == EXPECTED_CONFIG_SHA256
        ),
    }
    if not all(checks.values()):
        raise AssertionError("Fold 4 frozen configuration integrity failed")
    return {
        **base,
        "checks": checks,
        "fold3_frozen_copy_sha256": file_sha256(fold3_frozen_copy),
    }


def pooled_period_results(
    alert_sets: Iterable[pd.DataFrame],
    *,
    period: str,
    expected_seasons: Iterable[int],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pooled = pd.concat(list(alert_sets), ignore_index=True)
    observed = set(pd.to_numeric(pooled["season"], errors="raise").astype(int).unique())
    expected = {int(season) for season in expected_seasons}
    if observed != expected:
        raise AssertionError(
            f"{period} has seasons {sorted(observed)}; expected {sorted(expected)}"
        )
    family = cross_season_family_results({period: pooled})
    direction = cross_season_direction_results({period: pooled})
    weekly = cross_season_weekly_stability({period: pooled})
    return family, direction, weekly


def fold4_release_gate_table(
    family_methods_2024: pd.DataFrame,
    gates: dict[str, float],
    cross_season_directions: pd.DataFrame,
) -> pd.DataFrame:
    primary = family_methods_2024.loc[
        family_methods_2024["partial_policy"].eq(PRIMARY_POLICY)
    ]
    rows: list[dict[str, Any]] = []
    for family, disposition in FOLD4_CANDIDATE_DISPOSITION.items():
        if family in RETIRED_FAMILIES:
            rows.append(
                {
                    "role_family": family,
                    "candidate_disposition": disposition,
                    "fold4_candidate_status": "NOT_APPLICABLE_RETIRED",
                    "alerts": 0,
                    "evaluable_alerts": 0,
                    "persistent_alerts": 0,
                    "precision": np.nan,
                    "naive_precision": np.nan,
                    "precision_improvement": np.nan,
                    "reversion_rate": np.nan,
                    "naive_reversion_rate": np.nan,
                    "reversion_improvement": np.nan,
                    "median_retention": np.nan,
                    "alerts_per_week": 0.0,
                    "failed_checks": "retired_before_fold4",
                }
            )
            continue
        full_rows = primary.loc[
            primary["role_family"].eq(family)
            & primary["method"].eq("full_propwar")
        ]
        naive_rows = primary.loc[
            primary["role_family"].eq(family)
            & primary["method"].eq("naive_spike")
        ]
        if len(full_rows) != 1 or len(naive_rows) != 1:
            rows.append(
                {
                    "role_family": family,
                    "candidate_disposition": disposition,
                    "fold4_candidate_status": "INSUFFICIENT_EVIDENCE",
                    "alerts": 0,
                    "evaluable_alerts": 0,
                    "persistent_alerts": 0,
                    "precision": np.nan,
                    "naive_precision": np.nan,
                    "precision_improvement": np.nan,
                    "reversion_rate": np.nan,
                    "naive_reversion_rate": np.nan,
                    "reversion_improvement": np.nan,
                    "median_retention": np.nan,
                    "alerts_per_week": 0.0,
                    "failed_checks": "missing_method_output | min_holdout_alerts",
                }
            )
            continue
        full = full_rows.iloc[0]
        naive = naive_rows.iloc[0]
        precision_improvement = float(full["precision"] - naive["precision"])
        reversion_improvement = float(
            naive["reversion_rate"] - full["reversion_rate"]
        )
        comparable = cross_season_directions.loc[
            cross_season_directions["role_family"].eq(family)
        ].dropna(subset=["precision_full", "precision_naive"])
        direction_consistent = bool(
            len(comparable) and comparable["precision_improvement"].ge(0).all()
        )
        checks = {
            "min_holdout_alerts": full["alerts"] >= gates["min_holdout_alerts"],
            "min_persistence_precision": (
                full["precision"] >= gates["min_persistence_precision"]
            ),
            "min_absolute_improvement_vs_naive": (
                precision_improvement >= gates["min_absolute_improvement_vs_naive"]
            ),
            "max_immediate_reversion_rate": (
                full["reversion_rate"] <= gates["max_immediate_reversion_rate"]
            ),
            "min_reversion_improvement_vs_naive": (
                reversion_improvement >= gates["min_reversion_improvement_vs_naive"]
            ),
            "min_median_retention": (
                full["median_retention"] >= gates["min_median_retention"]
            ),
            "min_alerts_per_week": (
                full["alerts"] / 18 >= gates["min_alerts_per_week"]
            ),
            "direction_consistent_across_periods": direction_consistent,
            "frozen_before_holdout": True,
        }
        status = (
            "INSUFFICIENT_EVIDENCE"
            if full["alerts"] < 25
            else (
                "PASSES_FOLD_4_POINT_GATES"
                if all(checks.values())
                else "FAILS_FOLD_4_POINT_GATES"
            )
        )
        rows.append(
            {
                "role_family": family,
                "candidate_disposition": disposition,
                "fold4_candidate_status": status,
                "alerts": int(full["alerts"]),
                "evaluable_alerts": int(full["evaluable_alerts"]),
                "persistent_alerts": int(full["persistent_alerts"]),
                "precision": full["precision"],
                "naive_precision": naive["precision"],
                "precision_improvement": precision_improvement,
                "reversion_rate": full["reversion_rate"],
                "naive_reversion_rate": naive["reversion_rate"],
                "reversion_improvement": reversion_improvement,
                "median_retention": full["median_retention"],
                "alerts_per_week": full["alerts"] / 18,
                **{f"check_{name}": bool(value) for name, value in checks.items()},
                "failed_checks": " | ".join(
                    name for name, value in checks.items() if not value
                ),
            }
        )
    return pd.DataFrame(rows)


def gate_detail_table(
    decisions: pd.DataFrame, gates: dict[str, float]
) -> pd.DataFrame:
    definitions = [
        ("min_holdout_alerts", "alerts", f">= {gates['min_holdout_alerts']}"),
        (
            "min_persistence_precision",
            "precision",
            f">= {gates['min_persistence_precision']}",
        ),
        (
            "min_absolute_improvement_vs_naive",
            "precision_improvement",
            f">= {gates['min_absolute_improvement_vs_naive']}",
        ),
        (
            "max_immediate_reversion_rate",
            "reversion_rate",
            f"<= {gates['max_immediate_reversion_rate']}",
        ),
        (
            "min_reversion_improvement_vs_naive",
            "reversion_improvement",
            f">= {gates['min_reversion_improvement_vs_naive']}",
        ),
        (
            "min_median_retention",
            "median_retention",
            f">= {gates['min_median_retention']}",
        ),
        (
            "min_alerts_per_week",
            "alerts_per_week",
            f">= {gates['min_alerts_per_week']}",
        ),
        (
            "direction_consistent_across_periods",
            "check_direction_consistent_across_periods",
            "all available period-direction lifts >= 0",
        ),
        ("frozen_before_holdout", "check_frozen_before_holdout", "required"),
    ]
    rows = []
    for row in decisions.loc[decisions["role_family"].isin(ACTIVE_FAMILIES)].itertuples(
        index=False
    ):
        values = row._asdict()
        for gate, observed_column, threshold in definitions:
            rows.append(
                {
                    "role_family": row.role_family,
                    "gate": gate,
                    "observed": values.get(observed_column),
                    "threshold": threshold,
                    "passed": bool(values.get(f"check_{gate}", False)),
                }
            )
    return pd.DataFrame(rows)


def recommendation_table(
    decisions: pd.DataFrame, *, integrity_passed: bool
) -> pd.DataFrame:
    by_family = decisions.set_index("role_family")
    rows = []
    for family in ACTIVE_FAMILIES:
        status = by_family.at[family, "fold4_candidate_status"]
        if not integrity_passed:
            recommendation = "INTEGRITY_BLOCKER"
        elif family == "rb_carry_share":
            recommendation = (
                "ADVANCE_UNCHANGED_TO_FINAL_2025_HOLDOUT"
                if status == "PASSES_FOLD_4_POINT_GATES"
                else "CONTINUE_SHADOW_ONLY"
            )
        else:
            recommendation = (
                "ADVANCE_UNCHANGED_TO_FINAL_2025_HOLDOUT_AS_SHADOW"
                if status == "PASSES_FOLD_4_POINT_GATES"
                else "CONTINUE_SHADOW_ONLY_WITHOUT_HOLDOUT_CLAIM"
            )
        rows.append(
            {
                "role_family": family,
                "fold4_status": status,
                "recommendation": recommendation,
            }
        )
    rows.extend(
        [
            {
                "role_family": "wr_target_share",
                "fold4_status": "NOT_APPLICABLE_RETIRED",
                "recommendation": "REMAIN_RETIRED",
            },
            {
                "role_family": "te_target_share",
                "fold4_status": "NOT_APPLICABLE_RETIRED",
                "recommendation": "REMAIN_RETIRED",
            },
        ]
    )
    return pd.DataFrame(rows)


def subgroup_stability(alerts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = add_diagnostic_dimensions(alerts).copy()
    work = work.loc[
        work["partial_policy"].eq(PRIMARY_POLICY)
        & work["role_family"].isin(ACTIVE_FAMILIES)
        & work["method"].isin(["full_propwar", "naive_spike"])
    ].copy()
    work["baseline_stability_gap"] = (
        pd.to_numeric(work["recent_baseline_value"], errors="coerce")
        - pd.to_numeric(work["season_baseline_value"], errors="coerce")
    ).abs()
    thresholds = (
        work.loc[work["method"].eq("full_propwar")]
        .groupby("role_family", as_index=False)["baseline_stability_gap"]
        .median()
        .rename(columns={"baseline_stability_gap": "median_gap_threshold"})
    )
    work = work.merge(thresholds, on="role_family", how="left", validate="many_to_one")
    work["baseline_stability"] = np.where(
        work["baseline_stability_gap"].le(work["median_gap_threshold"]),
        "low_gap_more_stable",
        "high_gap_less_stable",
    )
    dimensions = {
        "week_block": "week_block",
        "player": "player_id",
        "team": "team",
        "absolute_role_change": "absolute_detected_change_bin",
        "player_opportunity_count": "raw_player_opportunities_bin",
        "team_denominator": "team_opportunity_denominator_bin",
        "baseline_stability": "baseline_stability",
    }
    outputs = []
    for dimension, column in dimensions.items():
        summary = summarize_metrics(work, ["role_family", "method", column])
        summary = summary.rename(columns={column: "segment"})
        summary.insert(2, "dimension", dimension)
        outputs.append(summary)
    return pd.concat(outputs, ignore_index=True), thresholds


def concentration_tables(alerts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    full = alerts.loc[
        alerts["partial_policy"].eq(PRIMARY_POLICY)
        & alerts["method"].eq("full_propwar")
        & alerts["role_family"].isin(ACTIVE_FAMILIES)
    ].copy()
    entity_parts = []
    summary_rows = []
    for family, family_group in full.groupby("role_family", sort=True):
        for dimension, column in [("player", "player_id"), ("team", "team")]:
            entity = summarize_metrics(family_group, [column]).rename(
                columns={column: "entity"}
            )
            entity.insert(0, "dimension", dimension)
            entity.insert(0, "role_family", family)
            entity = entity.sort_values(["alerts", "entity"], ascending=[False, True])
            entity["alert_share"] = entity["alerts"] / len(family_group)
            entity["rank"] = range(1, len(entity) + 1)
            entity_parts.append(entity)
            shares = entity["alert_share"].astype(float)
            hhi = float((shares**2).sum())
            summary_rows.append(
                {
                    "role_family": family,
                    "dimension": dimension,
                    "alerts": len(family_group),
                    "unique_entities": len(entity),
                    "top_entity": entity.iloc[0]["entity"] if len(entity) else None,
                    "top_entity_alerts": int(entity.iloc[0]["alerts"]) if len(entity) else 0,
                    "top_entity_share": float(entity.iloc[0]["alert_share"]) if len(entity) else np.nan,
                    "hhi": hhi,
                    "effective_entities": 1 / hhi if hhi else np.nan,
                }
            )
    return pd.concat(entity_parts, ignore_index=True), pd.DataFrame(summary_rows)


def overlap_dependence(alerts: pd.DataFrame) -> pd.DataFrame:
    full = add_diagnostic_dimensions(
        alerts.loc[
            alerts["partial_policy"].eq(PRIMARY_POLICY)
            & alerts["method"].eq("full_propwar")
            & alerts["role_family"].isin(ACTIVE_FAMILIES)
        ].copy()
    )
    carry_keys = set(
        map(
            tuple,
            full.loc[full["role_family"].eq("rb_carry_share"), FEED_KEY].itertuples(
                index=False, name=None
            ),
        )
    )
    opportunity_keys = set(
        map(
            tuple,
            full.loc[
                full["role_family"].eq("rb_opportunity_share"), FEED_KEY
            ].itertuples(index=False, name=None),
        )
    )
    overlap = carry_keys & opportunity_keys
    full["overlap_status"] = [
        "overlapping_rb_family" if tuple(row) in overlap else "family_only"
        for row in full[FEED_KEY].itertuples(index=False, name=None)
    ]
    return summarize_metrics(full, ["role_family", "overlap_status"])


def retention_diagnostics(alerts: pd.DataFrame) -> pd.DataFrame:
    full = alerts.loc[
        alerts["partial_policy"].eq(PRIMARY_POLICY)
        & alerts["method"].eq("full_propwar")
        & alerts["role_family"].isin(ACTIVE_FAMILIES)
        & alerts["persistent"].notna()
    ].copy()
    rows = []
    for family, group in full.groupby("role_family", sort=True):
        values = pd.to_numeric(group["retention"], errors="coerce").dropna().sort_values()
        trim = int(np.floor(len(values) * 0.10))
        trimmed = values.iloc[trim : len(values) - trim] if trim and len(values) > 2 * trim else values
        rows.append(
            {
                "role_family": family,
                "evaluable_retention_values": len(values),
                "minimum": values.min(),
                "p05": values.quantile(0.05),
                "median": values.median(),
                "mean": values.mean(),
                "trimmed_mean_10pct": trimmed.mean(),
                "clipped_0_1_mean": values.clip(0, 1).mean(),
                "p95": values.quantile(0.95),
                "maximum": values.max(),
            }
        )
    return pd.DataFrame(rows)


def partial_alert_status(alerts: pd.DataFrame) -> pd.DataFrame:
    work = add_diagnostic_dimensions(alerts)
    work = work.loc[
        work["partial_policy"].eq(PRIMARY_POLICY)
        & work["role_family"].isin(ACTIVE_FAMILIES)
    ]
    return summarize_metrics(
        work, ["role_family", "method", "partial_game_status"]
    )
