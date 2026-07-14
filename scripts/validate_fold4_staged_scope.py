from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "role_validation" / "fold_4"
NOTEBOOK = "notebooks/fold_4_untouched_2024_validation.ipynb"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=check,
    )


def main() -> int:
    frozen = json.loads(
        (OUT / "frozen_execution_package_manifest.json").read_text(encoding="utf-8")
    )
    staged = [
        line.strip()
        for line in git("diff", "--cached", "--name-only").stdout.splitlines()
        if line.strip()
    ]
    disallowed = [
        path
        for path in staged
        if not (
            path.startswith("outputs/role_validation/fold_4/") or path == NOTEBOOK
        )
    ]
    package_mismatches = {
        name: {
            "expected": item["sha256"],
            "observed": sha256(ROOT / item["path"]),
        }
        for name, item in frozen["files"].items()
        if sha256(ROOT / item["path"]) != item["sha256"]
    }
    head = git("rev-parse", "HEAD").stdout.strip()
    diff_check = git("diff", "--cached", "--check", check=False)
    checks = [
        {
            "check": "staged_files_present",
            "passed": bool(staged),
            "detail": f"{len(staged)} staged paths",
        },
        {
            "check": "only_fold4_artifacts_staged",
            "passed": not disallowed,
            "detail": disallowed or "all allowed",
        },
        {
            "check": "executed_notebook_staged",
            "passed": NOTEBOOK in staged,
            "detail": NOTEBOOK,
        },
        {
            "check": "execution_package_commit_unchanged",
            "passed": head == frozen["execution_package_commit"],
            "detail": head,
        },
        {
            "check": "execution_package_hashes_unchanged",
            "passed": not package_mismatches,
            "detail": package_mismatches or f"{len(frozen['files'])} matched",
        },
        {
            "check": "cached_diff_check",
            "passed": diff_check.returncode == 0,
            "detail": (diff_check.stdout + diff_check.stderr).strip() or "clean",
        },
        {
            "check": "dashboard_not_staged",
            "passed": not any(path.startswith("dashboard/") for path in staged),
            "detail": "none",
        },
    ]
    result = {
        "validator": "fold4_staged_scope_validator",
        "passed": all(item["passed"] for item in checks),
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "staged_paths": staged,
        "checks": checks,
    }
    (OUT / "staged_scope_validation.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
