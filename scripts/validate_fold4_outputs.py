from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import nbformat
import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_4"
NOTEBOOK = ROOT / "notebooks" / "fold_4_untouched_2024_validation.ipynb"
sys.path.insert(0, str(ROOT / "src"))

from role_validation.fold2 import (  # noqa: E402
    PRIMARY_POLICY,
    comparison_results,
    method_results,
)
from role_validation.fold3 import cross_season_direction_results  # noqa: E402
from role_validation.fold4 import (  # noqa: E402
    ACTIVE_FAMILIES,
    EXPECTED_CONFIG_SHA256,
    fold4_release_gate_table,
    recommendation_table,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(left: object, right: object) -> bool:
    return bool(
        np.isclose(
            float(left), float(right), equal_nan=True, rtol=1e-10, atol=1e-12
        )
    )


def load_prior() -> dict[str, pd.DataFrame]:
    fold1 = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "recommended_candidate_partial_sensitivity_alerts_2018_2021.csv.gz",
        low_memory=False,
    )
    fold2 = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_2" / "fold2_alerts_2022.csv.gz",
        low_memory=False,
    )
    fold3 = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_3" / "fold3_alerts_2023.csv.gz",
        low_memory=False,
    )
    return {
        "redeveloped_2021": fold1.loc[
            fold1["season"].eq(2021)
            & fold1["partial_policy"].eq(PRIMARY_POLICY)
            & fold1["role_family"].isin(ACTIVE_FAMILIES)
        ].copy(),
        "untouched_2022": fold2.loc[
            fold2["partial_policy"].eq(PRIMARY_POLICY)
            & fold2["role_family"].isin(ACTIVE_FAMILIES)
        ].copy(),
        "untouched_2023": fold3.loc[
            fold3["partial_policy"].eq(PRIMARY_POLICY)
            & fold3["role_family"].isin(ACTIVE_FAMILIES)
        ].copy(),
    }


