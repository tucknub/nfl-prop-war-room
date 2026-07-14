# PropWar role research UI command ledger

Working directory unless noted: `C:\Users\tucka\OneDrive\Desktop\NFL PropWar Role Research UI`

## Repository isolation and branch

```powershell
git -C "C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection" status --short --branch
git -C "C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection" worktree add -b propwar-role-research-ui-v1 "C:\Users\tucka\OneDrive\Desktop\NFL PropWar Role Research UI" f3e4a9d5349215af1ee1b1204511dcc377dc7e2e
git status --short --branch
git log -1 --format="%H %s"
```

## Data build and validation

```powershell
python scripts/build_role_research_data.py
python scripts/build_role_research_data.py
python scripts/validate_role_research_outputs.py
python -m pytest -q tests/test_role_research.py tests/test_public_role_research_language.py
python -m pytest -q
python -m compileall dashboard scripts tests
rg -n -i "validated detector|betting recommendation|betting recommendations|odds|edge score|propwar score|should bet|actionable betting" dashboard/Home.py dashboard/pages/01_Teams.py dashboard/pages/02_Players.py dashboard/pages/03_Games.py dashboard/pages/04_Reports.py dashboard/pages/05_Explorer.py
```

The build was run twice to verify deterministic artifact hashes. The validator compares the checked-in artifacts with `build_manifest.json`, reconciles all-play and normal-game opportunities, and enforces the public-language boundary.

## Local UI execution and browser QA

```powershell
python -m streamlit run dashboard/app.py --server.headless true --server.port 8511 --browser.gatherUsageStats false
```

The in-app Browser was used against `http://127.0.0.1:8511` to inspect all six public routes and the separated admin route at desktop and 390-by-844 mobile sizes. It also exercised the Teams game-script tab, Reports comparison control, and Explorer two-minute filter. Console logs were checked in a fresh tab after the final server restart.

## Final repository checks

```powershell
git diff --check
git status --short --branch
python -m pytest -q
python scripts/validate_role_research_outputs.py
git diff --cached --check
```

The final staging and commit commands are recorded by Git in the resulting commit; no merge, push, deployment, or public-dashboard release command was run.
