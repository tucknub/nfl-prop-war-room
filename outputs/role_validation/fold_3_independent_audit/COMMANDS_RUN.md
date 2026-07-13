# Independent Fold 3 audit command ledger

Working directory unless otherwise noted:

`C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection`

## Request and skill instructions

```powershell
Get-Content 'C:\Users\tucka\.codex\attachments\5600ab6e-503b-4d07-9811-d57d4a27c16c\pasted-text.txt'
Get-Content -Raw 'C:\Users\tucka\.codex\plugins\cache\openai-curated-remote\data-analytics\0.2.8-13ceeea1f599\skills\analyze-data-quality\SKILL.md'
Get-Content -Raw 'C:\Users\tucka\.codex\plugins\cache\openai-curated-remote\data-analytics\0.2.8-13ceeea1f599\skills\validate-data\SKILL.md'
Get-Content -Raw 'C:\Users\tucka\.codex\plugins\cache\openai-curated-remote\data-analytics\0.2.8-13ceeea1f599\skills\jupyter-notebooks\SKILL.md'
```

## Repository and checkpoint inspection

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git show --stat --oneline --decorate --no-renames a18c5cc3e8c9124be4781bececea0a93f7b4faf8
git tag --points-at c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9
git cat-file -e c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9:scripts/run_fold3_validation.py
git diff --name-only c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9 a18c5cc3e8c9124be4781bececea0a93f7b4faf8 -- dashboard config/role_change_fold2_candidate.yaml config/role_change_validation.yaml ROLE_CHANGE_VALIDATION_PROTOCOL.md LOCKED_DECISIONS.md
```

## Protocol, configuration, and implementation review

```powershell
Get-Content -Raw ROLE_CHANGE_VALIDATION_PROTOCOL.md
Get-Content -Raw LOCKED_DECISIONS.md
Get-Content -Raw config/role_change_validation.yaml
Get-Content -Raw config/role_change_fold2_candidate.yaml
rg -n "release|gate|min_holdout|min_persistence|min_absolute|max_immediate|min_reversion|min_median|min_alerts|direction" ROLE_CHANGE_VALIDATION_PROTOCOL.md LOCKED_DECISIONS.md config/role_change_validation.yaml config/role_change_fold2_candidate.yaml src/role_validation/evaluation.py src/role_validation/fold3.py
Get-Content src/role_validation/fold3.py | Select-Object -Skip 150 -First 130
Get-Content src/role_validation/evaluation.py | Select-Object -Skip 100 -First 220
Get-Content scripts/run_fold3_validation.py | Select-Object -First 260
Get-Content scripts/run_fold3_validation.py | Select-Object -Skip 260 -First 280
rg -n "equal_volume|EXPECTED_METHODS|method_eligible|top|deterministic|naive_spike|run_candidate" src/role_validation/redevelopment.py
Get-Content src/role_validation/redevelopment.py | Select-Object -Skip 480 -First 210
rg -n "2024|2025|allowed|seasons|timestamp|next_game|evidence_available|injury" src/role_validation/partial_game.py scripts/run_fold3_validation.py src/role_validation/redevelopment.py src/role_validation/evaluation.py
git show c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9:outputs/role_validation/fold_2/FOLD_2_REPORT.md | Select-String -Pattern 'direction-consistency check' -Context 0,3
git show c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9:outputs/role_validation/fold_2/release_gate_results_2022.csv | Select-Object -First 6
```

One read-only inspection attempted to pipe `git show ...:config/role_change_fold2_candidate.yaml` into `Get-FileHash`; PowerShell rejected pipeline input for `Get-FileHash`. No state changed, and the hashes were subsequently verified from repository files and Git objects.

## Hash and lineage verification

```powershell
Get-FileHash outputs/role_validation/canonical_player_week_role.csv.gz -Algorithm SHA256
Get-FileHash data/raw/role_validation/pbp_2017_2025.csv.gz -Algorithm SHA256
Get-FileHash data/raw/role_validation/participation_2017_2025.csv.gz -Algorithm SHA256
Get-FileHash data/raw/role_validation/injuries_2017_2025.csv.gz -Algorithm SHA256
Get-FileHash outputs/role_validation/fold_3/fold3_alerts_2023.csv.gz -Algorithm SHA256
Get-Content outputs/role_validation/fold_3/input_source_manifest.csv
Get-Content outputs/role_validation/fold_3/pre_run_manifest.json
Get-Content outputs/role_validation/fold_3/run_manifest.json
Get-Content outputs/role_validation/fold_3/frozen_config_fingerprint.json
Get-Content outputs/role_validation/fold_3/fold3_execution_lock.json
```

## Independent calculations

```powershell
python -m py_compile scripts/audit_fold3_independent.py
python scripts/audit_fold3_independent.py
```

The script was rerun after adding outcome-label reconstruction, full-alert rule compliance, partial-policy/repeat diagnostics, and 648-cell comparator-selection replay. It never invokes `run_candidate`, does not select full-detector alerts, and does not execute Fold 4.

Read-only Python inspection snippets loaded only the Fold 1 2021, Fold 2 2022, and Fold 3 2023 archives; printed source schemas and independently aggregated headline, pooled, direction, weekly, overlap, concentration, partial, denominator, opportunity, retention, and gate tables.

## Notebook

```powershell
python -m py_compile scripts/build_fold3_independent_audit_notebook.py
python scripts/build_fold3_independent_audit_notebook.py
python -m nbconvert --to notebook --execute --inplace notebooks/fold_3_independent_methodological_audit.ipynb --ExecutePreprocessor.timeout=300
```

Notebook execution was checked with `nbformat`: eight code cells executed and zero error outputs.

## Tests and independent validator

```powershell
python -m pytest -q tests/test_role_validation_redevelopment.py tests/test_role_validation_fold2.py tests/test_role_validation_fold3.py
python -m pytest -q
python -m py_compile scripts/validate_fold3_independent_audit.py
python scripts/validate_fold3_independent_audit.py
```

## Final scope and commit

```powershell
git add -- scripts/audit_fold3_independent.py scripts/build_fold3_independent_audit_notebook.py scripts/validate_fold3_independent_audit.py notebooks/fold_3_independent_methodological_audit.ipynb outputs/role_validation/fold_3_independent_audit
python scripts/validate_fold3_independent_audit.py
git diff --cached --name-only
git diff --cached --check
git commit -m "Audit Fold 3 validation independently"
git rev-parse HEAD
git status --short
```
