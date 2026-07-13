from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from role_validation.diagnostics import add_diagnostic_dimensions, summarize_metrics
from role_validation.evaluation import summarize_alerts, summarize_method_comparisons
from role_validation.fold2 import (
    EXPECTED_METHODS,
    PARTIAL_POLICIES,
    PRIMARY_POLICY,
    assert_frozen_config_integrity,
    file_sha256,
)
from role_validation.redevelopment import ROLE_FAMILIES


FOLD3_SEASON = 2023
EXPECTED_CONFIG_SHA256 = "4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7"
FOLD3_CANDIDATE_DISPOSITION = {
    "rb_carry_share": "PRIMARY_CANDIDATE",
    "rb_opportunity_share": "SHADOW_CANDIDATE",
    "wr_target_share": "RETIRED_DESCRIPTIVE_ONLY",
    "te_target_share": "RETIRED_DESCRIPTIVE_ONLY",
}


def assert_fold3_config_integrity(
    config_path: Path,
    fold1_report_path: Path,
    fold2_frozen_copy: Path,
    fold2_fingerprint_path: Path,
) -> dict[str, Any]:
    base = assert_frozen_config_integrity(
        config_path,
        fold1_report_path,
        expected_sha256=EXPECTED_CONFIG_SHA256,
    )
    if config_path.read_bytes() != fold2_frozen_copy.read_bytes():
        raise AssertionError("Current config differs byte-for-byte from Fold 2 frozen copy")
    import json

    fold2_fingerprint = json.loads(fold2_fingerprint_path.read_text(encoding="utf-8"))
    checks = {
        **base["checks"],
        "byte_identical_to_fold2_frozen_copy": True,
        "fold2_fingerprint_matches": (
            fold2_fingerprint.get("config_sha256") == EXPECTED_CONFIG_SHA256
            and fold2_fingerprint.get("frozen_copy_sha256") == EXPECTED_CONFIG_SHA256
        ),
    }
    if not all(checks.values()):
        raise AssertionError("Fold 3 frozen configuration integrity failed")
    return {
        **base,
        "checks": checks,
        "fold2_frozen_copy_sha256": file_sha256(fold2_frozen_copy),
    }


def _period_family_result(alerts: pd.DataFrame, period: str) -> pd.DataFrame:
    method = summarize_alerts(alerts, bootstrap_iterations=2000)
    comparisons = summarize_method_comparisons(
        alerts,
        bootstrap_iterations=2000,
        confidence_level=0.95,
        seed=850,
    )
    full_ci = method.loc[
        method["method"].eq("full_propwar"),
        ["role_family", "precision_ci_low", "precision_ci_high"],
    ]
    result = comparisons.merge(full_ci, on="role_family", how="left", validate="one_to_one")
    result.insert(0, "period", period)
    return result


