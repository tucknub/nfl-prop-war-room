from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "propwar_correctness_audit"
BASE = "e939b886c9b75d6a06eaf9bf95dc8ec1a1e093ad"
ALLOWED = [
    "dashboard/research_data.py",
    "dashboard/research_ui.py",
    "dashboard/pages/01_Teams.py",
    "dashboard/pages/02_Players.py",
    "dashboard/pages/04_Reports.py",
    "docs/propwar/CURRENT_PHASE.md",
    "outputs/propwar_correctness_audit/*_after_fix.csv",
    "outputs/propwar_correctness_audit/*_after_fix.json",
    "outputs/propwar_correctness_audit/FIX_VALIDATION_REPORT.md",
    "outputs/propwar_correctness_audit/COMMANDS_RUN_FIXES.md",
    "scripts/run_targeted_correctness_audit.py",
    "scripts/run_targeted_correctness_fix_validation.py",
    "scripts/validate_targeted_correctness_outputs.py",
    "scripts/validate_targeted_correctness_after_fix.py",
    "scripts/validate_targeted_correctness_fix_scope.py",
    "tests/test_targeted_correctness_audit.py",
    "tests/test_targeted_correctness_fixes.py",
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


def canonical_sha(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    tracked = subprocess.check_output(["git", "diff", "--name-only", BASE, "--"], cwd=ROOT, text=True).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True
    ).splitlines()
    changed = sorted(set(path.replace("\\", "/") for path in tracked + untracked if path))
    violations = [path for path in changed if not any(fnmatch.fnmatch(path, pattern) for pattern in ALLOWED)]
    hashes = []
    for relative in PROTECTED:
        baseline = subprocess.check_output(["git", "show", f"{BASE}:{relative}"], cwd=ROOT)
        current = (ROOT / relative).read_bytes()
        before, after = canonical_sha(baseline), canonical_sha(current)
        hashes.append(
            {
                "path": relative,
                "baseline_sha256": before,
                "worktree_sha256": after,
                "match": before == after,
                "hash_basis": "canonical LF bytes",
            }
        )
    violations.extend(item["path"] for item in hashes if not item["match"] and item["path"] not in violations)
    payload = {
        "baseline_commit": BASE,
        "changed_paths": changed,
        "allowed_patterns": ALLOWED,
        "violations": violations,
        "protected_hashes": hashes,
        "protected_files_unchanged": not violations,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "protected_file_validation_after_fix.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    final_path = OUT / "final_validation_after_fix.json"
    if final_path.exists():
        final = json.loads(final_path.read_text(encoding="utf-8"))
        final["acceptance_gates"]["protected_files_unchanged"] = not violations
        final_path.write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    if violations:
        print("FIX SCOPE VALIDATION FAILED")
        print("\n".join(f"- {path}" for path in violations))
        return 1
    print(f"FIX SCOPE VALIDATION PASSED: {len(changed)} paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
