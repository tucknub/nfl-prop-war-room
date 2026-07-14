from __future__ import annotations

import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = "8b759f18c34708300acf5e3ef84d0e4cbbbde597"
ALLOWED = [
    "docs/propwar/*",
    "outputs/propwar_correctness_audit/*",
    "notebooks/propwar_targeted_correctness_audit.ipynb",
    "scripts/run_targeted_correctness_audit.py",
    "scripts/build_targeted_correctness_notebook.py",
    "scripts/validate_targeted_correctness_outputs.py",
    "scripts/validate_targeted_correctness_scope.py",
    "tests/test_targeted_correctness_audit.py",
]
PROTECTED_HASH_FILES = [
    "LOCKED_DECISIONS.md",
    "ROLE_CHANGE_VALIDATION_PROTOCOL.md",
    "outputs/role_validation/release_gate_integrity.json",
    "outputs/role_validation/fold_2/frozen_role_change_fold2_candidate.yaml",
    "outputs/role_validation/fold_2/frozen_config_fingerprint.json",
    "outputs/role_validation/fold_2/release_gate_results_2022.csv",
    "outputs/role_validation/fold_3/frozen_config_fingerprint.json",
    "outputs/role_validation/fold_3/frozen_role_change_fold3_candidate.yaml",
    "outputs/role_validation/fold_4/frozen_role_change_fold4_candidate.yaml",
    "outputs/role_validation/fold_4/frozen_execution_package_manifest.json",
]


def changed_paths() -> list[str]:
    tracked = subprocess.check_output(
        ["git", "diff", "--name-only", BASE, "--"], cwd=ROOT, text=True
    ).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=ROOT, text=True
    ).splitlines()
    return sorted(set(path.replace("\\", "/") for path in tracked + untracked if path))


def main() -> int:
    changed = changed_paths()
    violations = [path for path in changed if not any(fnmatch.fnmatch(path, pattern) for pattern in ALLOWED)]
    protected_hashes = []
    for relative in PROTECTED_HASH_FILES:
        baseline_bytes = subprocess.check_output(["git", "show", f"{BASE}:{relative}"], cwd=ROOT)
        worktree_bytes = (ROOT / relative).read_bytes()
        # Git may materialize CRLF on Windows without a content change. Compare
        # canonical LF bytes while retaining SHA-256 evidence for both sides.
        baseline_canonical = baseline_bytes.replace(b"\r\n", b"\n")
        worktree_canonical = worktree_bytes.replace(b"\r\n", b"\n")
        baseline_hash = hashlib.sha256(baseline_canonical).hexdigest()
        worktree_hash = hashlib.sha256(worktree_canonical).hexdigest()
        protected_hashes.append(
            {
                "path": relative,
                "baseline_sha256": baseline_hash,
                "worktree_sha256": worktree_hash,
                "hash_basis": "canonical LF bytes",
                "match": baseline_hash == worktree_hash,
            }
        )
    hash_mismatches = [item["path"] for item in protected_hashes if not item["match"]]
    violations.extend(path for path in hash_mismatches if path not in violations)
    payload = {
        "baseline_commit": BASE,
        "changed_paths": changed,
        "allowed_patterns": ALLOWED,
        "violations": violations,
        "protected_hashes": protected_hashes,
        "protected_files_unchanged": not violations,
    }
    out = ROOT / "outputs" / "propwar_correctness_audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / "protected_file_validation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    final_path = out / "final_validation.json"
    if final_path.exists():
        final = json.loads(final_path.read_text(encoding="utf-8"))
        final["acceptance_gates"]["protected_files_unchanged"] = not violations
        final_path.write_text(json.dumps(final, indent=2) + "\n", encoding="utf-8")
    if violations:
        print("STAGED SCOPE VALIDATION FAILED")
        print("\n".join(f"- {path}" for path in violations))
        return 1
    print(f"STAGED SCOPE VALIDATION PASSED: {len(changed)} paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
