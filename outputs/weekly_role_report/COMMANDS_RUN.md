# Commands Run

Working directory for repository commands:

`C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration`

## Git and repository inspection

```powershell
git status --short --branch
git branch --show-current
git rev-parse HEAD
git switch -c propwar-weekly-role-report-v1 009703cfaead7beaaef6ddf53202557b87bde744
rg --files tests scripts
rg "observable_changes|Opportunity Versus Production|query_params|yards_per|normal|partial|game_id|player_href|team" dashboard
git diff -- outputs/propwar_correctness_audit/final_validation_after_fix.json
git diff --exit-code -- outputs/propwar_correctness_audit/final_validation_after_fix.json
```

## Read-only data probes

```powershell
python -
```

The inline probes imported `primary_rows`, `load_production_data`, `load_situational_data`, `load_opportunity_events`, and `observable_changes`; printed schemas and selected 2025 rows; and evaluated fixed Weeks 2, 5, 8, 11, 14, and 18. A second inline probe independently calculated prior count-weighted baselines, all-play versus normal-game gaps, and yards per opportunity for threshold review. Neither probe wrote repository files.

## Replay and automated validation

```powershell
python scripts/run_weekly_role_report_replay.py
python -m pytest tests/test_weekly_role_report.py tests/test_public_role_research_language.py -q
python -m pytest -q
python -m compileall -q dashboard scripts tests
python scripts/run_targeted_correctness_fix_validation.py --help
python scripts/validate_targeted_correctness_after_fix.py
python scripts/validate_targeted_correctness_outputs.py
python scripts/validate_weekly_role_report.py
python scripts/validate_weekly_role_report_scope.py
python scripts/validate_weekly_role_report_scope.py --staged
git diff --check
git diff --cached --check
```

`run_targeted_correctness_fix_validation.py` does not implement a help-only path, so the `--help` probe executed the corrected audit. The run completed successfully. Its one regenerated manifest difference was restored with `apply_patch`, and `git diff --exit-code` verified that every existing correctness-audit artifact remained byte-equivalent to the branch checkpoint.

## Local Streamlit QA

```powershell
Start-Process -FilePath python -ArgumentList @('-m','streamlit','run','dashboard/app.py','--server.port','8511','--server.headless','true','--browser.gatherUsageStats','false') -WorkingDirectory 'C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration' -WindowStyle Hidden -RedirectStandardOutput "$env:TEMP\propwar-weekly-streamlit.out.log" -RedirectStandardError "$env:TEMP\propwar-weekly-streamlit.err.log"
Get-NetTCPConnection -LocalPort 8511 -State Listen
Stop-Process -Id 3040
```

The in-app browser then opened `http://localhost:8511/`, set explicit 390×844 and 1440×900 viewport overrides, inspected DOM measurements, expanded a card, operated Player/Team/Game evidence links, checked the Week 1 empty state, captured the required screenshots, read browser console errors, reset the viewport override, and finalized the QA tab.

## Final Git operations

```powershell
git status --short
git diff --stat
git diff --check
git add dashboard/home_page.py dashboard/research_ui.py dashboard/weekly_report.py dashboard/pages/01_Teams.py dashboard/pages/02_Players.py dashboard/pages/03_Games.py docs/propwar/CURRENT_PHASE.md outputs/weekly_role_report scripts/run_weekly_role_report_replay.py scripts/validate_weekly_role_report.py scripts/validate_weekly_role_report_scope.py tests/test_public_role_research_language.py tests/test_weekly_role_report.py
git diff --cached --check
git commit -m "Build weekly NFL role report"
git rev-parse HEAD
```
