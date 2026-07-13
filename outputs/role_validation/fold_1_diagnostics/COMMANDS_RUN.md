# Commands Run

All commands below were run from:

`C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection`

This records every material analysis, mutation, test, notebook, validation, and Git command. Read-only discovery used `git status`, `git log`, `rg`, `Get-Content`, `Get-ChildItem`, and short inline Python/Pandas probes throughout; those probes inspected only repository state and 2018–2021 diagnostic artifacts. All source edits were applied with the Codex `apply_patch` operation.

## Branch and checkpoint

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
git tag -a role-change-validation-v1-fold1-checkpoint 00d6085a55c60147e0ace46c847460ef5708e968 -m "Preserve original Fold 1 checkpoint before detector redevelopment"
git for-each-ref refs/tags/role-change-validation-v1-fold1-checkpoint --format="%(objecttype)|%(objectname)|%(subject)|%(*objectname)"
```

## Diagnostic development and execution

```powershell
python -m py_compile src/role_validation/redevelopment.py src/role_validation/diagnostics.py src/role_validation/partial_game.py src/role_validation/legacy_ablation.py scripts/run_fold1_diagnostics.py
python scripts/run_fold1_diagnostics.py --stage explore
python scripts/run_fold1_diagnostics.py --stage final --recommended-config config/role_change_fold2_candidate.yaml
```

The explore command was rerun while implementing integrity checks. Early attempts exposed and then fixed a grouping-key error and one infeasible one-game comparator cell; the latter remains recorded as the single screen integrity failure. The final command was rerun after confirmed fixes for fixed-volume ablation backfill, next-team-game temporal boundaries, Raiders alias normalization, global no-return play ordering, and CI grouping. One obsolete superseded raw ablation archive was removed only after its resolved absolute path was verified inside the diagnostic output directory:

```powershell
$target = Resolve-Path -LiteralPath "outputs/role_validation/fold_1_diagnostics/legacy_safeguard_ablation_alerts_2021.csv.gz" -ErrorAction Stop
if ($target.Path -notlike "C:\Users\tucka\OneDrive\Desktop\NFL PRop Projection\outputs\role_validation\fold_1_diagnostics\*") { throw "Refusing unexpected path $($target.Path)" }
Remove-Item -LiteralPath $target.Path
```

Final successful execution:

```powershell
python scripts/run_fold1_diagnostics.py --stage final --recommended-config config/role_change_fold2_candidate.yaml
```

Result: exit 0 in 584.7 seconds; 28,199 canonical rows; 53 valid screens and 1 documented integrity failure; all serious candidates equal-volume; Fold 2 false; post-2021 results false.

## Manual false-positive adjudication

All 254 false-positive rows were displayed in reason-code batches with player/week/family, direction, baselines, opportunities, denominators, partial evidence, outcomes, duplicate, and repeat context. The materialization command was:

```powershell
python scripts/finalize_fold1_false_positive_review.py --review config/fold1_false_positive_manual_review.yaml
```

Result: 254/254 manually adjudicated; 66 transparent overrides; source SHA-256 locked in `manual_review_manifest.json`.

## Report and notebook

```powershell
python scripts/generate_fold1_diagnostic_report.py
python scripts/build_fold1_diagnostic_notebook.py
python -m nbconvert --execute --to notebook --inplace notebooks/fold_1_detector_diagnostics.ipynb --ExecutePreprocessor.timeout=300
```

Result: report generated; notebook executed top-to-bottom with 9 executed code cells and 0 error outputs.

## Tests and validation

```powershell
python -m pytest -q tests/test_role_validation_redevelopment.py
python scripts/validate_fold1_diagnostics.py
python -m pytest -q
```

Results:

- Targeted redevelopment tests: 13 passed.
- Independent diagnostic validator: 57 core checks passed; 59 checks passed with staged-scope enforcement.
- Full unit suite: 19 passed.

The staged-scope validator and Git commit commands are run during final staging:

```powershell
git add -- config/fold1_false_positive_manual_review.yaml config/role_change_fold1_experiments.yaml config/role_change_fold2_candidate.yaml notebooks/fold_1_detector_diagnostics.ipynb outputs/role_validation/fold_1_diagnostics scripts/build_fold1_diagnostic_notebook.py scripts/finalize_fold1_false_positive_review.py scripts/generate_fold1_diagnostic_report.py scripts/run_fold1_diagnostics.py scripts/validate_fold1_diagnostics.py src/role_validation/diagnostics.py src/role_validation/legacy_ablation.py src/role_validation/partial_game.py src/role_validation/redevelopment.py tests/test_role_validation_redevelopment.py
git diff --cached --name-only
git diff --cached --check
python scripts/validate_fold1_diagnostics.py --require-staged-scope
git add -- outputs/role_validation/fold_1_diagnostics/final_validation.json
git commit -m "Redevelop role detector after Fold 1 diagnostics"
```

No Fold 2, merge, push, deployment, or dashboard command was run.
