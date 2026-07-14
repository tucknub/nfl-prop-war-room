from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

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
    cross_season_direction_results,
    cross_season_family_results,
    cross_season_weekly_stability,
)
from role_validation.fold4 import (  # noqa: E402
    ACTIVE_FAMILIES,
    EXPECTED_CONFIG_SHA256,
    FOLD4_SEASON,
    assert_fold4_config_integrity,
    concentration_tables,
    fold4_release_gate_table,
    gate_detail_table,
    overlap_dependence,
    partial_alert_status,
    pooled_period_results,
    recommendation_table,
    retention_diagnostics,
    subgroup_stability,
)
from role_validation.partial_game import (  # noqa: E402
    build_partial_game_status,
    load_explicit_injury_sources,
)
from role_validation.redevelopment import (  # noqa: E402
    CANONICAL_KEY,
    EXPECTED_METHODS,
    run_candidate,
)


CHECKPOINT_COMMIT = "603bd5159833e1ce11ca4ff261b0d88fd040ea73"
CHECKPOINT_TAG = "pre-fold-4-checkpoint"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and execute the frozen candidate once on untouched 2024 Fold 4."
    )
    parser.add_argument("--stage", choices=["precheck", "execute"], required=True)
    parser.add_argument("--config", default="config/role_change_fold2_candidate.yaml")
    parser.add_argument(
        "--canonical", default="outputs/role_validation/canonical_player_week_role.csv.gz"
    )
    parser.add_argument("--source-cache-dir", default="data/raw/role_validation")
    parser.add_argument("--output-dir", default="outputs/role_validation/fold_4")
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


def _season_values(frame: pd.DataFrame, path: Path) -> pd.Series:
    if "season" in frame:
        return pd.to_numeric(frame["season"], errors="coerce")
    if "nflverse_game_id" in frame:
        return pd.to_numeric(
            frame["nflverse_game_id"].astype(str).str[:4], errors="coerce"
        )
    raise ValueError(f"Cannot determine season in {path}")


def load_local_season(
    path: Path, season: int, *, chunksize: int
) -> tuple[pd.DataFrame, list[int]]:
    selected = []
    physically_opened: set[int] = set()
    for chunk in pd.read_csv(path, chunksize=chunksize, low_memory=False):
        values = _season_values(chunk, path)
        physically_opened.update(values.dropna().astype(int).unique().tolist())
        selected_chunk = chunk.loc[values.eq(season)].copy()
        if "season" not in selected_chunk:
            selected_chunk["season"] = values.loc[selected_chunk.index].astype("Int64")
        selected.append(selected_chunk)
    result = pd.concat(selected, ignore_index=True) if selected else pd.DataFrame()
    observed = set(pd.to_numeric(result["season"], errors="raise").astype(int).unique())
    if observed != {season}:
        raise AssertionError(f"{path.name} selected seasons {sorted(observed)}")
    return result, sorted(physically_opened)


def select_cache_path(cache_dir: Path, name: str) -> Path:
    matches = sorted(cache_dir.glob(f"{name}_*.csv.gz"))
    if not matches:
        raise FileNotFoundError(f"No cached {name} source in {cache_dir}")
    return max(matches, key=lambda item: item.stat().st_size)


