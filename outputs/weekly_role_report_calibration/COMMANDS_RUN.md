# Phase B2A Command Ledger

All commands ran from `C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration` on branch `propwar-weekly-role-report-calibration-v1` unless noted.

## Branch and baseline

```powershell
git status --short --branch
git rev-parse HEAD
git branch --show-current
git switch -c propwar-weekly-role-report-calibration-v1 cec6244e0987ebfdc2e9c0138f0a707aec867887
git diff --stat
```

The branch began at `cec6244e0987ebfdc2e9c0138f0a707aec867887`. Production was not checked out, merged, pushed, or deployed.

## Tests and compilation

```powershell
python -m pytest tests/test_weekly_role_report.py -q
python -m pytest -q
python -m compileall -q dashboard scripts tests
python -m pytest tests/test_public_role_research_language.py -q
python -m pytest tests/test_weekly_role_report.py -k "future or leakage or link or selected_week or same_season" -q
python -m pytest tests/test_targeted_correctness_fixes.py -k "link or state" -q
python -m pytest tests/test_targeted_correctness_fixes.py -q
```

Final successful results:

- Focused calibration: 25 passed.
- Complete repository: 91 passed.
- Public-language guardrail: 5 passed.
- Weekly leakage/link subset: 5 passed, 20 deselected.
- Correctness-fix regressions: 7 passed.
- Python compilation: passed.

The targeted-correctness `-k "link or state"` probe selected no tests and returned pytest exit code 1 with 7 deselected; the complete seven-test file was then run and passed. This was a selection-expression issue, not a product failure.

## Replay and independent validation

```powershell
python scripts/run_weekly_role_report_calibration.py
python scripts/run_targeted_correctness_fix_validation.py
git status --short outputs/propwar_correctness_audit
git diff --exit-code -- outputs/propwar_correctness_audit
git restore --source=HEAD -- outputs/propwar_correctness_audit/final_validation_after_fix.json
git diff --exit-code -- outputs/propwar_correctness_audit
python scripts/validate_targeted_correctness_after_fix.py
python scripts/validate_targeted_correctness_outputs.py --section all
python scripts/validate_targeted_correctness_outputs.py --section link-state
python scripts/validate_targeted_correctness_outputs.py --section language
python scripts/validate_weekly_role_report_calibration_scope.py
python scripts/validate_weekly_role_report_calibration.py
```

The corrected audit passed. Its legacy runner refreshed only `final_validation_after_fix.json`; that generated rewrite was restored immediately, then `git diff --exit-code` proved the entire prior correctness-audit output directory unchanged. The independent after-fix, all-output, link/state, language, calibration, and protected-scope validators passed.

## Local runtime and exact-viewport QA

```powershell
python -m streamlit run dashboard/app.py --server.headless=true --server.port=8510 --browser.gatherUsageStats=false
Start-Process python -ArgumentList @('-m','streamlit','run','dashboard/app.py','--server.headless=true','--server.port=8512','--browser.gatherUsageStats=false') -WorkingDirectory 'C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration' -WindowStyle Hidden -PassThru
```

The connected Codex Browser exercised Home and all public supporting routes. Supplemental Python Playwright runs used Chromium at exact 390×844 and 1440×900 viewports, measured `window.innerWidth` and `document.documentElement.scrollWidth`, checked every `.pw-report-card` bounding box, captured the committed screenshots, expanded evidence, and checked console errors.

Two QA probes failed before the final successful run: the first searched for shorter notice text than the rendered strings, and the second searched for a Streamlit expander label while the component is an HTML `summary`. Both probes still reported zero overflow; selectors were corrected and the full final QA passed against a freshly started runtime on port 8512.

## Final Git validation

```powershell
git diff --check
git add dashboard/home_page.py dashboard/pages/02_Players.py dashboard/research_data.py dashboard/research_ui.py dashboard/weekly_report.py docs/propwar/CURRENT_PHASE.md outputs/weekly_role_report_calibration scripts/run_weekly_role_report_calibration.py scripts/validate_weekly_role_report_calibration.py scripts/validate_weekly_role_report_calibration_scope.py tests/test_weekly_role_report.py
python scripts/validate_weekly_role_report_calibration_scope.py --staged --no-write
git diff --cached --check
git diff --cached --name-status
git commit -m "Calibrate weekly role report allocation"
```

These final commands were run in this order. No merge, production push, or deployment command was run.
