from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_4"
CHECKPOINT_COMMIT = "603bd5159833e1ce11ca4ff261b0d88fd040ea73"
CHECKPOINT_TAG = "pre-fold-4-checkpoint"
INITIAL_EXECUTION_PACKAGE_COMMIT = "12cdb1bf34352392b6fba5a40c7cec82d532f4bc"
EXPECTED_CONFIG_SHA256 = "4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7"
PACKAGE_FILES = {
    "candidate_configuration": "config/role_change_fold2_candidate.yaml",
    "fold4_runner": "scripts/run_fold4_validation.py",
    "fold4_evaluator": "src/role_validation/fold4.py",
    "fold4_report_generator": "scripts/generate_fold4_report.py",
    "fold4_output_validator": "scripts/validate_fold4_outputs.py",
    "fold4_staged_scope_validator": "scripts/validate_fold4_staged_scope.py",
    "fold4_notebook_builder": "scripts/build_fold4_notebook.py",
    "fold4_execution_freezer": "scripts/freeze_fold4_execution.py",
    "shared_candidate_execution": "src/role_validation/redevelopment.py",
    "shared_partial_game_execution": "src/role_validation/partial_game.py",
    "shared_season_scope_tests": "tests/test_role_validation_redevelopment.py",
    "fold4_tests": "tests/test_role_validation_fold4.py",
    "protocol": "ROLE_CHANGE_VALIDATION_PROTOCOL.md",
    "locked_decisions": "LOCKED_DECISIONS.md",
    "release_gates": "config/role_change_validation.yaml",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> int:
    if git("branch", "--show-current") != "role-change-validation-v1":
        raise AssertionError("Fold 4 must run on role-change-validation-v1")
    head = git("rev-parse", "HEAD")
    if git("rev-list", "-n", "1", CHECKPOINT_TAG) != CHECKPOINT_COMMIT:
        raise AssertionError("Pre-Fold-4 checkpoint tag is incorrect")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", CHECKPOINT_COMMIT, head],
        cwd=ROOT,
        check=True,
    )
    paths = list(PACKAGE_FILES.values())
    dirty = git("status", "--porcelain", "--", *paths)
    if dirty:
        raise AssertionError(f"Execution package is not committed and clean:\n{dirty}")
    for path in paths:
        git("ls-files", "--error-unmatch", path)

    config_path = ROOT / PACKAGE_FILES["candidate_configuration"]
    if sha256(config_path) != EXPECTED_CONFIG_SHA256:
        raise AssertionError("Candidate configuration hash changed")
    document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    contract = document["analysis_contract"]
    expected_protected = {
        "release_gates": contract["release_gates_source_sha256"],
        "protocol": contract["protocol_sha256"],
        "locked_decisions": contract["locked_decisions_sha256"],
    }
    observed_protected = {
        name: sha256(ROOT / PACKAGE_FILES[name]) for name in expected_protected
    }
    if observed_protected != expected_protected:
        raise AssertionError(
            f"Protocol, locked decisions, or release gates changed: {observed_protected}"
        )

    OUT.mkdir(parents=True, exist_ok=True)
    prior_precheck_failure_path = OUT / "precheck_failure.json"
    prior_precheck_failure = (
        json.loads(prior_precheck_failure_path.read_text(encoding="utf-8"))
        if prior_precheck_failure_path.is_file()
        else None
    )
    frozen_config = OUT / "frozen_role_change_fold4_candidate.yaml"
    shutil.copyfile(config_path, frozen_config)
    files = {
        name: {
            "path": path,
            "sha256": sha256(ROOT / path),
        }
        for name, path in PACKAGE_FILES.items()
    }
    manifest = {
        "manifest_type": "pre_result_frozen_fold4_execution_package",
        "initial_execution_package_commit": INITIAL_EXECUTION_PACKAGE_COMMIT,
        "initial_package_frozen_before_first_2024_data_access": True,
        "frozen_before_first_2024_data_access": prior_precheck_failure is None,
        "frozen_before_2024_result_access": True,
        "prior_invalidated_precheck": prior_precheck_failure,
        "checkpoint_tag": CHECKPOINT_TAG,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "execution_package_commit": head,
        "candidate_config_sha256": sha256(config_path),
        "frozen_candidate_path": str(frozen_config.relative_to(ROOT)).replace("\\", "/"),
        "frozen_candidate_sha256": sha256(frozen_config),
        "protected_hashes": observed_protected,
        "files": files,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "fold4_results_read": False,
        "fold4_executed": False,
        "post_result_execution_code_changes_permitted": False,
    }
    (OUT / "frozen_execution_package_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
