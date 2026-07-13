# Fold 2 Commands Run

All repository commands were run from:

`C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection`

Read-only discovery used `git status`, `git log`, `git rev-parse`, `rg`, `Get-Content`, `Get-ChildItem`, `Import-Csv`, `Get-FileHash`, and bounded inline Python/Pandas probes. Those probes inspected the frozen configuration, Fold 1 report, 2022-only canonical/source partitions, generated artifacts, and Git scope. No 2023–2025 result partition was selected.

## Branch, fingerprint, and checkpoint

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
Get-FileHash -Algorithm SHA256 -LiteralPath 'config/role_change_fold2_candidate.yaml'
git diff --name-only HEAD -- config/role_change_fold2_candidate.yaml
git tag -a role-change-validation-v1-pre-fold2-checkpoint bdff056fa625eef76152e1b9f3ef0e88fda2bbab -m 'Freeze candidate before untouched 2022 Fold 2 execution'
git rev-list -n 1 role-change-validation-v1-pre-fold2-checkpoint
```

Frozen SHA-256: `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7`.

## Pre-run implementation and automated checks

All source edits were made with the Codex `apply_patch` operation. The detector rules and candidate YAML were not edited.

```powershell
python -m py_compile src/role_validation/redevelopment.py src/role_validation/evaluation.py src/role_validation/fold2.py src/role_validation/partial_game.py scripts/run_fold2_validation.py tests/test_role_validation_fold2.py
python -m pytest -q tests/test_role_validation_redevelopment.py tests/test_role_validation_fold2.py
python scripts/run_fold2_validation.py --stage precheck
```

Pre-run result: 16 targeted tests passed; the 2022 audit passed; evaluation remained unexecuted.

A synthetic-only post-processing preflight was run with a bounded inline Python script. Its first run exposed a missing-method-column edge case in the release-table pivot. That code defect was fixed before the 2022 execution. The preflight was rerun successfully, followed by:

```powershell
python -m py_compile src/role_validation/fold2.py scripts/run_fold2_validation.py tests/test_role_validation_fold2.py
python -m pytest -q tests/test_role_validation_redevelopment.py tests/test_role_validation_fold2.py
```

Result: 16 passed. The execute command also reran the same targeted tests internally immediately before creating the execution lock; its captured output is `pre_execution_test_results.txt`.

## Single Fold 2 execution

```powershell
python scripts/run_fold2_validation.py --stage execute
```

Result: exit 0 in 30.3 seconds. The execution lock records one completed 2022 run and the frozen alert-archive hash. The command cannot be rerun while the lock exists.

## Reports and notebook

```powershell
python scripts/generate_fold2_report.py
```

The first report-generation attempt failed before writing a report because optional `tabulate` was not installed. The generator was changed to use a dependency-free Markdown renderer, then the same command succeeded. It was run once more after adding the direct direction-generalization and named partial-sensitivity artifacts. No detector calculation was rerun.

```powershell
python scripts/build_fold2_notebook.py
python -m nbconvert --execute --to notebook --inplace notebooks/fold_2_untouched_2022_validation.ipynb --ExecutePreprocessor.timeout=300
```

The notebook executed top-to-bottom without error.

## Tests and independent validation

```powershell
python -m py_compile scripts/generate_fold2_report.py scripts/build_fold2_notebook.py scripts/validate_fold2_outputs.py
python scripts/validate_fold2_outputs.py
python -m pytest -q
python scripts/validate_fold2_outputs.py
```

Results: 22 full-suite tests passed; independent validation passed 60 checks before staging.

## Final staging and commit

```powershell
git add -- src/role_validation/redevelopment.py src/role_validation/evaluation.py src/role_validation/partial_game.py src/role_validation/fold2.py scripts/run_fold2_validation.py scripts/generate_fold2_report.py scripts/build_fold2_notebook.py scripts/validate_fold2_outputs.py tests/test_role_validation_redevelopment.py tests/test_role_validation_fold2.py notebooks/fold_2_untouched_2022_validation.ipynb outputs/role_validation/fold_2
git diff --cached --name-only
git diff --cached --check
python scripts/validate_fold2_outputs.py --require-staged-scope
git add -- outputs/role_validation/fold_2/final_validation.json outputs/role_validation/fold_2/COMMANDS_RUN.md outputs/role_validation/fold_2/TEST_AND_VALIDATION_RESULTS.md
git commit -m "Execute frozen role detector on Fold 2"
```

No merge, push, deployment, dashboard command, Fold 3 execution, post-2022 evaluation, or candidate-tuning command was run.