def assert_execution_package(output: Path, config_path: Path) -> dict[str, Any]:
    manifest_path = output / "frozen_execution_package_manifest.json"
    if not manifest_path.is_file():
        raise AssertionError("Frozen Fold 4 execution manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    tag_commit = git("rev-list", "-n", "1", CHECKPOINT_TAG)
    if branch != "role-change-validation-v1":
        raise AssertionError(f"Unexpected branch: {branch}")
    if tag_commit != CHECKPOINT_COMMIT:
        raise AssertionError("Pre-Fold-4 tag does not resolve to the checkpoint")
    if manifest["checkpoint_commit"] != CHECKPOINT_COMMIT:
        raise AssertionError("Frozen manifest checkpoint differs")
    if manifest["execution_package_commit"] != head:
        raise AssertionError(
            f"HEAD {head} differs from execution package commit "
            f"{manifest['execution_package_commit']}"
        )
    package_paths = [item["path"] for item in manifest["files"].values()]
    dirty = git("status", "--porcelain", "--", *package_paths)
    if dirty:
        raise AssertionError(f"Frozen execution files changed:\n{dirty}")
    mismatches = {
        name: {
            "expected": item["sha256"],
            "observed": file_sha256(ROOT / item["path"]),
        }
        for name, item in manifest["files"].items()
        if file_sha256(ROOT / item["path"]) != item["sha256"]
    }
    if mismatches:
        raise AssertionError(f"Frozen execution hashes changed: {mismatches}")
    if file_sha256(config_path) != EXPECTED_CONFIG_SHA256:
        raise AssertionError("Candidate configuration hash changed")
    frozen_copy = output / "frozen_role_change_fold4_candidate.yaml"
    if file_sha256(frozen_copy) != EXPECTED_CONFIG_SHA256:
        raise AssertionError("Fold 4 frozen candidate copy changed")
    integrity = assert_fold4_config_integrity(
        config_path,
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "FOLD_1_DIAGNOSTIC_AND_REDEVELOPMENT_REPORT.md",
        ROOT / "outputs" / "role_validation" / "fold_2"
        / "frozen_role_change_fold2_candidate.yaml",
        ROOT / "outputs" / "role_validation" / "fold_2"
        / "frozen_config_fingerprint.json",
        ROOT / "outputs" / "role_validation" / "fold_3"
        / "frozen_role_change_fold3_candidate.yaml",
        ROOT / "outputs" / "role_validation" / "fold_3"
        / "frozen_config_fingerprint.json",
    )
    return {
        "branch": branch,
        "head": head,
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": tag_commit,
        "execution_manifest_sha256": file_sha256(manifest_path),
        "config_integrity_checks": integrity["checks"],
        "execution_files_verified": len(manifest["files"]),
    }


def _source_row(
    source: str,
    path: str,
    available: list[int],
    *,
    sha256: str | None,
    purpose: str,
    admitted_feature: list[int] | None = None,
    admitted_alert: list[int] | None = None,
    admitted_outcome: list[int] | None = None,
) -> dict[str, Any]:
    joined = lambda values: "|".join(map(str, values or []))
    return {
        "source": source,
        "path": path,
        "sha256": sha256,
        "purpose": purpose,
        "source_seasons_physically_available": joined(available),
        "source_seasons_physically_opened": joined(available),
        "seasons_admitted_to_feature_generation": joined(admitted_feature),
        "seasons_admitted_to_alert_selection": joined(admitted_alert),
        "seasons_admitted_to_outcome_evaluation": joined(admitted_outcome),
    }


def _timestamp_prechecks(enriched: pd.DataFrame) -> pd.DataFrame:
    confirmed = enriched.loc[
        enriched["confirmed_partial_game"].fillna(False).astype(bool)
    ].copy()
    evidence = pd.to_datetime(confirmed["evidence_available_at_utc"], utc=True, errors="coerce")
    trigger_end = pd.to_datetime(confirmed["trigger_end_proxy_utc"], utc=True, errors="coerce")
    next_game = pd.to_datetime(confirmed["next_game_kickoff_utc"], utc=True, errors="coerce")
    checks = {
        "canonical_season_is_2024": set(enriched["season"].astype(int).unique()) == {2024},
        "trigger_timestamps_present": enriched["trigger_kickoff_utc"].notna().all(),
        "confirmed_evidence_timestamp_present": evidence.notna().all(),
        "confirmed_evidence_after_trigger_game": evidence.ge(trigger_end).all(),
        "confirmed_evidence_before_next_game": evidence.lt(next_game).all(),
        "no_confirmed_and_suspected_overlap": not (
            enriched["confirmed_partial_game"].fillna(False).astype(bool)
            & enriched["suspected_partial_game"].fillna(False).astype(bool)
        ).any(),
    }
    return pd.DataFrame([{"check": name, "passed": bool(value)} for name, value in checks.items()])


def precheck(args: argparse.Namespace) -> int:
    output = absolute(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    if (output / "pre_run_manifest.json").exists():
        raise AssertionError("Fold 4 precheck already exists; repeated precheck prohibited")
    config_path = absolute(args.config)
    repository = assert_execution_package(output, config_path)
    validation_config = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )

    canonical_path = absolute(args.canonical)
    canonical, canonical_opened = load_local_season(
        canonical_path, FOLD4_SEASON, chunksize=10_000
    )
    audit = canonical_audit(
        canonical,
        validation_config["data"]["required_columns"],
        expected_season=FOLD4_SEASON,
    )
    write_csv(audit, output / "data_audit_2024.csv")
    write_csv(
        missingness_table(canonical, expected_season=FOLD4_SEASON),
        output / "missingness_2024.csv",
    )

    cache_dir = absolute(args.source_cache_dir)
    cache_inputs: dict[str, tuple[pd.DataFrame, Path, list[int]]] = {}
    for name in ["pbp", "participation", "injuries"]:
        path = select_cache_path(cache_dir, name)
        frame, opened = load_local_season(path, FOLD4_SEASON, chunksize=100_000)
        cache_inputs[name] = (frame, path, opened)
    explicit_pbp, explicit_rosters, schedules = load_explicit_injury_sources(
        [FOLD4_SEASON]
    )
    explicit_paths = {
        "explicit_nflverse_pbp": output / "explicit_pbp_2024.csv.gz",
        "explicit_nflverse_rosters": output / "explicit_rosters_2024.csv.gz",
        "explicit_nflverse_schedules": output / "explicit_schedules_2024.csv.gz",
    }
    for frame, path in [
        (explicit_pbp, explicit_paths["explicit_nflverse_pbp"]),
        (explicit_rosters, explicit_paths["explicit_nflverse_rosters"]),
        (schedules, explicit_paths["explicit_nflverse_schedules"]),
    ]:
        write_csv(frame, path, compressed=True)

    partial = build_partial_game_status(
        canonical,
        selected_pbp=cache_inputs["pbp"][0],
        participation=cache_inputs["participation"][0],
        injuries=cache_inputs["injuries"][0],
        explicit_pbp=explicit_pbp,
        full_rosters=explicit_rosters,
        schedules=schedules,
        seasons=[FOLD4_SEASON],
    )
    enriched = partial.canonical
    if len(enriched) != len(canonical) or enriched.duplicated(CANONICAL_KEY).any():
        raise AssertionError("Partial-game enrichment changed canonical grain")
    write_csv(enriched, output / "canonical_role_2024_enriched.csv.gz", compressed=True)
    write_csv(partial.evidence_ledger, output / "partial_game_evidence_2024.csv")
    write_csv(partial.source_coverage, output / "partial_game_source_coverage_2024.csv")
    exclusions = enriched.loc[
        ~enriched["data_quality_pass"].fillna(False).astype(bool)
        | enriched["confirmed_partial_game"].fillna(False).astype(bool)
    ].copy()
    exclusions["exclusion_reason"] = "CONFIRMED_PARTIAL_GAME"
    exclusions.loc[
        ~exclusions["data_quality_pass"].fillna(False).astype(bool),
        "exclusion_reason",
    ] = "DATA_QUALITY_FAIL"
    write_csv(exclusions, output / "exclusions_2024.csv")

    source_path = ROOT / "outputs" / "role_validation" / "source_coverage_by_season.csv"
    source_all = pd.read_csv(source_path)
    source_seasons = sorted(source_all["season"].astype(int).unique())
    source = source_all.loc[source_all["season"].eq(FOLD4_SEASON)].copy()
    join_path = ROOT / "outputs" / "role_validation" / "join_coverage.csv"
    joins_all = pd.read_csv(join_path)
    join_seasons = sorted(joins_all["season"].astype(int).unique())
    joins = joins_all.loc[joins_all["season"].eq(FOLD4_SEASON)].copy()
    if len(source) != 1 or not bool(source.iloc[0]["complete_schema_and_games"]):
        raise AssertionError("2024 source coverage is incomplete")
    if joins.empty or not joins["coverage_rate"].eq(1.0).all():
        raise AssertionError("2024 identity/opportunity joins are incomplete")
    write_csv(source, output / "source_coverage_2024.csv")
    write_csv(joins, output / "join_coverage_2024.csv")

    temporal = _timestamp_prechecks(enriched)
    if not temporal["passed"].all():
        raise AssertionError(
            f"Pre-run temporal checks failed: {temporal.loc[~temporal['passed'], 'check'].tolist()}"
        )
    write_csv(temporal, output / "temporal_precheck_2024.csv")

    source_rows = [
        _source_row(
            "canonical",
            str(canonical_path),
            canonical_opened,
            sha256=file_sha256(canonical_path),
            purpose="canonical_feature_alert_and_outcome_input",
            admitted_feature=[2024],
            admitted_alert=[2024],
            admitted_outcome=[2024],
        )
    ]
    for name, (_, path, opened) in cache_inputs.items():
        source_rows.append(
            _source_row(
                f"cached_{name}",
                str(path),
                opened,
                sha256=file_sha256(path),
                purpose="2024_partial_game_and_quality_enrichment",
                admitted_feature=[2024],
                admitted_alert=[2024],
            )
        )
    for name, path in explicit_paths.items():
        source_rows.append(
            _source_row(
                name,
                str(path),
                [2024],
                sha256=file_sha256(path),
                purpose="materialized_2024_explicit_injury_input",
                admitted_feature=[2024],
                admitted_alert=[2024],
            )
        )
    source_rows.extend(
        [
            _source_row(
                "source_coverage_metadata",
                str(source_path),
                source_seasons,
                sha256=file_sha256(source_path),
                purpose="pre_run_completeness_audit_only",
            ),
            _source_row(
                "join_coverage_metadata",
                str(join_path),
                join_seasons,
                sha256=file_sha256(join_path),
                purpose="pre_run_join_audit_only",
            ),
            _source_row(
                "candidate_configuration",
                str(config_path),
                [],
                sha256=file_sha256(config_path),
                purpose="frozen_candidate_rules",
            ),
        ]
    )
    prior_paths = {
        "redeveloped_2021_alert_archive": ROOT / "outputs" / "role_validation"
        / "fold_1_diagnostics" / "recommended_candidate_partial_sensitivity_alerts_2018_2021.csv.gz",
        "untouched_2022_alert_archive": ROOT / "outputs" / "role_validation"
        / "fold_2" / "fold2_alerts_2022.csv.gz",
        "untouched_2023_alert_archive": ROOT / "outputs" / "role_validation"
        / "fold_3" / "fold3_alerts_2023.csv.gz",
    }
    for name, path in prior_paths.items():
        season = int(name.split("_")[1])
        source_rows.append(
            _source_row(
                name,
                str(path),
                [season],
                sha256=file_sha256(path),
                purpose="cross_season_reporting_only_not_2024_generation",
            )
        )
    access = pd.DataFrame(source_rows)
    write_csv(access, output / "file_access_manifest.csv")
    write_csv(
        access[["source", "path", "sha256", "purpose"]],
        output / "input_source_manifest.csv",
    )

    audit_checks = pd.DataFrame(
        [
            {"check": "canonical_grain_unique", "passed": not enriched.duplicated(CANONICAL_KEY).any()},
            {"check": "required_fields_complete", "passed": int(audit.at[0, "required_null_cells"]) == 0},
            {"check": "identity_coverage_complete", "passed": float(audit.at[0, "identity_coverage"]) == 1.0},
            {"check": "played_weeks_complete", "passed": int(audit.at[0, "observed_weeks"]) == 18},
            {"check": "source_schema_and_games_complete", "passed": bool(source.iloc[0]["complete_schema_and_games"])},
            {"check": "identity_and_opportunity_joins_complete", "passed": bool(joins["coverage_rate"].eq(1.0).all())},
            {"check": "execution_hashes_verified", "passed": True},
            {"check": "temporal_precheck_passed", "passed": bool(temporal["passed"].all())},
        ]
    )
    write_csv(audit_checks, output / "data_audit_checks_2024.csv")
    manifest = {
        "stage": "precheck",
        "passed": bool(audit_checks["passed"].all()),
        "evaluation_executed": False,
        "test_season": 2024,
        "source_seasons_physically_available": sorted(
            set(canonical_opened)
            | set().union(*(set(value[2]) for value in cache_inputs.values()))
            | set(source_seasons)
            | set(join_seasons)
        ),
        "source_seasons_physically_opened": sorted(
            set(canonical_opened)
            | set().union(*(set(value[2]) for value in cache_inputs.values()))
            | set(source_seasons)
            | set(join_seasons)
        ),
        "seasons_admitted_to_feature_generation": [2024],
        "seasons_admitted_to_alert_selection": [2024],
        "seasons_admitted_to_outcome_evaluation": [2024],
        "seasons_admitted_to_cross_season_reporting": [2021, 2022, 2023, 2024],
        "post_2024_values_admitted": False,
        "canonical_rows": len(enriched),
        "canonical_duplicate_keys": int(enriched.duplicated(CANONICAL_KEY, keep=False).sum()),
        "confirmed_partial_family_rows": int(enriched["confirmed_partial_game"].sum()),
        "suspected_partial_family_rows": int(enriched["suspected_partial_game"].sum()),
        "repository": repository,
    }
    (output / "pre_run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["passed"] else 2


def _load_prior_alerts() -> dict[str, pd.DataFrame]:
    prior_2021_all = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "recommended_candidate_partial_sensitivity_alerts_2018_2021.csv.gz",
        low_memory=False,
    )
    prior_2022_all = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_2" / "fold2_alerts_2022.csv.gz",
        low_memory=False,
    )
    prior_2023_all = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_3" / "fold3_alerts_2023.csv.gz",
        low_memory=False,
    )
    return {
        "redeveloped_2021": prior_2021_all.loc[
            prior_2021_all["season"].eq(2021)
            & prior_2021_all["partial_policy"].eq(PRIMARY_POLICY)
            & prior_2021_all["role_family"].isin(ACTIVE_FAMILIES)
        ].copy(),
        "untouched_2022": prior_2022_all.loc[
            prior_2022_all["partial_policy"].eq(PRIMARY_POLICY)
            & prior_2022_all["role_family"].isin(ACTIVE_FAMILIES)
        ].copy(),
        "untouched_2023": prior_2023_all.loc[
            prior_2023_all["partial_policy"].eq(PRIMARY_POLICY)
            & prior_2023_all["role_family"].isin(ACTIVE_FAMILIES)
        ].copy(),
    }


