# Fold 4 exact command ledger

Working directory unless noted:

`C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection`

## Requested skill instructions

```powershell
Get-Content -Raw -LiteralPath 'C:\Users\tucka\.codex\plugins\cache\openai-curated-remote\data-analytics\0.2.8-13ceeea1f599\skills\analyze-data-quality\SKILL.md'
Get-Content -Raw -LiteralPath 'C:\Users\tucka\.codex\plugins\cache\openai-curated-remote\data-analytics\0.2.8-13ceeea1f599\skills\jupyter-notebooks\SKILL.md'
Get-Content -Raw -LiteralPath 'C:\Users\tucka\.codex\plugins\cache\openai-curated-remote\data-analytics\0.2.8-13ceeea1f599\skills\validate-data\SKILL.md'
```

## Checkpoint and repository inspection

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git tag --list '*fold*4*'
git tag -a pre-fold-4-checkpoint 603bd5159833e1ce11ca4ff261b0d88fd040ea73 -m "Pre-Fold-4 checkpoint: frozen candidate before 2024 evaluation"
git rev-list -n 1 pre-fold-4-checkpoint
rg --files scripts src/role_validation tests config outputs/role_validation
Get-Content -Raw ROLE_CHANGE_VALIDATION_PROTOCOL.md
Get-Content -Raw LOCKED_DECISIONS.md
Get-Content -Raw config/role_change_fold2_candidate.yaml
Get-Content -Raw config/role_change_validation.yaml
Get-Content -Raw scripts/run_fold3_validation.py
Get-Content -Raw src/role_validation/fold3.py
Get-Content -Raw scripts/generate_fold3_report.py
Get-Content -Raw scripts/validate_fold3_outputs.py
Get-Content -Raw scripts/build_fold3_notebook.py
Get-Content -Raw tests/test_role_validation_fold3.py
rg -n "^def |^class |CANONICAL_KEY|PRIMARY_POLICY|PARTIAL_POLICIES|EXPECTED_METHODS" src/role_validation/*.py
```

Prior 2021-2023 gate/status files and 2023 schemas were read to preserve the
locked comparison semantics. No actual 2024 row was opened during this phase.

## Pre-result package checks and commits

```powershell
python -m py_compile src/role_validation/fold4.py src/role_validation/redevelopment.py src/role_validation/partial_game.py scripts/freeze_fold4_execution.py scripts/run_fold4_validation.py scripts/generate_fold4_report.py scripts/validate_fold4_outputs.py scripts/validate_fold4_staged_scope.py scripts/build_fold4_notebook.py tests/test_role_validation_fold4.py
python -m pytest -q tests/test_role_validation_redevelopment.py tests/test_role_validation_fold2.py tests/test_role_validation_fold3.py tests/test_role_validation_fold4.py
python -m pytest -q
git diff --check
Get-FileHash -Algorithm SHA256 config/role_change_fold2_candidate.yaml
git add -- src/role_validation/redevelopment.py src/role_validation/partial_game.py src/role_validation/fold4.py scripts/freeze_fold4_execution.py scripts/run_fold4_validation.py scripts/generate_fold4_report.py scripts/validate_fold4_outputs.py scripts/validate_fold4_staged_scope.py scripts/build_fold4_notebook.py tests/test_role_validation_fold4.py tests/test_role_validation_redevelopment.py
git diff --cached --check
git commit -m "Freeze Fold 4 execution package"
git rev-parse HEAD
python scripts/freeze_fold4_execution.py
```

The first targeted package run found the old test expectation that post-2023
requests must fail: **1 failed, 21 passed**. The season-scope test was corrected
before real 2024 access. The rerun passed **22 tests**, and the contemporaneous
full suite passed **28 tests**.

## Invalidated data-audit precheck and schema-only correction

```powershell
python scripts/run_fold4_validation.py --stage precheck
Get-ChildItem -LiteralPath data/raw/role_validation -Filter '*.csv.gz'
Get-Content -Raw outputs/role_validation/fold_4/precheck_failure.json
Test-Path outputs/role_validation/fold_4/fold4_execution_lock.json
Test-Path outputs/role_validation/fold_4/fold4_alerts_2024.csv.gz
python -m py_compile scripts/run_fold4_validation.py tests/test_role_validation_fold4.py
python -m pytest -q tests/test_role_validation_redevelopment.py tests/test_role_validation_fold2.py tests/test_role_validation_fold3.py tests/test_role_validation_fold4.py
python -m pytest -q
git add -- scripts/run_fold4_validation.py tests/test_role_validation_fold4.py
git diff --cached --check
git commit -m "Fix Fold 4 precheck season normalization"
git rev-parse HEAD
python scripts/freeze_fold4_execution.py
python -m py_compile scripts/freeze_fold4_execution.py
git add -- scripts/freeze_fold4_execution.py
git diff --cached --check
git commit -m "Document invalidated Fold 4 precheck"
git rev-parse HEAD
python scripts/freeze_fold4_execution.py
```

The invalidated precheck failed with `KeyError: 'season'`. It produced no alert
archive, execution lock, metric, gate, or recommendation. The corrected package
passed **23 targeted tests** and **29 full-suite tests** before the successful
precheck.

## Successful data audit and single Fold 4 execution

```powershell
python scripts/run_fold4_validation.py --stage precheck
Import-Csv outputs/role_validation/fold_4/data_audit_2024.csv
Import-Csv outputs/role_validation/fold_4/source_coverage_2024.csv
Import-Csv outputs/role_validation/fold_4/join_coverage_2024.csv
Import-Csv outputs/role_validation/fold_4/partial_game_source_coverage_2024.csv
Import-Csv outputs/role_validation/fold_4/data_audit_checks_2024.csv
Import-Csv outputs/role_validation/fold_4/temporal_precheck_2024.csv
Import-Csv outputs/role_validation/fold_4/missingness_2024.csv
python scripts/run_fold4_validation.py --stage execute
```

The `--stage execute` command above was run exactly once.

## Report, notebook, and independent validation

```powershell
python scripts/generate_fold4_report.py
python scripts/build_fold4_notebook.py
python -m nbconvert --to notebook --execute --inplace notebooks/fold_4_untouched_2024_validation.ipynb --ExecutePreprocessor.timeout=300
python scripts/validate_fold4_outputs.py
python -m pytest -q tests/test_role_validation_redevelopment.py tests/test_role_validation_fold2.py tests/test_role_validation_fold3.py tests/test_role_validation_fold4.py
python -m pytest -q
python -m py_compile scripts/freeze_fold4_execution.py scripts/run_fold4_validation.py scripts/generate_fold4_report.py scripts/build_fold4_notebook.py scripts/validate_fold4_outputs.py scripts/validate_fold4_staged_scope.py src/role_validation/fold4.py
```

Read-only `Import-Csv`, `Get-Content`, and Python schema/reconciliation commands
were used to inspect headline, method, directional, weekly, subgroup,
concentration, overlap, partial-sensitivity, cross-season, pooled, gate, and
recommendation tables. They did not write or select alerts.

## Final artifact scope and commit

```powershell
git add -- outputs/role_validation/fold_4 notebooks/fold_4_untouched_2024_validation.ipynb
python scripts/validate_fold4_staged_scope.py
git add -- outputs/role_validation/fold_4/staged_scope_validation.json
python scripts/validate_fold4_staged_scope.py
python scripts/validate_fold4_outputs.py
git diff --cached --check
git diff --cached --name-only
git commit -m "Record Fold 4 validation results"
git rev-parse HEAD
git status --short
```

One attempted `git add` used the nonexistent path
`tests/test_role_validation/fold4.py`; Git rejected the command and staged
nothing from that attempt. The corrected explicit allowlist was then used.
