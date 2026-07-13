# Fold 3 exact command ledger

Working directory for every repository command:

`C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection`

## Checkpoint, branch, and frozen configuration

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git tag -a role-change-validation-v1-pre-fold3-checkpoint c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9 -m "Freeze candidate before untouched 2023 Fold 3 execution"
git rev-parse role-change-validation-v1-pre-fold3-checkpoint^{}
Get-FileHash config/role_change_fold2_candidate.yaml -Algorithm SHA256
Get-FileHash outputs/role_validation/fold_2/frozen_role_change_fold2_candidate.yaml -Algorithm SHA256
Get-FileHash config/role_change_validation.yaml -Algorithm SHA256
Get-FileHash ROLE_CHANGE_VALIDATION_PROTOCOL.md -Algorithm SHA256
Get-FileHash LOCKED_DECISIONS.md -Algorithm SHA256
```

## Pre-run audit and controlled execution

```powershell
python -m pytest -q tests/test_role_validation_redevelopment.py tests/test_role_validation_fold2.py tests/test_role_validation_fold3.py
python scripts/run_fold3_validation.py --stage precheck
python -m py_compile scripts/run_fold3_validation.py src/role_validation/fold3.py
python scripts/run_fold3_validation.py --stage execute
```

`--stage execute` was run exactly once. The execution lock records start/completion timestamps and the alert-archive hash.

## Report, notebook, and independent validation

```powershell
python -m py_compile scripts/generate_fold3_report.py scripts/build_fold3_notebook.py scripts/validate_fold3_outputs.py
python scripts/generate_fold3_report.py
python scripts/build_fold3_notebook.py
python -m jupyter nbconvert --to notebook --execute --inplace notebooks/fold_3_untouched_2023_validation.ipynb --ExecutePreprocessor.timeout=300
& 'C:\Users\tucka\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m jupyter nbconvert --to notebook --execute --inplace notebooks/fold_3_untouched_2023_validation.ipynb --ExecutePreprocessor.timeout=300
python -m nbconvert --to notebook --execute --inplace notebooks/fold_3_untouched_2023_validation.ipynb --ExecutePreprocessor.timeout=300
python scripts/validate_fold3_outputs.py
python scripts/generate_fold3_report.py
python scripts/validate_fold3_outputs.py
```

The first notebook command failed because the default Jupyter launcher did not expose `jupyter-nbconvert`. The bundled workspace Python command failed because that runtime did not include Jupyter. `python -m nbconvert` succeeded with all six code cells executed and zero error outputs. Early validator invocations caught and led to corrections in the validator itself (config path and evaluable-only retention reconstruction); the final independent result is 24/24 passed.

## Tests

```powershell
python -m pytest -q tests/test_role_validation_redevelopment.py tests/test_role_validation_fold2.py tests/test_role_validation_fold3.py
python -m pytest -q
```

## Read-only result and scope inspections

```powershell
Get-ChildItem outputs/role_validation/fold_3 | Sort-Object Name | Select-Object Name,Length | Format-Table -AutoSize
Import-Csv outputs/role_validation/fold_3/partial_game_source_coverage_2023.csv | Format-List
Get-Content outputs/role_validation/fold_3/frozen_config_fingerprint.json
Get-Content outputs/role_validation/fold_3/fold3_execution_lock.json
Get-Content outputs/role_validation/fold_3/FOLD_3_REPORT.md | Select-Object -First 160
git status --short
git diff --stat
git tag --list '*fold3*' --format='%(refname:short) %(objectname)'
git cat-file -p refs/tags/role-change-validation-v1-pre-fold3-checkpoint
git diff -- src/role_validation/redevelopment.py src/role_validation/partial_game.py src/role_validation/fold2.py src/role_validation/fold3.py tests/test_role_validation_redevelopment.py tests/test_role_validation_fold3.py scripts/run_fold3_validation.py scripts/generate_fold3_report.py scripts/build_fold3_notebook.py scripts/validate_fold3_outputs.py
```

Additional read-only Python snippets printed selected CSV tables, archive columns, notebook execution counts, and UTF-8 report checks. They did not write repository state.

## Final staging and commit

These commands are appended/confirmed by the final committed artifact:

```powershell
git add -- src/role_validation/redevelopment.py src/role_validation/partial_game.py src/role_validation/fold2.py src/role_validation/fold3.py scripts/run_fold3_validation.py scripts/generate_fold3_report.py scripts/build_fold3_notebook.py scripts/validate_fold3_outputs.py tests/test_role_validation_redevelopment.py tests/test_role_validation_fold3.py notebooks/fold_3_untouched_2023_validation.ipynb outputs/role_validation/fold_3
python scripts/validate_fold3_outputs.py
git diff --cached --name-only
git diff --cached --check
git commit -m "Execute frozen role detector on Fold 3"
git rev-parse HEAD
git status --short
```
