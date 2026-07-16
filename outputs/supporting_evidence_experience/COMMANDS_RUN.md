# Phase B3 Command Ledger

All commands ran from `C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration` unless stated otherwise.

## Baseline and branch

```powershell
git status --short --branch
git rev-parse HEAD
git rev-parse streamlit-cloud-deploy
git switch -c propwar-supporting-evidence-experience-v1 6c93e26100fb3c077cf2f9a936dea79ceb9ec254
git branch --show-current
```

All files under `docs/propwar/` were read before implementation. The branch began clean at the exact requested production commit.

## Source and schema inspection

```powershell
rg --files dashboard tests scripts
Get-Content dashboard/research_data.py -TotalCount 130
python -
rg -n "final_score|home_score|away_score|total_home_score|score_home|score_away|longest|longest_play|yards_gained" outputs dashboard scripts tests --glob '!outputs/role_validation/**' --glob '!outputs/propwar_correctness_audit/**'
```

The inline Python schema probe read the committed `game_player_usage.csv.gz`, `opportunity_events.csv.gz`, `situational_player_week.csv.gz`, and `canonical_role_2025_descriptive.csv.gz` column sets and samples.

## Focused calculations and tests

```powershell
python -m compileall -q dashboard
python -m pytest -q tests/test_supporting_evidence_experience.py
python -m pytest -q tests/test_supporting_evidence_experience.py tests/test_control_state_searchability.py tests/test_weekly_role_report.py
python -m pytest -q tests/test_targeted_correctness_audit.py::test_explorer_reset_defaults_are_complete tests/test_targeted_correctness_audit.py::test_invalid_state_handling_is_explicit tests/test_supporting_evidence_experience.py
python -m pytest -q tests/test_supporting_evidence_experience.py tests/test_public_role_research_language.py tests/test_control_state_searchability.py tests/test_weekly_role_report.py tests/test_targeted_correctness_fixes.py
python -m compileall -q dashboard scripts tests
python -m pytest -q
python -m pytest -q tests/test_weekly_role_report.py -k "future or leakage or link or selected_week or same_season"
python -m pytest -q tests/test_targeted_correctness_fixes.py
```

One early combined pytest command had a 120-second harness timeout before producing results. The first complete repository run reported two legacy compatibility failures; explicit invalid-state messages and the literal Reset-default dictionary were restored. The final focused group reported 61 passed and the final complete suite reported 115 passed.

## Replay, audit, and validators

```powershell
python scripts/run_supporting_evidence_audit.py
python scripts/run_weekly_role_report_calibration.py
python scripts/validate_targeted_correctness_after_fix.py
python scripts/validate_targeted_correctness_outputs.py --section all
python scripts/validate_targeted_correctness_outputs.py --section link-state
python scripts/validate_targeted_correctness_outputs.py --section explorer
python scripts/validate_targeted_correctness_outputs.py --section language
git diff --name-only 6c93e26100fb3c077cf2f9a936dea79ceb9ec254 -- outputs/weekly_role_report outputs/weekly_role_report_calibration outputs/propwar_correctness_audit outputs/control_state_searchability outputs/role_validation
```

The legacy replay runner refreshed `outputs/weekly_role_report_calibration/final_validation.json`; its unchanged validated content was restored with `apply_patch`, and `git hash-object` matched the baseline object exactly. No preserved audit directory has a content diff.

## Browser QA

```powershell
python -m streamlit run dashboard/Home.py --server.port 8514 --server.headless true --browser.gatherUsageStats false
python scripts/run_supporting_evidence_browser_qa.py
```

The connected Codex Browser first exercised Home → Team, Home → Player, Home → Game, Reports, and Explorer preset behavior. The exact-viewport Playwright command was repeated while its local proxy waits and desktop accessibility assertions were made deterministic. The final run passed 390×844 and 1440×900 with zero overflow, workflow failures, console errors, or page errors. A final one-route screenshot probe refreshed `desktop_teams.png` after the data grid finished painting.

## Final Git validation and commit

```powershell
python scripts/validate_supporting_evidence_experience.py
git diff --check
git add dashboard/home_page.py dashboard/research_ui.py dashboard/supporting_evidence.py dashboard/pages/01_Teams.py dashboard/pages/02_Players.py dashboard/pages/03_Games.py dashboard/pages/04_Reports.py dashboard/pages/05_Explorer.py tests/test_supporting_evidence_experience.py scripts/run_supporting_evidence_audit.py scripts/run_supporting_evidence_browser_qa.py scripts/validate_supporting_evidence_experience.py outputs/supporting_evidence_experience
git diff --cached --check
python scripts/validate_supporting_evidence_experience.py --staged
git commit -m "Build supporting evidence experience"
git rev-parse HEAD
git status --short --branch
```

No merge, push, production-branch checkout, or deployment command was run.
