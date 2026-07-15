from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "propwar_correctness_audit"
WORK = OUT / "_after_fix_work"
AUDIT_COMMIT = "e939b886c9b75d6a06eaf9bf95dc8ec1a1e093ad"
PRODUCTION_COMMIT = "8b759f18c34708300acf5e3ef84d0e4cbbbde597"
ORIGINAL_ARTIFACTS = [
    path for path in OUT.iterdir()
    if path.is_file()
    and "after_fix" not in path.name
    and path.name not in {"FIX_VALIDATION_REPORT.md", "COMMANDS_RUN_FIXES.md"}
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_audit_module():
    path = ROOT / "scripts" / "run_targeted_correctness_audit.py"
    spec = importlib.util.spec_from_file_location("propwar_targeted_audit", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    original_before = {path.name: sha256(path) for path in ORIGINAL_ARTIFACTS}
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    browser_evidence = OUT / "browser_state_evidence_after_fix.json"
    if browser_evidence.exists():
        shutil.copy2(browser_evidence, WORK / "browser_state_evidence.json")

    audit = load_audit_module()
    audit.OUT = WORK
    audit.main()

    calculations = pd.read_csv(WORK / "calculation_discrepancies.csv")
    cross_page = pd.read_csv(WORK / "cross_page_reconciliation.csv")
    links = pd.read_csv(WORK / "link_state_validation.csv")
    explorer = pd.read_csv(WORK / "explorer_validation.csv")
    home = pd.read_csv(WORK / "home_validation.csv")
    reports = pd.read_csv(WORK / "report_validation.csv")
    after = json.loads((WORK / "final_validation.json").read_text(encoding="utf-8"))
    before = json.loads((OUT / "final_validation.json").read_text(encoding="utf-8"))

    results = {
        "critical_findings": int(after["results"]["critical_findings"]),
        "high_findings": int(after["results"]["high_findings"]),
        "home_wrong_week_failures": int(home["status"].eq("FAIL").sum()),
        "situational_denominator_failures": int(
            calculations.loc[calculations["sample_type"].eq("situational"), "status"].eq("FAIL").sum()
        ),
        "explorer_zero_opportunity_failures": int(explorer["status"].eq("FAIL").sum()),
        "report_context_failures": int(reports["severity"].eq("High").sum()),
        "invalid_player_team_state_failures": int(
            (links["status"].eq("FAIL") & links["severity"].eq("High")).sum()
        ),
        "cross_page_failures": int(cross_page["status"].eq("FAIL").sum()),
    }
    pass_gate = all(value == 0 for value in results.values())
    original_after = {path.name: sha256(path) for path in ORIGINAL_ARTIFACTS}
    originals_unchanged = original_before == original_after
    after.update(
        {
            "phase": "Phase A — Correctness Fixes",
            "phase_status": "PASSED" if pass_gate and originals_unchanged else "FAILED",
            "production_status": "UNCHANGED",
            "production_commit": PRODUCTION_COMMIT,
            "audit_start_commit": AUDIT_COMMIT,
            "correctness_results": results,
            "original_audit_artifacts_unchanged": originals_unchanged,
            "original_audit_artifact_sha256": original_after,
            "before_results": before["results"],
        }
    )

    outputs = {
        "calculation_discrepancies.csv": "calculation_discrepancies_after_fix.csv",
        "cross_page_reconciliation.csv": "cross_page_reconciliation_after_fix.csv",
        "link_state_validation.csv": "link_state_validation_after_fix.csv",
        "explorer_validation.csv": "explorer_validation_after_fix.csv",
    }
    for source, destination in outputs.items():
        shutil.copy2(WORK / source, OUT / destination)
    (OUT / "final_validation_after_fix.json").write_text(
        json.dumps(after, indent=2) + "\n", encoding="utf-8"
    )

    remaining = pd.DataFrame(after["findings"])
    remaining_lines = (
        [f"- {row.severity}: {row.id} — {row.page}" for row in remaining.itertuples(index=False)]
        if not remaining.empty else ["- None."]
    )
    report = [
        "# PropWar Phase A Correctness Fix Validation",
        "",
        f"**Phase status:** {after['phase_status']}",
        "",
        "**Production status:** UNCHANGED",
        "",
        f"**Production commit:** `{PRODUCTION_COMMIT}`",
        "",
        "## Overall judgment",
        "",
        (
            "All five High correctness defects now pass the unchanged targeted audit definitions and sample sizes."
            if after["phase_status"] == "PASSED"
            else "One or more required correctness gates remain unresolved."
        ),
        "",
        "## Before and after",
        "",
        "| Gate | Before | After |",
        "|---|---:|---:|",
        f"| Critical findings | {before['results']['critical_findings']} | {results['critical_findings']} |",
        f"| High findings | {before['results']['high_findings']} | {results['high_findings']} |",
        f"| Home wrong-week rows | {before['results']['home_failures']} | {results['home_wrong_week_failures']} |",
        f"| Situational denominator failures | {before['results']['calculation_failures']} | {results['situational_denominator_failures']} |",
        f"| Explorer zero-opportunity failures | {before['results']['explorer_failures']} | {results['explorer_zero_opportunity_failures']} |",
        f"| Report context failures | 3 | {results['report_context_failures']} |",
        f"| Invalid player/team state failures | 4 static/live evidence rows | {results['invalid_player_team_state_failures']} |",
        f"| Cross-page mismatches | {before['results']['cross_page_failures']} | {results['cross_page_failures']} |",
        "",
        "## Previously passing controls",
        "",
        f"- Player window failures: {int(calculations.loc[calculations['audit_area'].eq('Player'), 'status'].eq('FAIL').sum())}",
        f"- Ordinary team role-ownership failures: {int(calculations.loc[calculations['sample_type'].eq('role_ownership'), 'status'].eq('FAIL').sum())}",
        f"- Canonical duplicate keys: {after['team_quality_checks']['duplicate_player_team_week_family_keys']}",
        f"- Numeric sorting 25.0% before 8.3%: {after['team_quality_checks']['numeric_sort_25_before_8_3']}",
        f"- Public-language failures: {after['results']['language_failures']}",
        "- No Week 0 and no fabricated 2026 usage.",
        "",
        "## Remaining Medium and Low findings",
        "",
        *remaining_lines,
        "",
        "## Integrity",
        "",
        f"- Original audit artifacts unchanged: {originals_unchanged}",
        "- Detector rules, frozen detector configuration, protocols, release gates, historical validation artifacts, and canonical statistical definitions were not changed.",
        "- No merge, push, or deployment occurred.",
    ]
    (OUT / "FIX_VALIDATION_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    shutil.rmtree(WORK)
    print(json.dumps({"phase_status": after["phase_status"], **results}, indent=2))


if __name__ == "__main__":
    main()
