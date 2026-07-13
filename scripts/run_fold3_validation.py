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

from role_validation.fold2 import (  # noqa: E402
    PARTIAL_POLICIES,
    PRIMARY_POLICY,
    assert_temporal_integrity,
    block_results,
    canonical_audit,
    comparison_results,
    direction_results,
    feed_summary,
    file_sha256,
    method_results,
    missingness_table,
    rb_overlap,
    repeat_rates,
    weekly_stability,
)
from role_validation.fold3 import (  # noqa: E402
    EXPECTED_CONFIG_SHA256,
    FOLD3_SEASON,
    assert_fold3_config_integrity,
    cross_season_direction_results,
    cross_season_family_results,
    cross_season_weekly_stability,
    fold3_release_gate_table,
    pooled_untouched_results,
)
from role_validation.partial_game import (  # noqa: E402
    build_partial_game_status,
    load_explicit_injury_sources,
)
from role_validation.redevelopment import (  # noqa: E402
    CANONICAL_KEY,
    EXPECTED_METHODS,
    load_canonical_seasons,
    run_candidate,
)


START_COMMIT = "c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9"
PRE_FOLD3_TAG = "role-change-validation-v1-pre-fold3-checkpoint"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run frozen candidate once on untouched 2023 Fold 3.")
    parser.add_argument("--stage", choices=["precheck", "execute"], required=True)
    parser.add_argument("--config", default="config/role_change_fold2_candidate.yaml")
    parser.add_argument("--canonical", default="outputs/role_validation/canonical_player_week_role.csv.gz")
    parser.add_argument("--source-cache-dir", default="data/raw/role_validation")
    parser.add_argument("--output-dir", default="outputs/role_validation/fold_3")
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


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def load_cached_season(cache_dir: Path, name: str) -> tuple[pd.DataFrame, Path]:
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
        selected.append(chunk.loc[source_season.eq(FOLD3_SEASON)].copy())
    result = pd.concat(selected, ignore_index=True)
    if result.empty:
        raise AssertionError(f"Cached {name} has no {FOLD3_SEASON} rows")
    return result, path


def repository_prechecks(config_path: Path) -> dict:
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    tag_commit = git("rev-list", "-n", "1", PRE_FOLD3_TAG)
    config_diff = git(
        "diff", "--name-only", "HEAD", "--", str(config_path.relative_to(ROOT))
    )
    if branch != "role-change-validation-v1":
        raise AssertionError(f"Unexpected branch: {branch}")
    if head != START_COMMIT:
        raise AssertionError(f"Fold 3 must start at {START_COMMIT}; found {head}")
    if tag_commit != START_COMMIT:
        raise AssertionError("Pre-Fold-3 tag does not resolve to the starting commit")
    if config_diff:
        raise AssertionError("Frozen candidate YAML differs from HEAD")
    integrity = assert_fold3_config_integrity(
        config_path,
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "FOLD_1_DIAGNOSTIC_AND_REDEVELOPMENT_REPORT.md",
        ROOT / "outputs" / "role_validation" / "fold_2"
        / "frozen_role_change_fold2_candidate.yaml",
        ROOT / "outputs" / "role_validation" / "fold_2"
        / "frozen_config_fingerprint.json",
    )
    contract = integrity["config_document"]["analysis_contract"]
    protected = {
        "release_gates": ROOT / contract["release_gates_source"],
        "protocol": ROOT / "ROLE_CHANGE_VALIDATION_PROTOCOL.md",
        "locked_decisions": ROOT / "LOCKED_DECISIONS.md",
    }
    expected = {
        "release_gates": contract["release_gates_source_sha256"],
        "protocol": contract["protocol_sha256"],
        "locked_decisions": contract["locked_decisions_sha256"],
    }
    observed = {name: file_sha256(path) for name, path in protected.items()}
    if observed != expected:
        raise AssertionError(f"Protected hashes changed: {observed}")
    return {
        "branch": branch,
        "start_commit": head,
        "pre_fold3_tag": PRE_FOLD3_TAG,
        "pre_fold3_tag_commit": tag_commit,
        "config_sha256": integrity["sha256"],
        "fold2_frozen_copy_sha256": integrity["fold2_frozen_copy_sha256"],
        "semantic_match_to_fold1_report": True,
        "byte_identical_to_fold2_frozen_copy": True,
        "protected_hashes": observed,
        "integrity_checks": integrity["checks"],
    }


