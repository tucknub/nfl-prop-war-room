from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "cec6244e0987ebfdc2e9c0138f0a707aec867887"
OUT = ROOT / "outputs" / "weekly_role_report_calibration"
ALLOWED = [
    "dashboard/home_page.py",
    "dashboard/pages/02_Players.py",
    "dashboard/research_data.py",
    "dashboard/research_ui.py",
    "dashboard/weekly_report.py",
    "docs/propwar/CURRENT_PHASE.md",
    "outputs/weekly_role_report_calibration/*",
    "scripts/run_weekly_role_report_calibration.py",
    "scripts/validate_weekly_role_report_calibration.py",
    "scripts/validate_weekly_role_report_calibration_scope.py",
    "tests/test_weekly_role_report.py",
]
PROTECTED = [
    "docs/propwar/PROJECT_BLUEPRINT.md",
    "docs/propwar/LOCKED_DECISIONS.md",
    "LOCKED_DECISIONS.md",
    "ROLE_CHANGE_VALIDATION_PROTOCOL.md",
    "outputs/role_validation/release_gate_integrity.json",
    "outputs/role_validation/fold_2/frozen_role_change_fold2_candidate.yaml",
    "outputs/role_validation/fold_2/frozen_config_fingerprint.json",
    "outputs/role_validation/fold_3/frozen_role_change_fold3_candidate.yaml",
    "outputs/role_validation/fold_4/frozen_role_change_fold4_candidate.yaml",
    "outputs/role_validation/fold_4/frozen_execution_package_manifest.json",
]
PRESERVED_OUTPUTS = [
    "outputs/propwar_correctness_audit",
    "outputs/weekly_role_report",
]


def _run(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()
    if args.staged:
        changed = _run("diff", "--cached", "--name-only", BASE).decode().splitlines()
    else:
        tracked = _run("diff", "--name-only", BASE).decode().splitlines()
        untracked = _run("ls-files", "--others", "--exclude-standard").decode().splitlines()
        changed = sorted(set(tracked + untracked))

    unexpected = [
        path
        for path in changed
        if path and not any(fnmatch.fnmatch(path, pattern) for pattern in ALLOWED)
    ]
    protected = []
    for relative in PROTECTED:
        baseline = _run("show", f"{BASE}:{relative}")
        current = (ROOT / relative).read_bytes()
        protected.append(
            {
                "path": relative,
                "baseline_sha256": _sha(baseline),
                "worktree_sha256": _sha(current),
                "unchanged": _sha(baseline) == _sha(current),
            }
        )
    preserved_outputs = []
    for relative in PRESERVED_OUTPUTS:
        paths = _run("diff", "--name-only", BASE, "--", relative).decode().splitlines()
        preserved_outputs.append(
            {"path": relative, "changed_files": paths, "unchanged": not paths}
        )

    status = (
        "PASS"
        if not unexpected
        and all(item["unchanged"] for item in protected)
        and all(item["unchanged"] for item in preserved_outputs)
        else "FAIL"
    )
    payload = {
        "status": status,
        "baseline_commit": BASE,
        "mode": "staged" if args.staged else "worktree",
        "changed_files": changed,
        "unexpected_files": unexpected,
        "protected_files": protected,
        "preserved_output_directories": preserved_outputs,
    }
    if not args.no_write:
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "protected_scope_validation.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(payload, indent=2))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
