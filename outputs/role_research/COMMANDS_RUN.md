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

The final staging and commit commands are recorded by Git in the resulting commit; no merge, push, deployment, or public-dashboard release command was run during that original UI task.

## Completed 2025 descriptive-data release — 2026-07-14

The following commands were run from `C:\Users\tucka\OneDrive\Desktop\NFL PropWar Role Research UI` unless a different working directory is shown.

### Build and validate

```powershell
git fetch origin --prune --tags
python scripts\build_role_research_2025.py --source-cache-dir "C:\Users\tucka\.codex\cache\propwar_role_research_2025"
python scripts\build_role_research_data.py --pbp "C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection\data\raw\pbp.csv" --canonical outputs\role_validation\fold_1_diagnostics\canonical_role_2018_2021_enriched.csv.gz outputs\role_validation\fold_2\canonical_role_2022_enriched.csv.gz outputs\role_validation\fold_3\canonical_role_2023_enriched.csv.gz outputs\role_validation\fold_4\canonical_role_2024_enriched.csv.gz outputs\role_research\canonical_role_2025_descriptive.csv.gz --output-dir outputs\role_research
python scripts\validate_role_research_outputs.py
python -m pytest tests\test_role_research.py tests\test_public_role_research_language.py -q
python -m pytest -q
python -m compileall -q dashboard scripts tests
git diff --check
git diff --cached --check
```

The two build commands were rerun after the final code edits. Their output hashes exactly matched the earlier run.

### Local application QA

```powershell
python -m streamlit run dashboard/app.py --server.port 8512 --server.headless true --browser.gatherUsageStats false
python -m streamlit run dashboard/Home.py --server.port 8513 --server.headless true --browser.gatherUsageStats false
```

The in-app Browser opened both entrypoints and directly loaded `/`, `/teams`, `/players`, `/games`, `/reports`, `/explorer`, and `/admin-research`. It captured desktop and 390-by-844 screenshots, checked headings and 2025 copy, checked for Streamlit exceptions and horizontal overflow, changed the Teams and Games selectors, selected the Backfield Usage report, and enabled the Explorer two-minute filter.

### Commit and isolated production integration

```powershell
git add -- STREAMLIT_DEPLOY.md dashboard/Home.py dashboard/app.py dashboard/home_page.py dashboard/pages/01_Teams.py dashboard/pages/02_Players.py dashboard/pages/03_Games.py dashboard/pages/04_Reports.py dashboard/pages/05_Explorer.py dashboard/pages/90_Admin_Research.py dashboard/research_data.py dashboard/research_ui.py docs/ROLE_RESEARCH_UI_V1.md outputs/role_research/DATA_VALIDATION.md outputs/role_research/build_manifest.json outputs/role_research/game_player_usage.csv.gz outputs/role_research/opportunity_events.csv.gz outputs/role_research/situational_player_week.csv.gz outputs/role_research/validation_report.json outputs/role_research/canonical_audit_2025.json outputs/role_research/canonical_role_2025_descriptive.csv.gz outputs/role_research/join_coverage_2025.csv outputs/role_research/partial_game_source_coverage_2025.csv outputs/role_research/partial_game_status_2025.csv.gz outputs/role_research/source_coverage_2025.csv outputs/role_research/source_input_manifest_2025.csv scripts/build_role_research_2025.py scripts/build_role_research_data.py scripts/validate_role_research_outputs.py tests/test_public_role_research_language.py tests/test_role_research.py
git diff --cached --check
git commit -m "Add completed 2025 role research data"
git tag -a production-streamlit-cloud-pre-role-research-2025 9dd335fa1743deaf2a1c08d139c28c7cdbbe6c1e -m "Pre Role Research 2025 production checkpoint"
git worktree add -b propwar-role-research-production "C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration" origin/streamlit-cloud-deploy
```

From `C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration`:

```powershell
git merge --ff-only propwar-role-research-ui-v1
python -m pytest -q
```

That fresh-checkout test found that Git converted the frozen YAML candidate to CRLF, changing its byte fingerprint. No validation file, gate, candidate, or expected hash was edited. The checkout policy was corrected and verified with:

```powershell
python -m pytest tests\test_role_validation_fold2.py::test_frozen_config_matches_fold1_report_and_fingerprint tests\test_role_validation_fold3.py::test_fold3_config_is_byte_identical_to_fold2_frozen_copy tests\test_role_validation_fold4.py::test_fold4_config_is_byte_identical_to_prior_frozen_copies -q
git add .gitattributes
git diff --cached --check
git commit -m "Preserve frozen validation fingerprints across checkouts"
git merge --ff-only propwar-role-research-ui-v1
git worktree remove "C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration"
git worktree add "C:\Users\tucka\OneDrive\Desktop\NFL PropWar Production Integration" propwar-role-research-production
Get-FileHash config\role_change_fold2_candidate.yaml -Algorithm SHA256
python -m pytest -q
python scripts\validate_role_research_outputs.py
git diff --check
git diff --cached --check
```

The `git worktree remove` and matching `git worktree add` commands were run from the Role Research UI worktree after confirming the integration worktree was clean and resolving its exact absolute path.

### Push and live verification

```powershell
git push origin propwar-role-research-ui-v1
git push -u origin propwar-role-research-production
git push origin production-streamlit-cloud-pre-role-research-2025
git push origin propwar-role-research-production:streamlit-cloud-deploy
git fetch origin --prune --tags
git rev-parse origin/streamlit-cloud-deploy
git rev-parse origin/propwar-role-research-production
git rev-parse origin/propwar-role-research-ui-v1
git rev-list -n 1 production-streamlit-cloud-pre-role-research-2025
```

The in-app Browser then woke `https://propwar.streamlit.app/`, directly loaded every public route at desktop and 390-by-844 sizes, captured screenshots, checked the expected headings and 2025 content, checked for Streamlit exceptions, and performed a final hard reload of the home route.

### Release documentation finalization

```powershell
git add outputs/role_research/COMMANDS_RUN.md outputs/role_research/ROLE_RESEARCH_2025_RELEASE.md
git diff --cached --check
git commit -m "Document 2025 role research release"
git merge --ff-only propwar-role-research-ui-v1
git push origin propwar-role-research-ui-v1
git push origin propwar-role-research-production
git push origin propwar-role-research-production:streamlit-cloud-deploy
```
