from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE = "production-streamlit-cloud-pre-mobile-ux-v2"
ALLOWED = [
    ".streamlit/config.toml",
    "dashboard/app.py",
    "dashboard/home_page.py",
    "dashboard/research_data.py",
    "dashboard/research_ui.py",
    "dashboard/pages/01_Teams.py",
    "dashboard/pages/02_Players.py",
    "dashboard/pages/03_Games.py",
    "dashboard/pages/04_Reports.py",
    "dashboard/pages/05_Explorer.py",
    "tests/test_public_role_research_language.py",
    "tests/test_role_research.py",
    "scripts/validate_mobile_ux_scope.py",
]
PROTECTED = [
    "ROLE_CHANGE_VALIDATION_PROTOCOL.md",
    "LOCKED_DECISIONS.md",
    "config/role_change_fold2_candidate.yaml",
    "outputs/role_validation/release_gate_integrity.json",
]


def run(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=DEFAULT_BASE)
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()

    if args.staged:
        changed_raw = run("diff", "--cached", "--name-only", args.base)
    else:
        changed_raw = run("diff", "--name-only", f"{args.base}...HEAD")
    changed = [line for line in changed_raw.decode().splitlines() if line]
    unexpected = [path for path in changed if not any(fnmatch.fnmatch(path, pattern) for pattern in ALLOWED)]

    protected = []
    for relative in PROTECTED:
        baseline = run("show", f"{args.base}:{relative}")
        # Compare Git's repository bytes so Windows checkout line-ending
        # conversion cannot create a false protected-file failure. Also
        # require that the protected path has no unstaged worktree change.
        current = run("show", f":{relative}")
        worktree_unchanged = subprocess.run(
            ["git", "diff", "--quiet", "--", relative], cwd=ROOT, check=False
        ).returncode == 0
        protected.append(
            {
                "path": relative,
                "baseline_sha256": digest(baseline),
                "current_sha256": digest(current),
                "unchanged": baseline == current and worktree_unchanged,
                "worktree_unchanged": worktree_unchanged,
            }
        )

    status = "PASS" if not unexpected and all(item["unchanged"] for item in protected) else "FAIL"
    report = {
        "status": status,
        "base": args.base,
        "mode": "staged" if args.staged else "committed",
        "changed_files": changed,
        "unexpected_files": unexpected,
        "protected_files": protected,
    }
    print(json.dumps(report, indent=2))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
