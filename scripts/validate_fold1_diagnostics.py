from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import nbformat
import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
ALLOWED = {2018, 2019, 2020, 2021}
CHECKPOINT = "00d6085a55c60147e0ace46c847460ef5708e968"
EXPECTED_HASHES = {
    "ROLE_CHANGE_VALIDATION_PROTOCOL.md": "b9fcc357e98388bb15c2d7ae853620f8ccd6c2e60e491a6cfcb990bbfbfcadbe",
    "LOCKED_DECISIONS.md": "57da1e3ebed077bd52709fb3331eb99e719c056e9e840d8c6913b512d7e4ba00",
    "config/role_change_validation.yaml": "e6a64afa9dcec76cf2c0ef582640c575f0f74e6f799427ff4f114699b97a086d",
}


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read(name: str) -> pd.DataFrame:
    frame = pd.read_csv(OUT / name, low_memory=False)
    if "season" in frame:
        observed = set(pd.to_numeric(frame["season"], errors="coerce").dropna().astype(int))
        assert observed.issubset(ALLOWED), f"{name} includes {sorted(observed - ALLOWED)}"
    return frame


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-staged-scope", action="store_true")
    args = parser.parse_args()
    checks: list[dict[str, object]] = []

    def check(name: str, condition: bool, detail: object) -> None:
        if not bool(condition):
            raise AssertionError(f"{name}: {detail}")
        checks.append({"check": name, "status": "PASS", "detail": detail})

    check("branch", git("branch", "--show-current") == "role-change-validation-v1", git("branch", "--show-current"))
    check(
        "checkpoint_tag",
        git("rev-list", "-n", "1", "role-change-validation-v1-fold1-checkpoint") == CHECKPOINT,
        CHECKPOINT,
    )
    for relative, expected in EXPECTED_HASHES.items():
        observed = digest(ROOT / relative)
        check(f"locked_hash:{relative}", observed == expected, observed)

    manifest = json.loads((OUT / "run_manifest.json").read_text(encoding="utf-8"))
    check("allowed_seasons_manifest", set(manifest["allowed_seasons"]) == ALLOWED, manifest["allowed_seasons"])
    check("fold2_not_executed", manifest["fold_2_executed"] is False, manifest["fold_2_executed"])
    check("post2021_not_used", manifest["post_2021_results_used"] is False, manifest["post_2021_results_used"])
    check("gates_unchanged_manifest", manifest["release_gates_changed"] is False, manifest["release_gates_changed"])
    check("screen_integrity_counts", manifest["screen_candidates_valid"] == 53 and manifest["screen_candidates_integrity_failures"] == 1, {"valid": manifest["screen_candidates_valid"], "failed": manifest["screen_candidates_integrity_failures"]})

    candidate_doc = yaml.safe_load((ROOT / "config" / "role_change_fold2_candidate.yaml").read_text(encoding="utf-8"))
    contract = candidate_doc["analysis_contract"]
    check("candidate_allowed_data", set(contract["allowed_development_data"]) == ALLOWED, contract["allowed_development_data"])
    check("candidate_fold2_flag", contract["fold_2_executed"] is False, contract["fold_2_executed"])
    check("candidate_post2021_flag", contract["post_2021_results_used"] is False, contract["post_2021_results_used"])
    check("candidate_gate_hash", contract["release_gates_source_sha256"] == EXPECTED_HASHES["config/role_change_validation.yaml"], contract["release_gates_source_sha256"])
    check("candidate_protocol_hash", contract["protocol_sha256"] == EXPECTED_HASHES["ROLE_CHANGE_VALIDATION_PROTOCOL.md"], contract["protocol_sha256"])
    check("candidate_decisions_hash", contract["locked_decisions_sha256"] == EXPECTED_HASHES["LOCKED_DECISIONS.md"], contract["locked_decisions_sha256"])
    source_manifest = read("input_source_manifest.csv").set_index("artifact")
    candidate_hash = digest(ROOT / "config" / "role_change_fold2_candidate.yaml")
    check(
        "candidate_config_manifest_hash",
        source_manifest.loc[
            "config/role_change_fold2_candidate.yaml", "sha256"
        ]
        == candidate_hash,
        candidate_hash,
    )

    audit = read("canonical_redevelopment_audit_2018_2021.csv")
    missing = read("canonical_redevelopment_missingness_2018_2021.csv")
    check("canonical_rows", int(audit["canonical_rows"].sum()) == 28199, int(audit["canonical_rows"].sum()))
    check("canonical_duplicate_grain", int(audit["duplicate_key_rows"].sum()) == 0, int(audit["duplicate_key_rows"].sum()))
    check("required_missingness", int(missing["null_rows"].sum()) == 0, int(missing["null_rows"].sum()))

    canonical = read("canonical_role_2018_2021_enriched.csv.gz")
    key = ["season", "week", "player_id", "team", "role_family"]
    check("enriched_grain", len(canonical) == 28199 and not canonical.duplicated(key).any(), len(canonical))
    check("confirmed_not_usage_only", canonical.loc[canonical["confirmed_partial_game"], "explicit_pbp_injury"].fillna(False).astype(bool).all(), int(canonical["confirmed_partial_game"].sum()))
    confirmed = canonical.loc[canonical["confirmed_partial_game"]]
    check("confirmed_no_return", confirmed["last_offensive_play_id"].le(confirmed["injury_play_id"]).all(), len(confirmed))
    check("confirmed_five_plays", confirmed["focal_team_offensive_plays_after_injury"].ge(5).all(), len(confirmed))
    check("confirmed_temporal_window", (pd.to_datetime(confirmed["trigger_end_proxy_utc"], utc=True) < pd.to_datetime(confirmed["next_game_kickoff_utc"], utc=True)).all(), len(confirmed))

    partial_source = read("partial_game_source_coverage.csv").iloc[0]
    check("schedule_trigger_coverage", int(partial_source["trigger_timestamp_missing_team_games"]) == 0, int(partial_source["trigger_timestamp_missing_team_games"]))
    check("schedule_final_boundaries", int(partial_source["next_boundary_missing_team_games"]) == 128, int(partial_source["next_boundary_missing_team_games"]))

    original_weekly = read("original_weekly_family_vs_deduplicated_volume_2021.csv")
    check("original_family_alerts", int(original_weekly["family_alert_rows"].sum()) == 717, int(original_weekly["family_alert_rows"].sum()))
    check("original_deduplicated_alerts", int(original_weekly["deduplicated_feed_alerts"].sum()) == 489, int(original_weekly["deduplicated_feed_alerts"].sum()))
    overlap = read("original_rb_family_overlap_2021.csv").iloc[0]
    check("rb_family_overlap", int(overlap["overlap_alerts"]) == 228 and int(overlap["direction_conflicts"]) == 0, overlap.to_dict())
    repeats = read("original_repeat_alerts_2021.csv").set_index("grain")
    check("consecutive_repeats", int(repeats.loc["deduplicated_player_week", "repeat_alerts"]) == 151, int(repeats.loc["deduplicated_player_week", "repeat_alerts"]))

    serious_equal = read("serious_candidate_equal_volume.csv")
    sensitivity_equal = read("recommended_candidate_partial_sensitivity_equal_volume.csv")
    for name, frame in [("serious", serious_equal), ("partial_sensitivity", sensitivity_equal)]:
        check(f"{name}_equal_volume", frame["equal_volume"].all(), len(frame))
        check(f"{name}_methods_present", frame["observed_method_count"].eq(4).all(), len(frame))
        count_columns = ["naive_spike_count", "two_week_raw_count", "normal_game_trend_count", "full_propwar_count"]
        check(f"{name}_counts_exact", frame[count_columns].nunique(axis=1).eq(1).all(), len(frame))

    screens = read("candidate_axis_screen_equal_volume.csv")
    check("screen_valid_failure", screens["integrity_pass"].fillna(False).sum() == 53 and (~screens["integrity_pass"].fillna(False)).sum() == 1, len(screens))

    serious = read("serious_candidate_alerts_2018_2021.csv.gz")
    sensitivity = read("recommended_candidate_partial_sensitivity_alerts_2018_2021.csv.gz")
    archive_key = ["candidate_name", "partial_policy", "method", *key]
    check("serious_archive_grain", not serious.duplicated(archive_key).any(), len(serious))
    check("sensitivity_archive_grain", not sensitivity.duplicated(archive_key).any(), len(sensitivity))
    serious_rec = serious.loc[serious["candidate_name"].eq("S2_symmetric_deltas") & serious["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")]
    sensitivity_primary = sensitivity.loc[sensitivity["partial_policy"].eq("PRIMARY_CONFIRMED_EXCLUDED")]
    membership_key = ["method", *key]
    check("recommended_membership_matches_serious", set(map(tuple, serious_rec[membership_key].to_numpy())) == set(map(tuple, sensitivity_primary[membership_key].to_numpy())), len(sensitivity_primary))

    family = read("recommended_candidate_partial_sensitivity_family.csv")
    comparisons = read("recommended_candidate_partial_sensitivity_comparisons.csv")
    ci_rows = family.loc[family["evaluable_alerts"].gt(0)]
    check("precision_intervals_present", ci_rows[["precision_ci_low", "precision_ci_high"]].notna().all().all(), len(ci_rows))
    comparison_ci_rows = comparisons.loc[comparisons["full_evaluable_alerts"].gt(0)]
    check("improvement_intervals_present", comparison_ci_rows[["precision_improvement_ci_low", "precision_improvement_ci_high"]].notna().all().all(), len(comparison_ci_rows))
    relative_expected = comparison_ci_rows["naive_precision"].notna() & comparison_ci_rows[
        "naive_precision"
    ].ne(0)
    check(
        "relative_improvement_present_when_defined",
        comparison_ci_rows.loc[
            relative_expected, "relative_precision_improvement"
        ].notna().all(),
        int(relative_expected.sum()),
    )

    gates = read("recommended_candidate_locked_gate_diagnostic_2021.csv")
    check("gate_diagnostic_only", gates["release_status"].eq("DIAGNOSTIC_ONLY_2021_REUSED_FOR_REDEVELOPMENT").all(), len(gates))
    check(
        "gate_result_labels_are_non_release",
        set(gates["point_gate_result"]).issubset(
            {"POINT_GATES_PASS", "POINT_GATES_FAIL"}
        ),
        sorted(set(gates["point_gate_result"])),
    )
    check("gate_not_frozen", gates["frozen_before_2021"].eq(False).all(), len(gates))

    manual = read("original_false_positive_manual_adjudication_2021.csv")
    manual_manifest = json.loads((OUT / "manual_review_manifest.json").read_text(encoding="utf-8"))
    check("manual_review_count", len(manual) == 254 == manual_manifest["reviewed_rows"], len(manual))
    check("manual_review_complete", manual["manual_review_status"].eq("MANUALLY_ADJUDICATED").all(), int(manual["manual_review_status"].eq("MANUALLY_ADJUDICATED").sum()))
    check("manual_review_source_hash", manual_manifest["source_sha256"] == digest(OUT / "original_false_positive_case_review_2021.csv"), manual_manifest["source_sha256"])

    report = (OUT / "FOLD_1_DIAGNOSTIC_AND_REDEVELOPMENT_REPORT.md")
    report_text = report.read_text(encoding="utf-8")
    check("report_exists", len(report_text) > 10000, len(report_text))
    for phrase in ["Fold 2 was not executed", "does not claim that the detector works", "Original versus recommended Fold 1", "Exact candidate recommended for Fold 2"]:
        check(f"report_phrase:{phrase}", phrase in report_text, phrase)

    notebook_path = ROOT / "notebooks" / "fold_1_detector_diagnostics.ipynb"
    notebook = nbformat.read(notebook_path, as_version=4)
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    check("notebook_executed", all(cell.execution_count is not None for cell in code_cells), len(code_cells))
    errors = [output for cell in code_cells for output in cell.get("outputs", []) if output.get("output_type") == "error"]
    check("notebook_no_errors", not errors, len(errors))

    if args.require_staged_scope:
        staged = [line for line in git("diff", "--cached", "--name-only").splitlines() if line]
        forbidden = [path for path in staged if path.startswith("dashboard/") or path in {"README.md", "DASHBOARD_NAVIGATION.md"}]
        check("staged_dashboard_scope", not forbidden, forbidden)
        check("locked_files_not_staged", not any(path in EXPECTED_HASHES for path in staged), staged)

    result = {
        "status": "PASS",
        "checks_passed": len(checks),
        "allowed_seasons": sorted(ALLOWED),
        "fold_2_executed": False,
        "release_gates_changed": False,
        "checks": checks,
    }
    (OUT / "final_validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "checks_passed": result["checks_passed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