def precheck(args: argparse.Namespace) -> int:
    output = absolute(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    config_path = absolute(args.config)
    repository = repository_prechecks(config_path)
    frozen_copy = output / "frozen_role_change_fold3_candidate.yaml"
    if frozen_copy.exists() and frozen_copy.read_bytes() != config_path.read_bytes():
        raise AssertionError("Existing Fold 3 frozen copy differs")
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
    canonical_path = absolute(args.canonical)
    canonical = load_canonical_seasons(str(canonical_path), [FOLD3_SEASON])
    audit = canonical_audit(
        canonical,
        validation_config["data"]["required_columns"],
        expected_season=FOLD3_SEASON,
    )
    write_csv(audit, output / "data_audit_2023.csv")
    write_csv(
        missingness_table(canonical, expected_season=FOLD3_SEASON),
        output / "missingness_2023.csv",
    )

    cache_dir = absolute(args.source_cache_dir)
    selected_pbp, pbp_path = load_cached_season(cache_dir, "pbp")
    participation, participation_path = load_cached_season(cache_dir, "participation")
    injuries, injuries_path = load_cached_season(cache_dir, "injuries")
    explicit_pbp, full_rosters, schedules = load_explicit_injury_sources([FOLD3_SEASON])
    partial = build_partial_game_status(
        canonical,
        selected_pbp=selected_pbp,
        participation=participation,
        injuries=injuries,
        explicit_pbp=explicit_pbp,
        full_rosters=full_rosters,
        schedules=schedules,
        seasons=[FOLD3_SEASON],
    )
    enriched = partial.canonical
    if len(enriched) != len(canonical) or enriched.duplicated(CANONICAL_KEY).any():
        raise AssertionError("Partial-game enrichment changed canonical grain")
    write_csv(enriched, output / "canonical_role_2023_enriched.csv.gz", compressed=True)
    write_csv(partial.evidence_ledger, output / "partial_game_evidence_2023.csv")
    write_csv(partial.source_coverage, output / "partial_game_source_coverage_2023.csv")
    exclusions = enriched.loc[
        ~enriched["data_quality_pass"].fillna(False).astype(bool)
        | enriched["confirmed_partial_game"].fillna(False).astype(bool)
    ].copy()
    exclusions["exclusion_reason"] = "CONFIRMED_PARTIAL_GAME"
    exclusions.loc[
        ~exclusions["data_quality_pass"].fillna(False).astype(bool),
        "exclusion_reason",
    ] = "DATA_QUALITY_FAIL"
    write_csv(exclusions, output / "exclusions_2023.csv")

    source = pd.read_csv(ROOT / "outputs" / "role_validation" / "source_coverage_by_season.csv")
    source = source.loc[source["season"].eq(FOLD3_SEASON)].copy()
    joins = pd.read_csv(ROOT / "outputs" / "role_validation" / "join_coverage.csv")
    joins = joins.loc[joins["season"].eq(FOLD3_SEASON)].copy()
    if len(source) != 1 or not bool(source.iloc[0]["complete_schema_and_games"]):
        raise AssertionError("2023 source coverage is incomplete")
    if joins.empty or not joins["coverage_rate"].eq(1.0).all():
        raise AssertionError("2023 identity joins are incomplete")
    write_csv(source, output / "source_coverage_2023.csv")
    write_csv(joins, output / "join_coverage_2023.csv")
    source_manifest = pd.DataFrame(
        [
            {"source": "canonical", "path": str(canonical_path), "sha256": file_sha256(canonical_path)},
            {"source": "cached_pbp", "path": str(pbp_path), "sha256": file_sha256(pbp_path)},
            {"source": "cached_participation", "path": str(participation_path), "sha256": file_sha256(participation_path)},
            {"source": "cached_injuries", "path": str(injuries_path), "sha256": file_sha256(injuries_path)},
            {"source": "frozen_config", "path": str(config_path), "sha256": file_sha256(config_path)},
            {"source": "fold2_frozen_config", "path": str(ROOT / "outputs" / "role_validation" / "fold_2" / "frozen_role_change_fold2_candidate.yaml"), "sha256": file_sha256(ROOT / "outputs" / "role_validation" / "fold_2" / "frozen_role_change_fold2_candidate.yaml")},
        ]
    )
    write_csv(source_manifest, output / "input_source_manifest.csv")
    manifest = {
        "stage": "precheck",
        "passed": True,
        "evaluation_executed": False,
        "allowed_seasons": [FOLD3_SEASON],
        "post_2023_seasons_read": False,
        "canonical_rows": len(enriched),
        "canonical_duplicate_keys": int(enriched.duplicated(CANONICAL_KEY, keep=False).sum()),
        "confirmed_partial_family_rows": int(enriched["confirmed_partial_game"].sum()),
        "suspected_partial_family_rows": int(enriched["suspected_partial_game"].sum()),
        "source_coverage_passed": True,
        "identity_coverage_passed": True,
        "config_integrity_passed": True,
        "temporal_design_static_checks_passed": True,
    }
    (output / "pre_run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


def execute(args: argparse.Namespace) -> int:
    output = absolute(args.output_dir)
    pre_run = json.loads((output / "pre_run_manifest.json").read_text(encoding="utf-8"))
    if not pre_run.get("passed") or pre_run.get("evaluation_executed"):
        raise AssertionError("Pre-run manifest does not authorize Fold 3")
    lock_path = output / "fold3_execution_lock.json"
    if lock_path.exists():
        raise AssertionError("Fold 3 execution lock exists; rerun prohibited")
    config_path = absolute(args.config)
    repository = repository_prechecks(config_path)
    frozen_copy = output / "frozen_role_change_fold3_candidate.yaml"
    if file_sha256(frozen_copy) != EXPECTED_CONFIG_SHA256:
        raise AssertionError("Fold 3 frozen copy hash changed")

    tests = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q",
            "tests/test_role_validation_redevelopment.py",
            "tests/test_role_validation_fold2.py",
            "tests/test_role_validation_fold3.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    (output / "pre_execution_test_results.txt").write_text(
        tests.stdout + tests.stderr, encoding="utf-8"
    )
    if tests.returncode != 0:
        raise AssertionError("Fold 3 pre-execution tests failed")

    lock = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": FOLD3_SEASON,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "start_commit": repository["start_commit"],
        "single_execution_authorized": True,
        "completed": False,
    }
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")

    candidate = yaml.safe_load(config_path.read_text(encoding="utf-8"))["candidate"]
    enriched = pd.read_csv(output / "canonical_role_2023_enriched.csv.gz", low_memory=False)
    if set(enriched["season"].astype(int).unique()) != {FOLD3_SEASON}:
        raise AssertionError("Fold 3 input is not 2023-only")

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
            allowed_seasons=[FOLD3_SEASON],
        )
        alert_parts.append(result["alerts"])
        equal_parts.append(result["equal_volume"])
        if not result["suppressed"].empty:
            suppressed_parts.append(result["suppressed"].assign(partial_policy=policy))
    alerts = pd.concat(alert_parts, ignore_index=True)
    equal = pd.concat(equal_parts, ignore_index=True)
    suppressed = pd.concat(suppressed_parts, ignore_index=True) if suppressed_parts else pd.DataFrame()
    if set(alerts["season"].astype(int).unique()) != {FOLD3_SEASON}:
        raise AssertionError("Fold 3 output contains a disallowed season")
    if not equal["equal_volume"].all() or not equal["observed_method_count"].eq(len(EXPECTED_METHODS)).all():
        raise AssertionError("Fold 3 equal-volume construction failed")

    primary_current = alerts.loc[alerts["partial_policy"].eq(PRIMARY_POLICY)].copy()
    temporal = assert_temporal_integrity(primary_current, expected_season=FOLD3_SEASON)
    methods = method_results(alerts)
    comparisons = comparison_results(alerts)
    directions = direction_results(alerts)
    blocks = block_results(alerts)
    weekly = weekly_stability(alerts, season=FOLD3_SEASON)
    feed, feed_weekly = feed_summary(alerts, season=FOLD3_SEASON)
    repeats = repeat_rates(alerts)
    overlap = rb_overlap(alerts)

    prior_2021_all = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "recommended_candidate_partial_sensitivity_alerts_2018_2021.csv.gz",
        low_memory=False,
    )
    prior_2021 = prior_2021_all.loc[
        prior_2021_all["season"].eq(2021)
        & prior_2021_all["partial_policy"].eq(PRIMARY_POLICY)
    ].copy()
    prior_2022_all = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_2" / "fold2_alerts_2022.csv.gz",
        low_memory=False,
    )
    prior_2022 = prior_2022_all.loc[
        prior_2022_all["partial_policy"].eq(PRIMARY_POLICY)
    ].copy()
    periods = {
        "redeveloped_2021": prior_2021,
        "untouched_2022": prior_2022,
        "untouched_2023": primary_current,
    }
    cross_family = cross_season_family_results(periods)
    cross_direction = cross_season_direction_results(periods)
    cross_weekly = cross_season_weekly_stability(periods)
    pooled_family, pooled_direction, pooled_weekly = pooled_untouched_results(
        prior_2022, primary_current
    )
    validation_config = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )
    gates = fold3_release_gate_table(
        methods,
        validation_config["release_gates"]["full_release"],
        cross_direction,
    )

    primary_comparisons = comparisons.loc[
        comparisons["partial_policy"].eq(PRIMARY_POLICY)
    ].set_index("role_family")
    sensitivity = comparisons.copy()
    sensitivity["sensitivity_type"] = sensitivity["partial_policy"].map(
        {
            PRIMARY_POLICY: "primary",
            "ALL_INCLUDED": "confirmed_partial_inclusion_sensitivity",
            "STRICT_SUSPECTED_EXCLUDED": "suspected_partial_exclusion_sensitivity",
        }
    )
    for metric in [
        "full_alerts", "full_evaluable_alerts", "full_precision",
        "precision_improvement", "full_reversion_rate", "reversion_improvement",
        "full_median_retention",
    ]:
        primary_values = primary_comparisons[metric].to_dict()
        sensitivity[f"delta_vs_primary_{metric}"] = sensitivity.apply(
            lambda row: row[metric] - primary_values.get(row["role_family"], float("nan")),
            axis=1,
        )

    rb_families = {"rb_carry_share", "rb_opportunity_share"}
    write_csv(alerts, output / "fold3_alerts_2023.csv.gz", compressed=True)
    write_csv(equal, output / "equal_volume_verification_2023.csv")
    write_csv(suppressed, output / "repeat_suppressed_alerts_2023.csv")
    write_csv(temporal, output / "temporal_integrity_checks_2023.csv")
    write_csv(methods, output / "family_method_results_2023.csv")
    write_csv(comparisons, output / "family_comparisons_2023.csv")
    write_csv(
        methods.loc[methods["role_family"].isin(rb_families)],
        output / "rb_family_method_results_2023.csv",
    )
    write_csv(
        comparisons.loc[comparisons["role_family"].isin(rb_families)],
        output / "rb_family_comparisons_2023.csv",
    )
    write_csv(directions, output / "direction_results_2023.csv")
    write_csv(
        directions.loc[directions["role_family"].isin(rb_families)],
        output / "rb_direction_results_2023.csv",
    )
    write_csv(blocks, output / "season_block_results_2023.csv")
    write_csv(weekly, output / "weekly_stability_2023.csv")
    write_csv(feed, output / "deduplicated_feed_summary_2023.csv")
    write_csv(feed_weekly, output / "deduplicated_weekly_volume_2023.csv")
    write_csv(repeats, output / "repeat_alert_rates_2023.csv")
    write_csv(overlap, output / "rb_family_overlap_2023.csv")
    write_csv(sensitivity, output / "partial_game_sensitivity_2023.csv")
    write_csv(cross_family, output / "cross_season_family_2021_2023.csv")
    write_csv(cross_direction, output / "cross_season_direction_2021_2023.csv")
    write_csv(cross_weekly, output / "cross_season_weekly_2021_2023.csv")
    write_csv(pooled_family, output / "pooled_untouched_family_2022_2023.csv")
    write_csv(pooled_direction, output / "pooled_untouched_direction_2022_2023.csv")
    write_csv(pooled_weekly, output / "pooled_untouched_weekly_2022_2023.csv")
    write_csv(gates, output / "fold3_gate_decisions.csv")

    lock["completed"] = True
    lock["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    lock["alert_archive_sha256"] = file_sha256(output / "fold3_alerts_2023.csv.gz")
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    rb_statuses = gates.loc[
        gates["role_family"].isin(rb_families)
    ].set_index("role_family")["fold3_candidate_status"].to_dict()
    run_manifest = {
        "stage": "execute",
        "passed": True,
        "fold3_executed_once": True,
        "test_season": FOLD3_SEASON,
        "post_2023_results_used": False,
        "fold4_executed": False,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "candidate_name": candidate["name"],
        "partial_policies": list(PARTIAL_POLICIES),
        "family_alert_method_rows": len(alerts),
        "primary_full_family_alerts": int(
            len(primary_current.loc[primary_current["method"].eq("full_propwar")])
        ),
        "equal_volume_cells": len(equal),
        "all_equal_volume": bool(equal["equal_volume"].all()),
        "all_temporal_checks_passed": bool(temporal["passed"].all()),
        "pre_execution_tests_passed": True,
        "rb_fold3_statuses": rb_statuses,
        "retired_families": ["wr_target_share", "te_target_share"],
    }
    (output / "run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(run_manifest, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    return precheck(args) if args.stage == "precheck" else execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