def _individual_season_statuses(gates_2024: pd.DataFrame) -> pd.DataFrame:
    rows = []
    fold1 = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_1_diagnostics"
        / "recommended_candidate_locked_gate_diagnostic_2021.csv"
    )
    for row in fold1.loc[fold1["role_family"].isin(ACTIVE_FAMILIES)].itertuples(index=False):
        rows.append(
            {
                "period": "redeveloped_2021",
                "season": 2021,
                "role_family": row.role_family,
                "archived_status": row.point_gate_result,
                "frozen_before_holdout": bool(row.frozen_before_2021),
                "interpretation": "development diagnostic; not untouched",
            }
        )
    fold2 = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_2" / "release_gate_results_2022.csv"
    )
    for row in fold2.loc[fold2["role_family"].isin(ACTIVE_FAMILIES)].itertuples(index=False):
        rows.append(
            {
                "period": "untouched_2022",
                "season": 2022,
                "role_family": row.role_family,
                "archived_status": row.status,
                "frozen_before_holdout": bool(row.check_frozen_before_holdout),
                "interpretation": "preserved archived Fold 2 decision",
            }
        )
    fold3 = pd.read_csv(
        ROOT / "outputs" / "role_validation" / "fold_3" / "fold3_gate_decisions.csv"
    )
    for row in fold3.loc[fold3["role_family"].isin(ACTIVE_FAMILIES)].itertuples(index=False):
        rows.append(
            {
                "period": "untouched_2023",
                "season": 2023,
                "role_family": row.role_family,
                "archived_status": row.fold3_candidate_status,
                "frozen_before_holdout": bool(row.check_frozen_before_holdout),
                "interpretation": "preserved archived Fold 3 decision",
            }
        )
    for row in gates_2024.loc[gates_2024["role_family"].isin(ACTIVE_FAMILIES)].itertuples(index=False):
        rows.append(
            {
                "period": "untouched_2024",
                "season": 2024,
                "role_family": row.role_family,
                "archived_status": row.fold4_candidate_status,
                "frozen_before_holdout": bool(row.check_frozen_before_holdout),
                "interpretation": "Fold 4 locked point-gate decision",
            }
        )
    return pd.DataFrame(rows)


