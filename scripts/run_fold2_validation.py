from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from role_validation.diagnostics import add_diagnostic_dimensions  # noqa: E402
from role_validation.fold2 import (  # noqa: E402
    FOLD2_SEASON,
    PARTIAL_POLICIES,
    PRIMARY_POLICY,
    assert_frozen_config_integrity,
    assert_temporal_integrity,
    block_results,
    canonical_audit,
    comparison_results,
    direction_results,
    feed_summary,
    file_sha256,
    generalization_direction_table,
    generalization_table,
    method_results,
    missingness_table,
    rb_overlap,
    release_gate_table,
    repeat_rates,
    weekly_stability,
)
from role_validation.partial_game import (  # noqa: E402
    build_partial_game_status,
    load_explicit_injury_sources,
)
from role_validation.redevelopment import (  # noqa: E402
    CANONICAL_KEY,
    EXPECTED_METHODS,
    ROLE_FAMILIES,
    load_canonical_seasons,
    run_candidate,
)


EXPECTED_CONFIG_SHA256 = "4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7"
START_COMMIT = "bdff056fa625eef76152e1b9f3ef0e88fda2bbab"
PRE_FOLD2_TAG = "role-change-validation-v1-pre-fold2-checkpoint"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the frozen 2022 Fold 2 validation once.")
    parser.add_argument("--stage", choices=["precheck", "execute"], required=True)
    parser.add_argument("--config", default="config/role_change_fold2_candidate.yaml")
    parser.add_argument(
        "--fold1-report",
        default="outputs/role_validation/fold_1_diagnostics/FOLD_1_DIAGNOSTIC_AND_REDEVELOPMENT_REPORT.md",
    )
    parser.add_argument(
        "--canonical", default="outputs/role_validation/canonical_player_week_role.csv.gz"
    )
    parser.add_argument("--source-cache-dir", default="data/raw/role_validation")
    parser.add_argument("--output-dir", default="outputs/role_validation/fold_2")
    return parser.parse_args()


