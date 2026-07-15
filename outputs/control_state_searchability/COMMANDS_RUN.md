# Commands Run

Working directory for every command unless noted: `C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration`.

## Branch and inspection

```powershell
git status --short --branch
git switch -c propwar-control-state-searchability-v1 5083db142f09dbb02404e250c7a7fb1ff50f75fe
git branch --show-current
git rev-parse 5083db142f09dbb02404e250c7a7fb1ff50f75fe
Get-Content docs/propwar/PROJECT_BLUEPRINT.md
Get-Content docs/propwar/CURRENT_PHASE.md
Get-Content docs/propwar/LOCKED_DECISIONS.md
Get-Content docs/propwar/PHASE_GATES.md
Get-Content docs/propwar/PRODUCT_BACKLOG.md
Get-Content docs/propwar/RELEASE_HISTORY.md
Get-Content docs/propwar/ROLLBACK_PLAN.md
```

## Local runtime and browser QA

```powershell
python -m streamlit run dashboard/app.py --server.headless=true --server.port=8514 --browser.gatherUsageStats=false
Invoke-WebRequest -UseBasicParsing http://localhost:8514/_stcore/health
python scripts/run_control_state_browser_qa.py --base-url http://localhost:8514 --live-url https://propwar.streamlit.app
python scripts/run_control_state_browser_qa.py --base-url http://localhost:8514 --live-url https://propwar.streamlit.app
python scripts/run_control_state_browser_qa.py --base-url http://localhost:8514 --live-url https://propwar.streamlit.app
python scripts/run_control_state_browser_qa.py --base-url http://localhost:8514 --live-url https://propwar.streamlit.app
python scripts/run_control_state_searchability_audit.py
```

The first browser-QA pass exposed an assertion that sampled the summary before Streamlit completed its render. The second proved that one Back step can remain on an intermediate PHI history entry after a second filter change. The final run waits for the rendered summary and verifies DAL/PHI only when the corresponding URL is active; both required viewports passed. Additional inline Playwright probes isolated hard-refresh timing and the raw local Streamlit subpage resource-path behavior. The committed runner contains the final reproducible checks and route-normalizing local harness.

The in-app browser was also used to reproduce the deployed DAL reversion, inspect all local public routes, exercise search/typeahead, and verify Back/Forward behavior. Exact viewport screenshots were captured by the committed Playwright runner because the in-app Browser screenshot command was unavailable.

## Tests and validators

```powershell
python -m pytest tests/test_control_state_searchability.py -q
python -m compileall -q dashboard scripts tests
git diff --check
python -m pytest -q
python scripts/run_weekly_role_report_calibration.py
python scripts/validate_weekly_role_report_calibration.py
git diff --name-only 5083db142f09dbb02404e250c7a7fb1ff50f75fe -- outputs/weekly_role_report_calibration outputs/weekly_role_report
python scripts/run_targeted_correctness_fix_validation.py
python scripts/validate_targeted_correctness_after_fix.py
python scripts/validate_targeted_correctness_outputs.py --section all
python scripts/validate_targeted_correctness_outputs.py --section link-state
python scripts/validate_targeted_correctness_outputs.py --section explorer
python scripts/validate_targeted_correctness_outputs.py --section language
git diff --name-only 5083db142f09dbb02404e250c7a7fb1ff50f75fe -- outputs/propwar_correctness_audit
python scripts/validate_control_state_searchability.py
git diff --check
git diff --cached --check
python scripts/validate_control_state_searchability.py --staged
```

## Final Git operations

```powershell
git status --short --branch
git diff --stat
git add dashboard/control_state.py dashboard/home_page.py dashboard/research_ui.py dashboard/pages/01_Teams.py dashboard/pages/02_Players.py dashboard/pages/03_Games.py dashboard/pages/04_Reports.py dashboard/pages/05_Explorer.py scripts/run_control_state_browser_qa.py scripts/run_control_state_searchability_audit.py scripts/validate_control_state_searchability.py tests/test_control_state_searchability.py outputs/control_state_searchability
git diff --cached --check
python scripts/validate_control_state_searchability.py --staged
git commit -m "Fix public control state and searchability"
git rev-parse HEAD
git status --short --branch
```

No merge, push, production-branch checkout, or deployment command was run.
