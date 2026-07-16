from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
BASE = "6c93e26100fb3c077cf2f9a936dea79ceb9ec254"
OUT = ROOT / "outputs" / "supporting_evidence_experience"
ALLOWED = [
    "dashboard/home_page.py", "dashboard/research_ui.py", "dashboard/supporting_evidence.py",
    "dashboard/pages/01_Teams.py", "dashboard/pages/02_Players.py", "dashboard/pages/03_Games.py",
    "dashboard/pages/04_Reports.py", "dashboard/pages/05_Explorer.py",
    "tests/test_supporting_evidence_experience.py", "scripts/run_supporting_evidence_audit.py",
    "scripts/run_supporting_evidence_browser_qa.py",
    "scripts/run_supporting_evidence_supplemental_audit.py",
    "scripts/validate_supporting_evidence_experience.py", "outputs/supporting_evidence_experience/*",
]
PROTECTED = [
    "docs/propwar/PROJECT_BLUEPRINT.md", "docs/propwar/LOCKED_DECISIONS.md",
    "LOCKED_DECISIONS.md", "ROLE_CHANGE_VALIDATION_PROTOCOL.md",
    "dashboard/research_data.py", "dashboard/weekly_report.py",
    "outputs/role_validation/release_gate_integrity.json",
    "outputs/role_validation/fold_2/frozen_role_change_fold2_candidate.yaml",
    "outputs/role_validation/fold_2/frozen_config_fingerprint.json",
    "outputs/role_validation/fold_3/frozen_role_change_fold3_candidate.yaml",
    "outputs/role_validation/fold_4/frozen_role_change_fold4_candidate.yaml",
    "outputs/role_validation/fold_4/frozen_execution_package_manifest.json",
]
PRESERVED = [
    "outputs/propwar_correctness_audit", "outputs/weekly_role_report",
    "outputs/weekly_role_report_calibration", "outputs/control_state_searchability",
    "outputs/role_validation",
]
REQUIRED = [
    "DESIGN_DECISIONS.md", "DATA_AVAILABILITY.md", "HOME_WORDING_AUDIT.csv",
    "TEAM_PAGE_VALIDATION.csv", "PLAYER_PAGE_VALIDATION.csv", "GAME_PAGE_VALIDATION.csv",
    "REPORT_PAGE_VALIDATION.csv", "EXPLORER_PRESET_VALIDATION.csv",
    "EVIDENCE_PATH_WALKTHROUGHS.md", "mobile_qa.md", "desktop_qa.md",
    "final_validation.json", "COMMANDS_RUN.md",
]
SUPPLEMENTAL_REQUIRED = [
    "GAP_MATRIX.md", "THIRTY_SECOND_USABILITY_AUDIT.csv", "DATA_STATUS_AUDIT.md",
    "mobile_qa.md", "desktop_qa.md", "final_validation.json", "COMMANDS_RUN.md",
]
SCREENSHOTS = [
    "mobile_home_to_team.png", "mobile_home_to_player.png", "mobile_home_to_game.png",
    "mobile_team_hierarchy.png", "mobile_player_summary.png", "mobile_player_chart.png",
    "mobile_game_summary.png", "mobile_reports.png", "mobile_explorer_presets.png",
    "desktop_home.png", "desktop_teams.png", "desktop_players.png", "desktop_games.png",
    "desktop_reports.png", "desktop_explorer.png",
]


def git_bytes(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def digest(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def changed_paths(staged: bool) -> list[str]:
    if staged:
        return git_bytes("diff", "--cached", "--name-only", BASE).decode().splitlines()
    tracked = git_bytes("diff", "--name-only", BASE).decode().splitlines()
    untracked = git_bytes("ls-files", "--others", "--exclude-standard").decode().splitlines()
    return sorted(set(tracked + untracked))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true")
    args = parser.parse_args()
    failures: list[str] = []
    failures.extend(f"missing artifact: {name}" for name in REQUIRED if not (OUT / name).exists())
    supplemental = OUT / "supplemental_gap_audit"
    failures.extend(
        f"missing supplemental artifact: {name}"
        for name in SUPPLEMENTAL_REQUIRED
        if not (supplemental / name).exists()
    )
    failures.extend(f"missing screenshot: {name}" for name in SCREENSHOTS if not (OUT / "screenshots" / name).exists())
    for name in ["HOME_WORDING_AUDIT.csv", "TEAM_PAGE_VALIDATION.csv", "PLAYER_PAGE_VALIDATION.csv", "GAME_PAGE_VALIDATION.csv", "REPORT_PAGE_VALIDATION.csv", "EXPLORER_PRESET_VALIDATION.csv"]:
        path = OUT / name
        if path.exists():
            frame = pd.read_csv(path)
            if "pass" in frame and not frame["pass"].astype(bool).all(): failures.append(f"failed validation row: {name}")
    home_path = OUT / "HOME_WORDING_AUDIT.csv"
    if home_path.exists():
        home = pd.read_csv(home_path)
        if len(home) != 79: failures.append(f"weekly replay count is {len(home)}, expected 79")
        if not home["selection_unchanged"].astype(bool).all(): failures.append("Home candidate selection changed")
        if not home["category_unchanged"].astype(bool).all(): failures.append("Home category assignment changed")

    changed = changed_paths(args.staged)
    unexpected = [path for path in changed if path and not any(fnmatch.fnmatch(path, pattern) for pattern in ALLOWED)]
    failures.extend(f"out-of-scope changed path: {path}" for path in unexpected)
    protected = []
    for relative in PROTECTED:
        baseline = git_bytes("show", f"{BASE}:{relative}")
        current = (ROOT / relative).read_bytes()
        before, after = digest(baseline), digest(current)
        protected.append({"path": relative, "baseline_sha256": before, "current_sha256": after, "unchanged": before == after})
        if before != after: failures.append(f"protected file changed: {relative}")
    preserved = []
    for relative in PRESERVED:
        changes = git_bytes("diff", "--name-only", BASE, "--", relative).decode().splitlines()
        preserved.append({"path": relative, "changed_files": changes, "unchanged": not changes})
        if changes: failures.append(f"preserved output changed: {relative}")
    payload = {
        "status": "PASS" if not failures else "FAIL", "baseline_commit": BASE,
        "mode": "staged" if args.staged else "worktree", "changed_files": changed,
        "unexpected_files": unexpected, "protected_files": protected,
        "preserved_output_directories": preserved, "failures": failures,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scope_validation.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
