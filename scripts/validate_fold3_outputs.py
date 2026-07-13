from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_3"
EXPECTED_CONFIG_SHA = "4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7"
EXPECTED_START = "c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def close(left: float, right: float) -> bool:
    return bool(np.isclose(left, right, equal_nan=True, rtol=1e-10, atol=1e-12))


def main() -> int:
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, detail: object) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": str(detail)})

    required = [
        "fold3_alerts_2023.csv.gz", "canonical_role_2023_enriched.csv.gz",
        "data_audit_2023.csv", "equal_volume_verification_2023.csv",
        "rb_family_method_results_2023.csv", "rb_direction_results_2023.csv",
        "weekly_stability_2023.csv", "partial_game_sensitivity_2023.csv",
        "cross_season_family_2021_2023.csv", "pooled_untouched_family_2022_2023.csv",
        "fold3_gate_decisions.csv", "run_manifest.json", "fold3_execution_lock.json",
        "FOLD_3_REPORT.md", "DATA_AUDIT_2023.md",
    ]
    missing = [name for name in required if not (OUT / name).is_file()]
    check("required_artifacts", not missing, missing or f"{len(required)} present")

    current_config = ROOT / "config" / "role_change_fold2_candidate.yaml"
    frozen_config = OUT / "frozen_role_change_fold3_candidate.yaml"
    check("current_config_hash", sha256(current_config) == EXPECTED_CONFIG_SHA, sha256(current_config))
    check("frozen_config_hash", sha256(frozen_config) == EXPECTED_CONFIG_SHA, sha256(frozen_config))
    with current_config.open(encoding="utf-8") as handle:
        current_semantic = yaml.safe_load(handle)
    with frozen_config.open(encoding="utf-8") as handle:
        frozen_semantic = yaml.safe_load(handle)
    check("semantic_config_equality", current_semantic == frozen_semantic, "YAML objects equal")

    fingerprint = json.loads((OUT / "frozen_config_fingerprint.json").read_text(encoding="utf-8"))
    run = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))
    lock = json.loads((OUT / "fold3_execution_lock.json").read_text(encoding="utf-8"))
    check("start_commit", fingerprint["start_commit"] == EXPECTED_START, fingerprint["start_commit"])
    check("single_execution", bool(run["fold3_executed_once"] and lock["completed"]), lock)
    check("season_isolation", run["test_season"] == 2023 and not run["post_2023_results_used"], run)
    check("alert_archive_hash", sha256(OUT / "fold3_alerts_2023.csv.gz") == lock["alert_archive_sha256"], lock["alert_archive_sha256"])

    canonical = pd.read_csv(OUT / "canonical_role_2023_enriched.csv.gz", low_memory=False)
    audit = pd.read_csv(OUT / "data_audit_2023.csv")
    key = ["season", "week", "player_id", "team", "role_family"]
    check("canonical_2023_only", set(canonical["season"].unique()) == {2023}, sorted(canonical["season"].unique()))
    check("canonical_row_count", len(canonical) == int(audit.at[0, "canonical_rows"]), len(canonical))
    check("canonical_duplicate_keys", not canonical.duplicated(key, keep=False).any(), int(canonical.duplicated(key, keep=False).sum()))
    check("canonical_required_nulls", int(audit.at[0, "required_null_cells"]) == 0, audit.at[0, "required_null_cells"])

    alerts = pd.read_csv(OUT / "fold3_alerts_2023.csv.gz", low_memory=False)
    check("alerts_2023_only", set(alerts["season"].unique()) == {2023}, sorted(alerts["season"].unique()))
    check("future_after_alert", bool((alerts["future_week_1"].dropna() > alerts.loc[alerts["future_week_1"].notna(), "week"]).all()), "future_week_1 > week")
    check("confirmation_ends_on_alert", bool((alerts["confirmation_end_week"] == alerts["week"]).all()), "confirmation_end_week == week")
    check("baseline_before_confirmation", bool((alerts["baseline_max_week"] < alerts["confirmation_start_week"]).all()), "baseline_max_week < confirmation_start_week")

    equal = pd.read_csv(OUT / "equal_volume_verification_2023.csv")
    check("equal_volume_file", len(equal) == 216 and bool(equal["equal_volume"].all()), f"{len(equal)} cells")
    counts = alerts.groupby(["partial_policy", "role_family", "week", "method"]).size().unstack("method", fill_value=0)
    check("equal_volume_recomputed", bool(counts.nunique(axis=1).eq(1).all()), f"{len(counts)} nonzero cells")

    summary = pd.read_csv(OUT / "family_method_results_2023.csv")
    discrepancies: list[str] = []
    for row in summary.itertuples(index=False):
        group = alerts.loc[
            alerts["partial_policy"].eq(row.partial_policy)
            & alerts["role_family"].eq(row.role_family)
            & alerts["method"].eq(row.method)
        ]
        evaluable = group["persistent"].notna()
        reversion_evaluable = group["immediate_reversion"].notna()
        recomputed = {
            "alerts": len(group),
            "evaluable_alerts": int(evaluable.sum()),
            "precision": group.loc[evaluable, "persistent"].astype(float).mean(),
            "reversion_rate": group.loc[reversion_evaluable, "immediate_reversion"].astype(float).mean(),
            "median_retention": group.loc[evaluable, "retention"].median(),
        }
        for metric, value in recomputed.items():
            expected = float(getattr(row, metric))
            if not close(float(value), expected):
                discrepancies.append(f"{row.partial_policy}/{row.role_family}/{row.method}/{metric}: {value} != {expected}")
    check("summary_metrics_recomputed", not discrepancies, discrepancies[:10] or f"{len(summary)} rows")

    temporal = pd.read_csv(OUT / "temporal_integrity_checks_2023.csv")
    check("temporal_manifest", bool(temporal["passed"].all()), temporal.to_dict(orient="records"))
    gates = pd.read_csv(OUT / "fold3_gate_decisions.csv").set_index("role_family")
    check("carry_status", gates.at["rb_carry_share", "fold3_candidate_status"] == "PASSES_FOLD_3_POINT_GATES", gates.at["rb_carry_share", "fold3_candidate_status"])
    check("opportunity_status", gates.at["rb_opportunity_share", "fold3_candidate_status"] == "FAILS_FOLD_3_POINT_GATES", gates.at["rb_opportunity_share", "failed_checks"])
    retired = gates.loc[["wr_target_share", "te_target_share"], "fold3_candidate_status"]
    check("retired_not_reinstated", retired.eq("NOT_APPLICABLE_RETIRED").all(), retired.to_dict())

    tracked_dashboard = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", "dashboard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()
    check("staged_dashboard_unchanged", tracked_dashboard == "", tracked_dashboard or "no staged dashboard files")

    result = {
        "validator": "independent_fold3_output_validator",
        "passed": all(bool(item["passed"]) for item in checks),
        "checks_passed": sum(bool(item["passed"]) for item in checks),
        "checks_total": len(checks),
        "test_season": 2023,
        "post_2023_results_used": False,
        "fold4_executed": False,
        "checks": checks,
    }
    (OUT / "final_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