def cross_season_family_results(period_alerts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return pd.concat(
        [_period_family_result(alerts, period) for period, alerts in period_alerts.items()],
        ignore_index=True,
    )


def cross_season_direction_results(period_alerts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for period, alerts in period_alerts.items():
        work = add_diagnostic_dimensions(alerts)
        summary = summarize_metrics(work, ["role_family", "method", "direction"])
        full = summary.loc[summary["method"].eq("full_propwar")].set_index(
            ["role_family", "direction"]
        )
        naive = summary.loc[summary["method"].eq("naive_spike")].set_index(
            ["role_family", "direction"]
        )
        combined = full[
            ["alerts", "evaluable_alerts", "precision", "reversion_rate", "median_retention"]
        ].join(
            naive[["alerts", "evaluable_alerts", "precision", "reversion_rate", "median_retention"]],
            how="outer",
            lsuffix="_full",
            rsuffix="_naive",
        ).reset_index()
        combined["precision_improvement"] = (
            combined["precision_full"] - combined["precision_naive"]
        )
        combined["reversion_improvement"] = (
            combined["reversion_rate_naive"] - combined["reversion_rate_full"]
        )
        combined.insert(0, "period", period)
        rows.append(combined)
    return pd.concat(rows, ignore_index=True)


def cross_season_weekly_stability(period_alerts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for period, alerts in period_alerts.items():
        season_values = sorted(pd.to_numeric(alerts["season"], errors="raise").astype(int).unique())
        full = alerts.loc[alerts["method"].eq("full_propwar")]
        for family in ROLE_FAMILIES:
            family = str(family)
            group = full.loc[full["role_family"].eq(family)]
            counts = pd.DataFrame(
                [(season, week) for season in season_values for week in range(1, 19)],
                columns=["season", "week"],
            )
            observed = group.groupby(["season", "week"]).size().rename("alerts").reset_index()
            counts = counts.merge(observed, on=["season", "week"], how="left")
            counts["alerts"] = counts["alerts"].fillna(0).astype(int)
            rows.append(
                {
                    "period": period,
                    "role_family": family,
                    "seasons": "|".join(map(str, season_values)),
                    "season_weeks": len(counts),
                    "weekly_median": float(counts["alerts"].median()),
                    "weekly_maximum": int(counts["alerts"].max()),
                    "zero_alert_weeks": int(counts["alerts"].eq(0).sum()),
                    "active_weeks": int(counts["alerts"].gt(0).sum()),
                    "weekly_mean": float(counts["alerts"].mean()),
                }
            )
    return pd.DataFrame(rows)


def pooled_untouched_results(
    alerts_2022: pd.DataFrame,
    alerts_2023: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pooled = pd.concat([alerts_2022, alerts_2023], ignore_index=True)
    observed = set(pd.to_numeric(pooled["season"], errors="raise").astype(int).unique())
    if observed != {2022, 2023}:
        raise AssertionError(f"Pooled untouched data has seasons {sorted(observed)}")
    family = _period_family_result(pooled, "pooled_untouched_2022_2023")
    direction = cross_season_direction_results(
        {"pooled_untouched_2022_2023": pooled}
    )
    weekly = cross_season_weekly_stability(
        {"pooled_untouched_2022_2023": pooled}
    )
    return family, direction, weekly


def fold3_release_gate_table(
    family_methods_2023: pd.DataFrame,
    gates: dict[str, float],
    cross_season_directions: pd.DataFrame,
) -> pd.DataFrame:
    primary = family_methods_2023.loc[
        family_methods_2023["partial_policy"].eq(PRIMARY_POLICY)
    ]
    rows = []
    for family in ROLE_FAMILIES:
        full_rows = primary.loc[
            primary["role_family"].eq(family)
            & primary["method"].eq("full_propwar")
        ]
        naive_rows = primary.loc[
            primary["role_family"].eq(family)
            & primary["method"].eq("naive_spike")
        ]
        disposition = FOLD3_CANDIDATE_DISPOSITION[family]
        if full_rows.empty or naive_rows.empty:
            rows.append(
                {
                    "role_family": family,
                    "candidate_disposition": disposition,
                    "fold3_candidate_status": (
                        "INSUFFICIENT_EVIDENCE"
                        if disposition in {"PRIMARY_CANDIDATE", "SHADOW_CANDIDATE"}
                        else "NOT_APPLICABLE_RETIRED"
                    ),
                    "descriptive_locked_point_status": "INSUFFICIENT_EVIDENCE",
                    "alerts": 0,
                    "evaluable_alerts": 0,
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
        precision_improvement = full["precision"] - naive["precision"]
        reversion_improvement = naive["reversion_rate"] - full["reversion_rate"]
        directional = cross_season_directions.loc[
            cross_season_directions["role_family"].eq(family)
        ]
        comparable = directional.dropna(
            subset=["precision_full", "precision_naive"]
        )
        direction_consistent = bool(
            len(comparable)
            and comparable["precision_improvement"].ge(0).all()
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
        point_status = (
            "INSUFFICIENT_EVIDENCE"
            if full["alerts"] < 25
            else (
                "PASSES_FOLD_3_POINT_GATES"
                if all(checks.values())
                else "FAILS_FOLD_3_POINT_GATES"
            )
        )
        candidate_status = (
            point_status
            if disposition in {"PRIMARY_CANDIDATE", "SHADOW_CANDIDATE"}
            else "NOT_APPLICABLE_RETIRED"
        )
        rows.append(
            {
                "role_family": family,
                "candidate_disposition": disposition,
                "fold3_candidate_status": candidate_status,
                "descriptive_locked_point_status": point_status,
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