def execute(args: argparse.Namespace) -> int:
    output = absolute(args.output_dir)
    pre_run = json.loads((output / "pre_run_manifest.json").read_text(encoding="utf-8"))
    if not pre_run.get("passed") or pre_run.get("evaluation_executed"):
        raise AssertionError("Pre-run manifest does not authorize Fold 4")
    lock_path = output / "fold4_execution_lock.json"
    if lock_path.exists():
        raise AssertionError("Fold 4 execution lock exists; rerun prohibited")
    config_path = absolute(args.config)
    repository = assert_execution_package(output, config_path)

    tests = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_role_validation_redevelopment.py",
            "tests/test_role_validation_fold2.py",
            "tests/test_role_validation_fold3.py",
            "tests/test_role_validation_fold4.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    (output / "pre_execution_test_results.txt").write_text(
        tests.stdout + tests.stderr, encoding="utf-8"
    )
    if tests.returncode != 0:
        raise AssertionError("Fold 4 pre-execution tests failed")

    lock = {
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": FOLD4_SEASON,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "execution_package_commit": repository["head"],
        "execution_manifest_sha256": repository["execution_manifest_sha256"],
        "single_execution_authorized": True,
        "completed": False,
    }
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")

    candidate = yaml.safe_load(config_path.read_text(encoding="utf-8"))["candidate"]
    enriched_all = pd.read_csv(
        output / "canonical_role_2024_enriched.csv.gz", low_memory=False
    )
    if set(enriched_all["season"].astype(int).unique()) != {FOLD4_SEASON}:
        raise AssertionError("Fold 4 input is not 2024-only")
    enriched = enriched_all.loc[
        enriched_all["role_family"].isin(ACTIVE_FAMILIES)
    ].copy()
    if set(enriched["role_family"].unique()) != set(ACTIVE_FAMILIES):
        raise AssertionError("Active-family input is incomplete")

    alert_parts = []
    equal_parts = []
    suppressed_parts = []
    feature_cache: dict[tuple[Any, ...], pd.DataFrame] = {}
    for policy in PARTIAL_POLICIES:
        result = run_candidate(
            enriched,
            candidate,
            partial_policy=policy,
            feature_cache=feature_cache,
            allowed_seasons=[FOLD4_SEASON],
            role_families=ACTIVE_FAMILIES,
        )
        alert_parts.append(result["alerts"])
        equal_parts.append(result["equal_volume"])
        if not result["suppressed"].empty:
            suppressed_parts.append(result["suppressed"].assign(partial_policy=policy))
    alerts = pd.concat(alert_parts, ignore_index=True)
    equal = pd.concat(equal_parts, ignore_index=True)
    suppressed = (
        pd.concat(suppressed_parts, ignore_index=True)
        if suppressed_parts
        else pd.DataFrame()
    )
    if set(alerts["season"].astype(int).unique()) != {FOLD4_SEASON}:
        raise AssertionError("Fold 4 output contains a disallowed season")
    if set(alerts["role_family"].unique()) != set(ACTIVE_FAMILIES):
        raise AssertionError("Retired family entered Fold 4 alert generation")
    if not equal["equal_volume"].all() or not equal["observed_method_count"].eq(
        len(EXPECTED_METHODS)
    ).all():
        raise AssertionError("Fold 4 equal-volume construction failed")

    primary_current = alerts.loc[
        alerts["partial_policy"].eq(PRIMARY_POLICY)
    ].copy()
    temporal = assert_temporal_integrity(
        primary_current, expected_season=FOLD4_SEASON
    )
    methods = method_results(alerts)
    comparisons = comparison_results(alerts)
    directions = direction_results(alerts)
    blocks = block_results(alerts)
    weekly = weekly_stability(alerts, season=FOLD4_SEASON)
    feed, feed_weekly = feed_summary(alerts, season=FOLD4_SEASON)
    repeats = repeat_rates(alerts)
    overlap = rb_overlap(alerts)
    subgroup, baseline_thresholds = subgroup_stability(alerts)
    concentration_entities, concentration_summary = concentration_tables(alerts)
    overlap_metrics = overlap_dependence(alerts)
    retention = retention_diagnostics(alerts)
    partial_status = partial_alert_status(alerts)

    prior = _load_prior_alerts()
    periods = {**prior, "untouched_2024": primary_current}
    cross_family = cross_season_family_results(periods)
    cross_direction = cross_season_direction_results(periods)
    cross_weekly = cross_season_weekly_stability(periods)
    pooled_22_23 = pooled_period_results(
        [prior["untouched_2022"], prior["untouched_2023"]],
        period="pooled_untouched_2022_2023",
        expected_seasons=[2022, 2023],
    )
    pooled_22_24 = pooled_period_results(
        [prior["untouched_2022"], prior["untouched_2023"], primary_current],
        period="pooled_untouched_2022_2024",
        expected_seasons=[2022, 2023, 2024],
    )
    validation_config = yaml.safe_load(
        (ROOT / "config" / "role_change_validation.yaml").read_text(encoding="utf-8")
    )
    release_gates = validation_config["release_gates"]["full_release"]
    gates = fold4_release_gate_table(methods, release_gates, cross_direction)
    gate_details = gate_detail_table(gates, release_gates)
    recommendations = recommendation_table(gates, integrity_passed=True)
    season_statuses = _individual_season_statuses(gates)

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
        "full_alerts",
        "full_evaluable_alerts",
        "full_precision",
        "precision_improvement",
        "full_reversion_rate",
        "reversion_improvement",
        "full_median_retention",
    ]:
        primary_values = primary_comparisons[metric].to_dict()
        sensitivity[f"delta_vs_primary_{metric}"] = sensitivity.apply(
            lambda row: row[metric]
            - primary_values.get(row["role_family"], float("nan")),
            axis=1,
        )

    write_csv(alerts, output / "fold4_alerts_2024.csv.gz", compressed=True)
    write_csv(equal, output / "equal_volume_verification_2024.csv")
    write_csv(suppressed, output / "repeat_suppressed_alerts_2024.csv")
    write_csv(temporal, output / "temporal_integrity_checks_2024.csv")
    write_csv(methods, output / "active_family_method_results_2024.csv")
    write_csv(comparisons, output / "active_family_comparisons_2024.csv")
    write_csv(directions, output / "direction_results_2024.csv")
    write_csv(blocks, output / "season_block_results_2024.csv")
    write_csv(weekly, output / "weekly_stability_2024.csv")
    write_csv(feed, output / "deduplicated_feed_summary_2024.csv")
    write_csv(feed_weekly, output / "deduplicated_weekly_volume_2024.csv")
    write_csv(repeats, output / "repeat_alert_rates_2024.csv")
    write_csv(overlap, output / "rb_family_overlap_2024.csv")
    write_csv(sensitivity, output / "partial_game_sensitivity_2024.csv")
    write_csv(partial_status, output / "partial_alert_status_2024.csv")
    write_csv(subgroup, output / "subgroup_stability_2024.csv")
    write_csv(baseline_thresholds, output / "baseline_stability_thresholds_2024.csv")
    write_csv(concentration_entities, output / "concentration_entities_2024.csv")
    write_csv(concentration_summary, output / "concentration_summary_2024.csv")
    write_csv(overlap_metrics, output / "overlap_dependence_2024.csv")
    write_csv(retention, output / "retention_outlier_diagnostics_2024.csv")
    write_csv(cross_family, output / "cross_season_family_2021_2024.csv")
    write_csv(cross_direction, output / "cross_season_direction_2021_2024.csv")
    write_csv(cross_weekly, output / "cross_season_weekly_2021_2024.csv")
    for suffix, frame in zip(["family", "direction", "weekly"], pooled_22_23):
        write_csv(frame, output / f"pooled_untouched_{suffix}_2022_2023.csv")
    for suffix, frame in zip(["family", "direction", "weekly"], pooled_22_24):
        write_csv(frame, output / f"pooled_untouched_{suffix}_2022_2024.csv")
    write_csv(gates, output / "fold4_gate_decisions.csv")
    write_csv(gate_details, output / "fold4_gate_details.csv")
    write_csv(recommendations, output / "fold4_family_recommendations.csv")
    write_csv(season_statuses, output / "individual_season_gate_status_2021_2024.csv")

    lock["completed"] = True
    lock["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    lock["alert_archive_sha256"] = file_sha256(
        output / "fold4_alerts_2024.csv.gz"
    )
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    statuses = gates.loc[gates["role_family"].isin(ACTIVE_FAMILIES)].set_index(
        "role_family"
    )["fold4_candidate_status"].to_dict()
    recs = recommendations.set_index("role_family")["recommendation"].to_dict()
    run_manifest = {
        "stage": "execute",
        "passed": True,
        "fold4_executed_once": True,
        "test_season": 2024,
        "2025_results_used": False,
        "post_result_redevelopment_performed": False,
        "config_sha256": EXPECTED_CONFIG_SHA256,
        "execution_package_commit": repository["head"],
        "candidate_name": candidate["name"],
        "active_families": list(ACTIVE_FAMILIES),
        "retired_families": ["wr_target_share", "te_target_share"],
        "partial_policies": list(PARTIAL_POLICIES),
        "primary_policy": PRIMARY_POLICY,
        "family_alert_method_rows": len(alerts),
        "equal_volume_cells": len(equal),
        "all_equal_volume": bool(equal["equal_volume"].all()),
        "all_temporal_checks_passed": bool(temporal["passed"].all()),
        "pre_execution_tests_passed": True,
        "fold4_statuses": statuses,
        "recommendations": recs,
        "source_seasons_physically_available": pre_run[
            "source_seasons_physically_available"
        ],
        "source_seasons_physically_opened": pre_run[
            "source_seasons_physically_opened"
        ],
        "seasons_admitted_to_feature_generation": [2024],
        "seasons_admitted_to_alert_selection": [2024],
        "seasons_admitted_to_outcome_evaluation": [2024],
        "seasons_admitted_to_cross_season_reporting": [2021, 2022, 2023, 2024],
    }
    (output / "run_manifest.json").write_text(
        json.dumps(run_manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(run_manifest, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    try:
        return precheck(args) if args.stage == "precheck" else execute(args)
    except Exception as error:
        output = absolute(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        failure_path = output / f"{args.stage}_failure.json"
        failure_path.write_text(
            json.dumps(
                {
                    "stage": args.stage,
                    "passed": False,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "fold4_execution_invalidated": args.stage == "execute",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        raise


if __name__ == "__main__":
    raise SystemExit(main())