def main() -> int:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": str(detail)})

    required = [
        "frozen_execution_package_manifest.json",
        "frozen_role_change_fold4_candidate.yaml",
        "pre_run_manifest.json",
        "run_manifest.json",
        "fold4_execution_lock.json",
        "file_access_manifest.csv",
        "input_source_manifest.csv",
        "data_audit_2024.csv",
        "missingness_2024.csv",
        "data_audit_checks_2024.csv",
        "canonical_role_2024_enriched.csv.gz",
        "fold4_alerts_2024.csv.gz",
        "equal_volume_verification_2024.csv",
        "temporal_integrity_checks_2024.csv",
        "active_family_method_results_2024.csv",
        "active_family_comparisons_2024.csv",
        "direction_results_2024.csv",
        "weekly_stability_2024.csv",
        "subgroup_stability_2024.csv",
        "partial_game_sensitivity_2024.csv",
        "cross_season_family_2021_2024.csv",
        "pooled_untouched_family_2022_2023.csv",
        "pooled_untouched_family_2022_2024.csv",
        "fold4_gate_decisions.csv",
        "fold4_gate_details.csv",
        "fold4_family_recommendations.csv",
        "DATA_AUDIT_2024.md",
        "FOLD_4_REPORT.md",
    ]
    missing = [name for name in required if not (OUT / name).is_file()]
    check("required_artifacts", not missing, missing or f"{len(required)} present")

    frozen = json.loads(
        (OUT / "frozen_execution_package_manifest.json").read_text(encoding="utf-8")
    )
    package_mismatches = {
        name: (item["sha256"], sha256(ROOT / item["path"]))
        for name, item in frozen["files"].items()
        if item["sha256"] != sha256(ROOT / item["path"])
    }
    check("frozen_execution_hashes", not package_mismatches, package_mismatches or f"{len(frozen['files'])} matched")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()
    check("execution_package_commit", head == frozen["execution_package_commit"], head)
    current_config = ROOT / "config" / "role_change_fold2_candidate.yaml"
    check("candidate_config_hash", sha256(current_config) == EXPECTED_CONFIG_SHA256, sha256(current_config))
    check(
        "frozen_config_hash",
        sha256(OUT / "frozen_role_change_fold4_candidate.yaml") == EXPECTED_CONFIG_SHA256,
        sha256(OUT / "frozen_role_change_fold4_candidate.yaml"),
    )

    pre = json.loads((OUT / "pre_run_manifest.json").read_text(encoding="utf-8"))
    run = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))
    lock = json.loads((OUT / "fold4_execution_lock.json").read_text(encoding="utf-8"))
    check("pre_run_passed", bool(pre["passed"] and not pre["evaluation_executed"]), pre)
    check("single_execution_completed", bool(run["fold4_executed_once"] and lock["completed"]), lock)
    check("no_2025_results", not run["2025_results_used"], run["2025_results_used"])
    admitted_fields = [
        "seasons_admitted_to_feature_generation",
        "seasons_admitted_to_alert_selection",
        "seasons_admitted_to_outcome_evaluation",
    ]
    check(
        "season_admission_boundary",
        all(run[field] == [2024] for field in admitted_fields),
        {field: run[field] for field in admitted_fields},
    )
    check(
        "physical_access_reported",
        2025 in run["source_seasons_physically_opened"],
        run["source_seasons_physically_opened"],
    )

    source_manifest = pd.read_csv(OUT / "input_source_manifest.csv")
    source_hash_errors = []
    for row in source_manifest.dropna(subset=["sha256"]).itertuples(index=False):
        path = Path(row.path)
        if not path.is_absolute():
            path = ROOT / path
        observed = sha256(path)
        if observed != row.sha256:
            source_hash_errors.append(f"{row.source}: {observed} != {row.sha256}")
    check("input_source_hashes", not source_hash_errors, source_hash_errors or f"{len(source_manifest)} inputs")

    audit_checks = pd.read_csv(OUT / "data_audit_checks_2024.csv")
    check("data_audit_checks", bool(audit_checks["passed"].all()), audit_checks.to_dict(orient="records"))
    canonical = pd.read_csv(OUT / "canonical_role_2024_enriched.csv.gz", low_memory=False)
    key = ["season", "week", "player_id", "team", "role_family"]
    check("canonical_2024_only", set(canonical["season"].astype(int).unique()) == {2024}, sorted(canonical["season"].unique()))
    check("canonical_grain", not canonical.duplicated(key, keep=False).any(), int(canonical.duplicated(key, keep=False).sum()))

    alerts = pd.read_csv(OUT / "fold4_alerts_2024.csv.gz", low_memory=False)
    check("alerts_2024_only", set(alerts["season"].astype(int).unique()) == {2024}, sorted(alerts["season"].unique()))
    check("active_families_only", set(alerts["role_family"].unique()) == set(ACTIVE_FAMILIES), sorted(alerts["role_family"].unique()))
    alert_key = ["partial_policy", "role_family", "method", "season", "week", "player_id", "team"]
    check("alert_grain_unique", not alerts.duplicated(alert_key, keep=False).any(), int(alerts.duplicated(alert_key, keep=False).sum()))
    check(
        "primary_excludes_confirmed_partial",
        not alerts.loc[
            alerts["partial_policy"].eq(PRIMARY_POLICY), "confirmed_partial_game"
        ].fillna(False).astype(bool).any(),
        "no confirmed primary alerts",
    )

    equal = pd.read_csv(OUT / "equal_volume_verification_2024.csv")
    check("equal_volume_manifest", len(equal) == 108 and bool(equal["equal_volume"].all()), f"{len(equal)} cells")
    counts = alerts.groupby(["partial_policy", "role_family", "week", "method"]).size().unstack("method", fill_value=0)
    check("equal_volume_recomputed", bool(counts.nunique(axis=1).eq(1).all()), f"{len(counts)} nonzero cells")
    temporal = pd.read_csv(OUT / "temporal_integrity_checks_2024.csv")
    check("temporal_manifest", bool(temporal["passed"].all()), temporal.to_dict(orient="records"))
    check("baseline_before_confirmation", bool((alerts["baseline_max_week"] < alerts["confirmation_start_week"]).all()), "strict")
    check("confirmation_ends_on_alert", bool(alerts["confirmation_end_week"].eq(alerts["week"]).all()), "exact")
    future = alerts.loc[alerts["future_week_1"].notna()]
    check("future_after_alert", bool(future["future_week_1"].gt(future["week"]).all()), f"{len(future)} rows")

    committed_methods = pd.read_csv(OUT / "active_family_method_results_2024.csv")
    recomputed_methods = method_results(alerts)
    method_merge = committed_methods.merge(
        recomputed_methods,
        on=["partial_policy", "role_family", "method"],
        suffixes=("_stored", "_recomputed"),
        validate="one_to_one",
    )
    method_discrepancies = []
    for metric in [
        "alerts", "evaluable_alerts", "persistent_alerts", "precision",
        "precision_ci_low", "precision_ci_high", "reversion_rate", "median_retention",
    ]:
        mismatched = ~np.isclose(
            pd.to_numeric(method_merge[f"{metric}_stored"], errors="coerce"),
            pd.to_numeric(method_merge[f"{metric}_recomputed"], errors="coerce"),
            equal_nan=True,
            rtol=1e-10,
            atol=1e-12,
        )
        if mismatched.any():
            method_discrepancies.append(metric)
    check("method_metrics_recomputed", not method_discrepancies, method_discrepancies or f"{len(method_merge)} rows")

    committed_comparisons = pd.read_csv(OUT / "active_family_comparisons_2024.csv")
    recomputed_comparisons = comparison_results(alerts)
    comparison_merge = committed_comparisons.merge(
        recomputed_comparisons,
        on=["partial_policy", "role_family"],
        suffixes=("_stored", "_recomputed"),
        validate="one_to_one",
    )
    comparison_discrepancies = []
    for metric in [
        "full_alerts", "full_evaluable_alerts", "full_precision", "naive_precision",
        "precision_improvement", "precision_improvement_ci_low",
        "precision_improvement_ci_high", "full_reversion_rate",
        "reversion_improvement", "full_median_retention",
    ]:
        mismatched = ~np.isclose(
            pd.to_numeric(comparison_merge[f"{metric}_stored"], errors="coerce"),
            pd.to_numeric(comparison_merge[f"{metric}_recomputed"], errors="coerce"),
            equal_nan=True,
            rtol=1e-10,
            atol=1e-12,
        )
        if mismatched.any():
            comparison_discrepancies.append(metric)
    check("comparison_metrics_recomputed", not comparison_discrepancies, comparison_discrepancies or f"{len(comparison_merge)} rows")

    prior = load_prior()
    primary_current = alerts.loc[alerts["partial_policy"].eq(PRIMARY_POLICY)].copy()
    pooled = pd.concat(
        [prior["untouched_2022"], prior["untouched_2023"], primary_current],
        ignore_index=True,
    )
    stored_pooled = pd.read_csv(OUT / "pooled_untouched_family_2022_2024.csv")
    pooled_discrepancies = []
    for family in ACTIVE_FAMILIES:
        group = pooled.loc[pooled["role_family"].eq(family)]
        full = group.loc[group["method"].eq("full_propwar")]
        naive = group.loc[group["method"].eq("naive_spike")]
        row = stored_pooled.loc[stored_pooled["role_family"].eq(family)].iloc[0]
        full_eval = full["persistent"].notna()
        naive_eval = naive["persistent"].notna()
        raw = {
            "full_alerts": len(full),
            "full_evaluable_alerts": int(full_eval.sum()),
            "full_precision": full.loc[full_eval, "persistent"].astype(float).mean(),
            "naive_alerts": len(naive),
            "naive_evaluable_alerts": int(naive_eval.sum()),
            "naive_precision": naive.loc[naive_eval, "persistent"].astype(float).mean(),
        }
        for metric, value in raw.items():
            if not close(value, row[metric]):
                pooled_discrepancies.append(f"{family}/{metric}")
    check("pooled_raw_recomputed", not pooled_discrepancies, pooled_discrepancies or "2022-2024 raw numerators matched")

    config = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )
    periods = {**prior, "untouched_2024": primary_current}
    cross_direction = cross_season_direction_results(periods)
    recomputed_gates = fold4_release_gate_table(
        committed_methods,
        config["release_gates"]["full_release"],
        cross_direction,
    )
    stored_gates = pd.read_csv(OUT / "fold4_gate_decisions.csv")
    status_compare = stored_gates.merge(
        recomputed_gates,
        on="role_family",
        suffixes=("_stored", "_recomputed"),
        validate="one_to_one",
    )
    check(
        "gate_statuses_recomputed",
        bool(status_compare["fold4_candidate_status_stored"].eq(status_compare["fold4_candidate_status_recomputed"]).all()),
        status_compare[["role_family", "fold4_candidate_status_stored", "fold4_candidate_status_recomputed"]].to_dict(orient="records"),
    )
    recomputed_recommendations = recommendation_table(stored_gates, integrity_passed=True)
    stored_recommendations = pd.read_csv(OUT / "fold4_family_recommendations.csv")
    recommendation_compare = stored_recommendations.merge(
        recomputed_recommendations,
        on="role_family",
        suffixes=("_stored", "_recomputed"),
        validate="one_to_one",
    )
    check(
        "recommendations_recomputed",
        bool(recommendation_compare["recommendation_stored"].eq(recommendation_compare["recommendation_recomputed"]).all()),
        recommendation_compare[["role_family", "recommendation_stored", "recommendation_recomputed"]].to_dict(orient="records"),
    )

    dimensions = set(pd.read_csv(OUT / "subgroup_stability_2024.csv")["dimension"])
    required_dimensions = {
        "week_block", "player", "team", "absolute_role_change",
        "player_opportunity_count", "team_denominator", "baseline_stability",
    }
    check("subgroup_dimensions", required_dimensions.issubset(dimensions), sorted(dimensions))
    check("alert_archive_hash", sha256(OUT / "fold4_alerts_2024.csv.gz") == lock["alert_archive_sha256"], lock["alert_archive_sha256"])

    if NOTEBOOK.is_file():
        notebook = nbformat.read(NOTEBOOK, as_version=4)
        code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
        errors = [
            output
            for cell in code_cells
            for output in cell.get("outputs", [])
            if output.get("output_type") == "error"
        ]
        notebook_ok = bool(code_cells) and all(
            cell.get("execution_count") is not None for cell in code_cells
        ) and not errors
        detail = f"{len(code_cells)} code cells; {len(errors)} errors"
    else:
        notebook_ok = False
        detail = "notebook missing"
    check("notebook_executed", notebook_ok, detail)

    report = (OUT / "FOLD_4_REPORT.md").read_text(encoding="utf-8")
    expected_recommendations = set(stored_recommendations["recommendation"])
    check("report_recommendations", all(value in report for value in expected_recommendations), sorted(expected_recommendations))
    staged_dashboard = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "dashboard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    check("staged_dashboard_unchanged", staged_dashboard == "", staged_dashboard or "none")
    check("no_execution_failure", not (OUT / "execute_failure.json").exists(), "absent")

    result = {
        "validator": "independent_fold4_output_validator",
        "passed": all(bool(item["passed"]) for item in checks),
        "checks_passed": sum(bool(item["passed"]) for item in checks),
        "checks_total": len(checks),
        "test_season": 2024,
        "2025_results_used": False,
        "fold4_executed_once": True,
        "checks": checks,
    }
    (OUT / "final_validation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
