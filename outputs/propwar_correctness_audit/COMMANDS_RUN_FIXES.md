# Commands Run — Phase A Correctness Fixes

Working directory:

`C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration`

## Branch and safety

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse origin/streamlit-cloud-deploy
git switch -c propwar-correctness-fixes-v1 e939b886c9b75d6a06eaf9bf95dc8ec1a1e093ad
git diff --name-only e939b886c9b75d6a06eaf9bf95dc8ec1a1e093ad
```

## Corrected audit and focused tests

```powershell
python -m py_compile dashboard/research_data.py dashboard/research_ui.py dashboard/pages/01_Teams.py dashboard/pages/02_Players.py dashboard/pages/04_Reports.py scripts/run_targeted_correctness_audit.py scripts/run_targeted_correctness_fix_validation.py scripts/validate_targeted_correctness_after_fix.py scripts/validate_targeted_correctness_fix_scope.py
python scripts/run_targeted_correctness_fix_validation.py
python -m pytest tests/test_targeted_correctness_audit.py tests/test_targeted_correctness_fixes.py -q
python -m pytest tests/test_role_research.py::test_team_window_uses_full_team_denominator tests/test_targeted_correctness_audit.py tests/test_targeted_correctness_fixes.py -q
```

The first full-suite run exposed the missing legacy `normal_game` output and
returned `1 failed, 65 passed`. After restoring that output with the corrected
denominator spine, the focused rerun returned `21 passed` and the final full
suite returned `66 passed`.

## Full validation

```powershell
python -m pytest -q
python -m compileall -q dashboard scripts tests
python scripts/validate_targeted_correctness_after_fix.py
python scripts/validate_targeted_correctness_outputs.py --section descriptive
python scripts/validate_targeted_correctness_outputs.py --section cross-page
python scripts/validate_targeted_correctness_outputs.py --section link-state
python scripts/validate_targeted_correctness_outputs.py --section explorer
python scripts/validate_targeted_correctness_outputs.py --section language
python scripts/validate_targeted_correctness_fix_scope.py
git diff --check
git diff --cached --check
```

## Local application and browser QA

```powershell
python -m streamlit run dashboard/app.py --server.headless true --server.address 127.0.0.1 --server.port 8511
```

Affected routes are inspected with the Codex in-app browser at desktop and
390×844 using `http://127.0.0.1:8511/` and the existing `/teams`, `/players`,
`/reports`, and `/explorer` routes. Browser checks include valid/invalid direct
URLs, Home Week 18 rows, Report context switching, Explorer Reset, framework
overlays, console health, and screenshots.

Local evidence is recorded in
`outputs/propwar_correctness_audit/browser_state_evidence_after_fix.json`.

## Commit preparation

```powershell
git add dashboard/research_data.py dashboard/research_ui.py dashboard/pages/01_Teams.py dashboard/pages/02_Players.py dashboard/pages/04_Reports.py docs/propwar/CURRENT_PHASE.md scripts/run_targeted_correctness_audit.py scripts/run_targeted_correctness_fix_validation.py scripts/validate_targeted_correctness_outputs.py scripts/validate_targeted_correctness_after_fix.py scripts/validate_targeted_correctness_fix_scope.py tests/test_targeted_correctness_audit.py tests/test_targeted_correctness_fixes.py outputs/propwar_correctness_audit/FIX_VALIDATION_REPORT.md outputs/propwar_correctness_audit/browser_state_evidence_after_fix.json outputs/propwar_correctness_audit/calculation_discrepancies_after_fix.csv outputs/propwar_correctness_audit/cross_page_reconciliation_after_fix.csv outputs/propwar_correctness_audit/link_state_validation_after_fix.csv outputs/propwar_correctness_audit/explorer_validation_after_fix.csv outputs/propwar_correctness_audit/final_validation_after_fix.json outputs/propwar_correctness_audit/protected_file_validation_after_fix.json outputs/propwar_correctness_audit/COMMANDS_RUN_FIXES.md
git diff --cached --check
git commit -m "fix PropWar public correctness defects"
```

No merge, production push, or deployment command was run.
