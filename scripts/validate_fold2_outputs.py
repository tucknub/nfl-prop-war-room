from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

import nbformat
import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "outputs" / "role_validation" / "fold_2"
sys.path.insert(0, str(ROOT / "src"))

from role_validation.fold2 import (  # noqa: E402
    EXPECTED_METHODS,
    PARTIAL_POLICIES,
    PRIMARY_POLICY,
    assert_frozen_config_integrity,
    canonical_audit,
    comparison_results,
    generalization_direction_table,
    method_results,
    release_gate_table,
)
from role_validation.redevelopment import CANONICAL_KEY, ROLE_FAMILIES  # noqa: E402


EXPECTED_CONFIG_SHA256 = "4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7"
EXPECTED_START_COMMIT = "bdff056fa625eef76152e1b9f3ef0e88fda2bbab"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Independently validate Fold 2 artifacts.")
    parser.add_argument("--require-staged-scope", action="store_true")
    return parser.parse_args()


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(OUTPUT / name, low_memory=False)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def assert_close(left: pd.Series, right: pd.Series, label: str) -> None:
    if not np.allclose(
        pd.to_numeric(left, errors="coerce"),
        pd.to_numeric(right, errors="coerce"),
        equal_nan=True,
        atol=1e-12,
        rtol=1e-12,
    ):
        raise AssertionError(f"Recomputed {label} differs from saved output")


