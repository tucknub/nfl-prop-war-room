from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "propwar_correctness_audit"
REQUIRED = [
    "FIX_VALIDATION_REPORT.md",
    "calculation_discrepancies_after_fix.csv",
    "cross_page_reconciliation_after_fix.csv",
    "link_state_validation_after_fix.csv",
    "explorer_validation_after_fix.csv",
    "final_validation_after_fix.json",
    "COMMANDS_RUN_FIXES.md",
]


def main() -> int:
    errors = [f"missing required output: {name}" for name in REQUIRED if not (OUT / name).exists()]
    if errors:
        print("AFTER-FIX VALIDATION FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    final = json.loads((OUT / "final_validation_after_fix.json").read_text(encoding="utf-8"))
    calculations = pd.read_csv(OUT / "calculation_discrepancies_after_fix.csv")
    cross_page = pd.read_csv(OUT / "cross_page_reconciliation_after_fix.csv")
    links = pd.read_csv(OUT / "link_state_validation_after_fix.csv")
    explorer = pd.read_csv(OUT / "explorer_validation_after_fix.csv")

    if final["phase_status"] != "PASSED":
        errors.append("phase status is not PASSED")
    if final["production_status"] != "UNCHANGED":
        errors.append("production status changed")
    if any(final["correctness_results"].values()):
        errors.append(f"non-zero correctness result: {final['correctness_results']}")
    if not final["original_audit_artifacts_unchanged"]:
        errors.append("original audit artifacts changed")
    if calculations["status"].eq("FAIL").any():
        errors.append("one or more corrected calculation checks fail")
    displayed = calculations[calculations["displayed_percentage"].notna() & calculations["denominator"].gt(0)]
    if not displayed.empty and (
        displayed["numerator"] / displayed["denominator"] - displayed["expected_percentage"]
    ).abs().max() > 1e-12:
        errors.append("independent expected share is not numerator / denominator")
    if cross_page["status"].eq("FAIL").any():
        errors.append("cross-page values disagree")
    if explorer["status"].eq("FAIL").any() or explorer["case_id"].nunique() != 18:
        errors.append("Explorer corrected matrix does not fully pass")
    if (links["status"].eq("FAIL") & links["severity"].eq("High")).any():
        errors.append("High link/state failure remains")
    if final["results"]["language_failures"] != 0:
        errors.append("public-language guardrail fails")
    if errors:
        print("AFTER-FIX VALIDATION FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print("AFTER-FIX VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