def absolute(path: str) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def write_csv(frame: pd.DataFrame, path: Path, *, compressed: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compressed:
        frame.to_csv(
            path,
            index=False,
            compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
        )
    else:
        frame.to_csv(path, index=False)


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def load_cached_season(cache_dir: Path, name: str, season: int) -> tuple[pd.DataFrame, Path]:
    matches = sorted(cache_dir.glob(f"{name}_*.csv.gz"))
    if not matches:
        raise FileNotFoundError(f"No cached {name} source in {cache_dir}")
    path = max(matches, key=lambda item: item.stat().st_size)
    selected = []
    for chunk in pd.read_csv(path, chunksize=100_000, low_memory=False):
        if "season" in chunk:
            source_season = pd.to_numeric(chunk["season"], errors="coerce")
        elif "nflverse_game_id" in chunk:
            source_season = pd.to_numeric(
                chunk["nflverse_game_id"].astype(str).str[:4], errors="coerce"
            )
        else:
            raise ValueError(f"Cannot determine season in {path.name}")
        selected.append(chunk.loc[source_season.eq(season)].copy())
    result = pd.concat(selected, ignore_index=True)
    if result.empty:
        raise AssertionError(f"Cached {name} has no {season} rows")
    return result, path


def repository_prechecks(config_path: Path, report_path: Path) -> dict:
    branch = run_git("branch", "--show-current")
    head = run_git("rev-parse", "HEAD")
    tagged = run_git("rev-list", "-n", "1", PRE_FOLD2_TAG)
    config_diff = run_git("diff", "--name-only", "HEAD", "--", str(config_path.relative_to(ROOT)))
    if branch != "role-change-validation-v1":
        raise AssertionError(f"Unexpected branch: {branch}")
    if head != START_COMMIT:
        raise AssertionError(f"Fold 2 must start at {START_COMMIT}; found {head}")
    if tagged != START_COMMIT:
        raise AssertionError("Pre-Fold-2 tag does not resolve to the frozen candidate commit")
    if config_diff:
        raise AssertionError("Frozen candidate YAML differs from HEAD")
    integrity = assert_frozen_config_integrity(
        config_path,
        report_path,
        expected_sha256=EXPECTED_CONFIG_SHA256,
    )
    release_path = ROOT / integrity["config_document"]["analysis_contract"]["release_gates_source"]
    protected = {
        "release_gates": release_path,
        "protocol": ROOT / "ROLE_CHANGE_VALIDATION_PROTOCOL.md",
        "locked_decisions": ROOT / "LOCKED_DECISIONS.md",
    }
    expected = {
        "release_gates": integrity["config_document"]["analysis_contract"]["release_gates_source_sha256"],
        "protocol": integrity["config_document"]["analysis_contract"]["protocol_sha256"],
        "locked_decisions": integrity["config_document"]["analysis_contract"]["locked_decisions_sha256"],
    }
    protected_hashes = {name: file_sha256(path) for name, path in protected.items()}
    if protected_hashes != expected:
        raise AssertionError(
            f"Protected protocol/gate hashes changed: observed={protected_hashes}, expected={expected}"
        )
    return {
        "branch": branch,
        "start_commit": head,
        "pre_fold2_tag": PRE_FOLD2_TAG,
        "pre_fold2_tag_commit": tagged,
        "config_sha256": integrity["sha256"],
        "config_matches_fold1_report": True,
        "protected_hashes": protected_hashes,
        "integrity_checks": integrity["checks"],
    }


def precheck(args: argparse.Namespace) -> int:
    output = absolute(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config_path = absolute(args.config)
    report_path = absolute(args.fold1_report)
    repository = repository_prechecks(config_path, report_path)

    frozen_copy = output / "frozen_role_change_fold2_candidate.yaml"
    if frozen_copy.exists() and frozen_copy.read_bytes() != config_path.read_bytes():
        raise AssertionError("Existing frozen configuration copy differs")
    shutil.copyfile(config_path, frozen_copy)
    fingerprint = {
        **repository,
        "frozen_copy": str(frozen_copy.relative_to(ROOT)).replace("\\", "/"),
        "frozen_copy_sha256": file_sha256(frozen_copy),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (output / "frozen_config_fingerprint.json").write_text(
        json.dumps(fingerprint, indent=2), encoding="utf-8"
    )

    validation_config = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )
    canonical = load_canonical_seasons(str(absolute(args.canonical)), [FOLD2_SEASON])
    audit = canonical_audit(canonical, validation_config["data"]["required_columns"])
    write_csv(audit, output / "data_audit_2022.csv")
    write_csv(missingness_table(canonical), output / "missingness_2022.csv")

    cache_dir = absolute(args.source_cache_dir)
    selected_pbp, pbp_path = load_cached_season(cache_dir, "pbp", FOLD2_SEASON)
    participation, participation_path = load_cached_season(
        cache_dir, "participation", FOLD2_SEASON
    )
    injuries, injuries_path = load_cached_season(cache_dir, "injuries", FOLD2_SEASON)
    explicit_pbp, full_rosters, schedules = load_explicit_injury_sources([FOLD2_SEASON])
    partial = build_partial_game_status(
        canonical,
        selected_pbp=selected_pbp,
        participation=participation,
        injuries=injuries,
        explicit_pbp=explicit_pbp,
        full_rosters=full_rosters,
        schedules=schedules,
        seasons=[FOLD2_SEASON],
    )
    enriched = partial.canonical
    if enriched.duplicated(CANONICAL_KEY).any() or len(enriched) != len(canonical):
        raise AssertionError("Partial-game enrichment changed canonical grain")
    write_csv(enriched, output / "canonical_role_2022_enriched.csv.gz", compressed=True)
    write_csv(partial.evidence_ledger, output / "partial_game_evidence_2022.csv")
    write_csv(partial.source_coverage, output / "partial_game_source_coverage_2022.csv")
    exclusions = enriched.loc[
        ~enriched["data_quality_pass"].fillna(False).astype(bool)
        | enriched["confirmed_partial_game"].fillna(False).astype(bool)
    ].copy()
    exclusions["exclusion_reason"] = "CONFIRMED_PARTIAL_GAME"
    exclusions.loc[
        ~exclusions["data_quality_pass"].fillna(False).astype(bool), "exclusion_reason"
    ] = "DATA_QUALITY_FAIL"
    write_csv(exclusions, output / "exclusions_2022.csv")

    source_coverage = pd.read_csv(ROOT / "outputs" / "role_validation" / "source_coverage_by_season.csv")
    source_coverage = source_coverage.loc[source_coverage["season"].eq(FOLD2_SEASON)].copy()
    join_coverage = pd.read_csv(ROOT / "outputs" / "role_validation" / "join_coverage.csv")
    join_coverage = join_coverage.loc[join_coverage["season"].eq(FOLD2_SEASON)].copy()
    if len(source_coverage) != 1 or not bool(source_coverage.iloc[0]["complete_schema_and_games"]):
        raise AssertionError("2022 source coverage is incomplete")
    if join_coverage.empty or not join_coverage["coverage_rate"].eq(1.0).all():
        raise AssertionError("2022 identity joins are incomplete")
    write_csv(source_coverage, output / "source_coverage_2022.csv")
    write_csv(join_coverage, output / "join_coverage_2022.csv")
    source_manifest = pd.DataFrame(
        [
            {"source": "canonical", "path": str(absolute(args.canonical)), "sha256": file_sha256(absolute(args.canonical))},
            {"source": "cached_pbp", "path": str(pbp_path), "sha256": file_sha256(pbp_path)},
            {"source": "cached_participation", "path": str(participation_path), "sha256": file_sha256(participation_path)},
            {"source": "cached_injuries", "path": str(injuries_path), "sha256": file_sha256(injuries_path)},
            {"source": "frozen_config", "path": str(config_path), "sha256": file_sha256(config_path)},
            {"source": "release_gates", "path": str(ROOT / "config" / "role_change_validation.yaml"), "sha256": file_sha256(ROOT / "config" / "role_change_validation.yaml")},
        ]
    )
    write_csv(source_manifest, output / "input_source_manifest.csv")
    manifest = {
        "stage": "precheck",
        "passed": True,
        "evaluation_executed": False,
        "allowed_seasons": [FOLD2_SEASON],
        "post_2022_seasons_read": False,
        "canonical_rows": len(enriched),
        "canonical_duplicate_keys": int(enriched.duplicated(CANONICAL_KEY, keep=False).sum()),
        "confirmed_partial_family_rows": int(enriched["confirmed_partial_game"].sum()),
        "suspected_partial_family_rows": int(enriched["suspected_partial_game"].sum()),
        "source_coverage_passed": True,
        "identity_coverage_passed": True,
        "config_integrity_passed": True,
        "temporal_design_static_checks_passed": True,
        "equal_volume_automated_test_required_before_execute": True,
    }
    (output / "pre_run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


def execute(args: argparse.Namespace) -> int:
    output = absolute(args.output_dir)
    pre_run_path = output / "pre_run_manifest.json"
    if not pre_run_path.exists():
        raise AssertionError("Pre-run manifest is missing")
    pre_run = json.loads(pre_run_path.read_text(encoding="utf-8"))
    if not pre_run.get("passed") or pre_run.get("evaluation_executed"):
        raise AssertionError("Pre-run checks did not authorize Fold 2 execution")
    lock_path = output / "fold2_execution_lock.json"
    if lock_path.exists():
        raise AssertionError("Fold 2 execution lock exists; rerun is prohibited")

    config_path = absolute(args.config)
    repository = repository_prechecks(config_path, absolute(args.fold1_report))
    frozen_copy = output / "frozen_role_change_fold2_candidate.yaml"
    if file_sha256(frozen_copy) != EXPECTED_CONFIG_SHA256:
        raise AssertionError("Frozen output copy hash changed")
    pre_execution_tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_role_validation_redevelopment.py",
            "tests/test_role_validation_fold2.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    (output / "pre_execution_test_results.txt").write_text(
        pre_execution_tests.stdout + pre_execution_tests.stderr,
        encoding="utf-8",
    )
    if pre_execution_tests.returncode != 0:
        raise AssertionError("Pre-execution temporal/equal-volume tests failed")
    lock = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": FOLD2_SEASON,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "start_commit": repository["start_commit"],
        "single_execution_authorized": True,
        "completed": False,
    }
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")

    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    candidate = document["candidate"]
    enriched = pd.read_csv(output / "canonical_role_2022_enriched.csv.gz", low_memory=False)
    if set(enriched["season"].astype(int).unique()) != {FOLD2_SEASON}:
        raise AssertionError("Fold 2 enriched input is not 2022-only")

    alert_parts = []
    equal_parts = []
    suppressed_parts = []
    feature_cache = {}
    for policy in PARTIAL_POLICIES:
        result = run_candidate(
            enriched,
            candidate,
            partial_policy=policy,
            feature_cache=feature_cache,
            allowed_seasons=[FOLD2_SEASON],
        )
        alert_parts.append(result["alerts"])
        equal_parts.append(result["equal_volume"])
        if not result["suppressed"].empty:
            suppressed_parts.append(result["suppressed"].assign(partial_policy=policy))
    alerts = pd.concat(alert_parts, ignore_index=True)
    equal_volume = pd.concat(equal_parts, ignore_index=True)
    suppressed = pd.concat(suppressed_parts, ignore_index=True) if suppressed_parts else pd.DataFrame()
    if set(alerts["season"].astype(int).unique()) != {FOLD2_SEASON}:
        raise AssertionError("Fold 2 results contain a disallowed season")
    if not equal_volume["equal_volume"].all():
        raise AssertionError("Fold 2 comparator matching is not equal-volume")
    if not equal_volume["observed_method_count"].eq(len(EXPECTED_METHODS)).all():
        raise AssertionError("Fold 2 comparator output is missing a method")

    temporal = assert_temporal_integrity(
        alerts.loc[alerts["partial_policy"].eq(PRIMARY_POLICY)]
    )
    methods = method_results(alerts)
    comparisons = comparison_results(alerts)
    directions = direction_results(alerts)
    blocks = block_results(alerts)
    weekly = weekly_stability(alerts)
    feed, feed_weekly = feed_summary(alerts)
    repeats = repeat_rates(alerts)
    overlap = rb_overlap(alerts)

    prior_alerts = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "recommended_candidate_partial_sensitivity_alerts_2018_2021.csv.gz",
        low_memory=False,
    )
    prior = prior_alerts.loc[
        prior_alerts["season"].eq(2021)
        & prior_alerts["partial_policy"].eq(PRIMARY_POLICY)
    ].copy()
    current = alerts.loc[alerts["partial_policy"].eq(PRIMARY_POLICY)].copy()
    generalization = generalization_table(prior, current)
    generalization_direction = generalization_direction_table(prior, current)
    validation_config = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )
    gates = release_gate_table(
        methods,
        validation_config["release_gates"]["full_release"],
        generalization_direction,
    )

    write_csv(alerts, output / "fold2_alerts_2022.csv.gz", compressed=True)
    write_csv(equal_volume, output / "equal_volume_verification_2022.csv")
    write_csv(suppressed, output / "repeat_suppressed_alerts_2022.csv")
    write_csv(temporal, output / "temporal_integrity_checks_2022.csv")
    write_csv(methods, output / "family_method_results_2022.csv")
    write_csv(comparisons, output / "family_comparisons_2022.csv")
    write_csv(directions, output / "direction_results_2022.csv")
    write_csv(blocks, output / "season_block_results_2022.csv")
    write_csv(weekly, output / "weekly_stability_2022.csv")
    write_csv(feed, output / "deduplicated_feed_summary_2022.csv")
    write_csv(feed_weekly, output / "deduplicated_weekly_volume_2022.csv")
    write_csv(repeats, output / "repeat_alert_rates_2022.csv")
    write_csv(overlap, output / "rb_family_overlap_2022.csv")
    write_csv(generalization, output / "generalization_2021_vs_2022.csv")
    write_csv(
        generalization_direction,
        output / "generalization_direction_2021_vs_2022.csv",
    )
    write_csv(gates, output / "release_gate_results_2022.csv")

    lock["completed"] = True
    lock["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    lock["alert_archive_sha256"] = file_sha256(output / "fold2_alerts_2022.csv.gz")
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    execution_manifest = {
        "stage": "execute",
        "passed": True,
        "fold2_executed_once": True,
        "test_season": FOLD2_SEASON,
        "post_2022_results_used": False,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "candidate_name": candidate["name"],
        "partial_policies": list(PARTIAL_POLICIES),
        "family_alert_method_rows": len(alerts),
        "primary_full_family_alerts": int(
            len(
                alerts.loc[
                    alerts["partial_policy"].eq(PRIMARY_POLICY)
                    & alerts["method"].eq("full_propwar")
                ]
            )
        ),
        "equal_volume_cells": len(equal_volume),
        "all_equal_volume": bool(equal_volume["equal_volume"].all()),
        "all_temporal_checks_passed": bool(temporal["passed"].all()),
        "pre_execution_tests_passed": True,
        "release_statuses": gates.set_index("role_family")["status"].to_dict(),
    }
    (output / "run_manifest.json").write_text(
        json.dumps(execution_manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(execution_manifest, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    if args.stage == "precheck":
        return precheck(args)
    return execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
