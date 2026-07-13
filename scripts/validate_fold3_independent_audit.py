from __future__ import annotations

import json
import subprocess
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_3_independent_audit"
AUDITED_COMMIT = "a18c5cc3e8c9124be4781bececea0a93f7b4faf8"


def main() -> int:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": str(detail)})

    manifest = json.loads((OUT / "audit_manifest.json").read_text(encoding="utf-8"))
    check("audit_manifest_passed", manifest["audit_passed"], manifest)
    check("audited_commit", manifest["audited_commit"] == AUDITED_COMMIT, manifest["audited_commit"])
    check("no_fold4", not manifest["fold4_executed"], manifest["fold4_executed"])

    headline = pd.read_csv(OUT / "headline_recomputed_2023.csv")
    comparisons = pd.read_csv(OUT / "family_comparisons_recomputed_2023.csv").set_index("role_family")
    carry = comparisons.loc["rb_carry_share"]
    opportunity = comparisons.loc["rb_opportunity_share"]
    check("carry_raw_numerators", (carry.full_alerts, carry.full_evaluable_alerts, carry.full_persistent_alerts) == (60, 47, 31), (carry.full_alerts, carry.full_evaluable_alerts, carry.full_persistent_alerts))
    check("opportunity_raw_numerators", (opportunity.full_alerts, opportunity.full_evaluable_alerts, opportunity.full_persistent_alerts) == (74, 57, 44), (opportunity.full_alerts, opportunity.full_evaluable_alerts, opportunity.full_persistent_alerts))
    check("headline_method_rows", len(headline) == 8, len(headline))
    check("carry_lift", np.isclose(carry.precision_improvement, .12896222318714712), carry.precision_improvement)
    check("opportunity_lift", np.isclose(opportunity.precision_improvement, .20296430732002413), opportunity.precision_improvement)

    gates = pd.read_csv(OUT / "family_decisions_independent_check.csv").set_index("role_family")
    check("carry_all_gates", bool(gates.at["rb_carry_share", "all_gates_pass"]), gates.loc["rb_carry_share"].to_dict())
    check("opportunity_direction_failure", not bool(gates.at["rb_opportunity_share", "all_gates_pass"]) and gates.at["rb_opportunity_share", "failed_gates"] == "direction_consistent_across_periods", gates.loc["rb_opportunity_share"].to_dict())

    pooled = pd.read_csv(OUT / "pooled_recomputed_2022_2023.csv").set_index("role_family")
    check("pooled_carry_raw", tuple(pooled.loc["rb_carry_share", ["full_alerts", "full_persistent_alerts", "full_evaluable_alerts"]].astype(int)) == (109, 56, 86), pooled.loc["rb_carry_share"].to_dict())
    check("pooled_opportunity_raw", tuple(pooled.loc["rb_opportunity_share", ["full_alerts", "full_persistent_alerts", "full_evaluable_alerts"]].astype(int)) == (133, 73, 104), pooled.loc["rb_opportunity_share"].to_dict())

    equal = pd.read_csv(OUT / "equal_volume_independent_check.csv")
    replay = pd.read_csv(OUT / "comparator_selection_replay.csv")
    compliance = pd.read_csv(OUT / "full_alert_rule_compliance.csv")
    temporal = pd.read_csv(OUT / "temporal_integrity_independent_check.csv")
    outcomes = pd.read_csv(OUT / "outcome_label_reconstruction.csv")
    sources = pd.read_csv(OUT / "input_hash_reconciliation.csv")
    reconciliation = pd.read_csv(OUT / "committed_summary_reconciliation.csv")
    check("equal_volume", len(equal) == 216 and bool(equal["equal_volume"].all()), f"{len(equal)} cells")
    check("comparator_replay", len(replay) == 648 and bool(replay["pool_sufficient"].all()) and bool(replay["selection_matches_deterministic_top_n"].all()), f"{len(replay)} cells")
    check("full_rule_compliance", bool(compliance["all_rules_satisfied"].all()), compliance.to_dict(orient="records"))
    check("temporal_checks", len(temporal) == 10 and bool(temporal["passed"].all()), temporal.to_dict(orient="records"))
    check("outcome_reconstruction", len(outcomes) == 9 and bool(outcomes["matched"].all()), outcomes.to_dict(orient="records"))
    check("input_hashes", bool(sources["matched"].all()), sources.to_dict(orient="records"))
    check("summary_reconciliation", bool(reconciliation["matched"].all()), reconciliation.to_dict(orient="records"))

    report = (OUT / "INDEPENDENT_FOLD_3_AUDIT.md").read_text(encoding="utf-8")
    recommendations = [
        "ADVANCE_UNCHANGED_TO_FOLD_4",
        "CONTINUE_UNCHANGED_SHADOW_FOLD_4",
        "REMAIN_RETIRED",
    ]
    check("report_recommendations", all(value in report for value in recommendations), recommendations)

    notebook_path = ROOT / "notebooks" / "fold_3_independent_methodological_audit.ipynb"
    notebook = nbformat.read(notebook_path, as_version=4)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    errors = [output for cell in code_cells for output in cell.get("outputs", []) if output.output_type == "error"]
    check("notebook_executed", len(code_cells) == 8 and all(cell.execution_count is not None for cell in code_cells) and not errors, f"{len(code_cells)} cells, {len(errors)} errors")

    protected_diff = subprocess.check_output(
        ["git", "diff", "--name-only", AUDITED_COMMIT, "--", "config", "src/role_validation", "outputs/role_validation/fold_3"],
        cwd=ROOT, text=True,
    ).splitlines()
    check("detector_results_and_config_unmodified", not protected_diff, protected_diff or "no changes")

    result = {
        "validator": "fold3_independent_audit_validator",
        "passed": all(bool(item["passed"]) for item in checks),
        "checks_passed": sum(bool(item["passed"]) for item in checks),
        "checks_total": len(checks),
        "audited_commit": AUDITED_COMMIT,
        "fold4_executed": False,
        "checks": checks,
    }
    (OUT / "validation_manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