def main() -> int:
    args = parse_args()
    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        passed = bool(condition)
        checks.append({"check": name, "passed": passed, "detail": detail})
        if not passed:
            raise AssertionError(f"{name}: {detail}")

    required = [
        "frozen_role_change_fold2_candidate.yaml",
        "frozen_config_fingerprint.json",
        "pre_run_manifest.json",
        "fold2_execution_lock.json",
        "run_manifest.json",
        "data_audit_2022.csv",
        "DATA_AUDIT_2022.md",
        "missingness_2022.csv",
        "source_coverage_2022.csv",
        "join_coverage_2022.csv",
        "partial_game_evidence_2022.csv",
        "partial_game_source_coverage_2022.csv",
        "canonical_role_2022_enriched.csv.gz",
        "exclusions_2022.csv",
        "input_source_manifest.csv",
        "pre_execution_test_results.txt",
        "fold2_alerts_2022.csv.gz",
        "equal_volume_verification_2022.csv",
        "repeat_suppressed_alerts_2022.csv",
        "temporal_integrity_checks_2022.csv",
        "family_method_results_2022.csv",
        "family_comparisons_2022.csv",
        "direction_results_2022.csv",
        "season_block_results_2022.csv",
        "weekly_stability_2022.csv",
        "deduplicated_feed_summary_2022.csv",
        "deduplicated_weekly_volume_2022.csv",
        "repeat_alert_rates_2022.csv",
        "rb_family_overlap_2022.csv",
        "generalization_2021_vs_2022.csv",
        "generalization_direction_2021_vs_2022.csv",
        "generalization_direction_direct_2021_vs_2022.csv",
        "partial_game_sensitivity_2022.csv",
        "release_gate_results_2022.csv",
        "FOLD_2_REPORT.md",
    ]
    missing = [name for name in required if not (OUTPUT / name).exists()]
    check("required_artifacts_present", not missing, f"missing={missing}")

    integrity = assert_frozen_config_integrity(
        ROOT / "config" / "role_change_fold2_candidate.yaml",
        ROOT
        / "outputs"
        / "role_validation"
        / "fold_1_diagnostics"
        / "FOLD_1_DIAGNOSTIC_AND_REDEVELOPMENT_REPORT.md",
        expected_sha256=EXPECTED_CONFIG_SHA256,
    )
    check("config_integrity", all(integrity["checks"].values()))
    check(
        "frozen_copy_byte_identical",
        (OUTPUT / "frozen_role_change_fold2_candidate.yaml").read_bytes()
        == (ROOT / "config" / "role_change_fold2_candidate.yaml").read_bytes(),
    )
    check("config_clean_vs_head", not git("diff", "--name-only", "HEAD", "--", "config/role_change_fold2_candidate.yaml"))
    check("pre_fold2_tag", git("rev-list", "-n", "1", "role-change-validation-v1-pre-fold2-checkpoint") == EXPECTED_START_COMMIT)

    lock = json.loads((OUTPUT / "fold2_execution_lock.json").read_text(encoding="utf-8"))
    check("execution_lock_completed", lock.get("completed") is True)
    check("execution_locked_to_2022", lock.get("season") == 2022)
    check("execution_locked_to_config", lock.get("config_sha256") == EXPECTED_CONFIG_SHA256)
    check("alert_archive_hash", lock.get("alert_archive_sha256") == digest(OUTPUT / "fold2_alerts_2022.csv.gz"))

    alerts = read("fold2_alerts_2022.csv.gz")
    equal = read("equal_volume_verification_2022.csv")
    enriched = read("canonical_role_2022_enriched.csv.gz")
    check("alerts_2022_only", set(alerts["season"].astype(int).unique()) == {2022})
    check("canonical_2022_only", set(enriched["season"].astype(int).unique()) == {2022})
    check("partial_policies_exact", set(alerts["partial_policy"].unique()) == set(PARTIAL_POLICIES))
    check("methods_exact", set(alerts["method"].unique()) == set(EXPECTED_METHODS))
    check("families_exact", set(alerts["role_family"].unique()) == set(ROLE_FAMILIES))
    check("canonical_unique_key", not enriched.duplicated(CANONICAL_KEY).any())

    validation_config = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )
    audit = canonical_audit(enriched, validation_config["data"]["required_columns"])
    saved_audit = read("data_audit_2022.csv")
    check("canonical_row_count_recomputed", int(audit.at[0, "canonical_rows"]) == int(saved_audit.at[0, "canonical_rows"]))
    check("canonical_required_nulls_zero", int(audit.at[0, "required_null_cells"]) == 0)
    check("canonical_identity_full", float(audit.at[0, "identity_coverage"]) == 1.0)

    count_columns = [f"{method}_count" for method in EXPECTED_METHODS]
    check("equal_volume_rows", len(equal) == len(PARTIAL_POLICIES) * len(ROLE_FAMILIES) * 18)
    check("equal_volume_all", equal["equal_volume"].fillna(False).astype(bool).all())
    check("equal_volume_method_count", equal["observed_method_count"].eq(len(EXPECTED_METHODS)).all())
    check("equal_volume_counts_match", equal[count_columns].nunique(axis=1).eq(1).all())

    temporal = read("temporal_integrity_checks_2022.csv")
    check("temporal_checks_all", temporal["passed"].fillna(False).astype(bool).all())
    primary_full = alerts.loc[
        alerts["partial_policy"].eq(PRIMARY_POLICY)
        & alerts["method"].eq("full_propwar")
    ]
    check("baseline_before_confirmation", primary_full["baseline_max_week"].lt(primary_full["confirmation_start_week"]).all())
    check("confirmation_ends_at_alert", primary_full["confirmation_end_week"].eq(primary_full["week"]).all())
    evaluable = primary_full.loc[primary_full["future_n"].ge(2)]
    check("outcomes_after_alert", evaluable["future_week_1"].gt(evaluable["week"]).all() and evaluable["future_week_2"].gt(evaluable["future_week_1"]).all())

    saved_methods = read("family_method_results_2022.csv").sort_values(
        ["partial_policy", "role_family", "method"]
    ).reset_index(drop=True)
    recomputed_methods = method_results(alerts).sort_values(
        ["partial_policy", "role_family", "method"]
    ).reset_index(drop=True)
    check("method_result_keys", saved_methods[["partial_policy", "role_family", "method"]].equals(recomputed_methods[["partial_policy", "role_family", "method"]]))
    for column in ["alerts", "evaluable_alerts", "precision", "precision_ci_low", "precision_ci_high", "reversion_rate", "median_retention"]:
        assert_close(saved_methods[column], recomputed_methods[column], column)
        checks.append({"check": f"recomputed_{column}", "passed": True, "detail": ""})

    saved_comparisons = read("family_comparisons_2022.csv").sort_values(
        ["partial_policy", "role_family"]
    ).reset_index(drop=True)
    recomputed_comparisons = comparison_results(alerts).sort_values(
        ["partial_policy", "role_family"]
    ).reset_index(drop=True)
    for column in ["full_alerts", "full_evaluable_alerts", "full_precision", "naive_precision", "precision_improvement", "precision_improvement_ci_low", "precision_improvement_ci_high", "full_reversion_rate", "reversion_improvement", "full_median_retention"]:
        assert_close(saved_comparisons[column], recomputed_comparisons[column], column)
        checks.append({"check": f"recomputed_comparison_{column}", "passed": True, "detail": ""})

    prior_alerts = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "recommended_candidate_partial_sensitivity_alerts_2018_2021.csv.gz",
        low_memory=False,
    )
    prior = prior_alerts.loc[
        prior_alerts["season"].eq(2021)
        & prior_alerts["partial_policy"].eq(PRIMARY_POLICY)
    ]
    direction = generalization_direction_table(
        prior,
        alerts.loc[alerts["partial_policy"].eq(PRIMARY_POLICY)],
    )
    recomputed_gates = release_gate_table(
        recomputed_methods,
        validation_config["release_gates"]["full_release"],
        direction,
    ).sort_values("role_family").reset_index(drop=True)
    saved_gates = read("release_gate_results_2022.csv").sort_values("role_family").reset_index(drop=True)
    check("release_status_recomputed", saved_gates["status"].equals(recomputed_gates["status"]))
    check("release_failures_recomputed", saved_gates["failed_checks"].fillna("").equals(recomputed_gates["failed_checks"].fillna("")))
    check("no_family_passes", not saved_gates["status"].eq("PASSES_FOLD_2_POINT_GATES").any())

    pretests = (OUTPUT / "pre_execution_test_results.txt").read_text(encoding="utf-8")
    check("pre_execution_tests_passed", "16 passed" in pretests)
    report = (OUTPUT / "FOLD_2_REPORT.md").read_text(encoding="utf-8")
    for heading in [
        "## Concise judgment", "## 2022 data audit", "## Family and method results",
        "## 2021 redevelopment versus untouched 2022", "## Partial-game sensitivity",
        "## Locked release-gate judgment", "## Recommended next action", "## Limitations",
    ]:
        check(f"report_section_{heading[3:].lower().replace(' ', '_')}", heading in report)
    check("report_no_validation_claim", "No family passes Fold 2 and none is validated." in report)
    check("report_no_post_2022_use", "No 2023–2025 result was read" in report)

    notebook_path = ROOT / "notebooks" / "fold_2_untouched_2022_validation.ipynb"
    notebook = nbformat.read(notebook_path, as_version=4)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    check("notebook_code_cells_executed", bool(code_cells) and all(cell.execution_count is not None for cell in code_cells))
    check("notebook_no_errors", not any(output.get("output_type") == "error" for cell in code_cells for output in cell.get("outputs", [])))

    if args.require_staged_scope:
        staged = [line for line in git("diff", "--cached", "--name-only").splitlines() if line]
        allowed_exact = {
            "src/role_validation/redevelopment.py",
            "src/role_validation/evaluation.py",
            "src/role_validation/partial_game.py",
            "src/role_validation/fold2.py",
            "scripts/run_fold2_validation.py",
            "scripts/generate_fold2_report.py",
            "scripts/build_fold2_notebook.py",
            "scripts/validate_fold2_outputs.py",
            "tests/test_role_validation_redevelopment.py",
            "tests/test_role_validation_fold2.py",
            "notebooks/fold_2_untouched_2022_validation.ipynb",
        }
        disallowed = [
            path for path in staged
            if path not in allowed_exact and not path.startswith("outputs/role_validation/fold_2/")
        ]
        check("staged_scope_only", not disallowed, f"disallowed={disallowed}")
        check("frozen_config_not_staged", "config/role_change_fold2_candidate.yaml" not in staged)
        check("dashboard_not_staged", not any(path.startswith("dashboard/") for path in staged))
        check("locked_files_not_staged", not any(path in {"ROLE_CHANGE_VALIDATION_PROTOCOL.md", "LOCKED_DECISIONS.md", "config/role_change_validation.yaml"} for path in staged))

    result = {
        "status": "PASS",
        "checks_passed": len(checks),
        "checks": checks,
        "validated_alert_archive_sha256": digest(OUTPUT / "fold2_alerts_2022.csv.gz"),
        "validated_config_sha256": EXPECTED_CONFIG_SHA256,
        "require_staged_scope": args.require_staged_scope,
    }
    (OUTPUT / "final_validation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps({"status": "PASS", "checks_passed": len(checks)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
