# Test and Validation Results

## Outcome

PASS. Fold 2 remains unexecuted, post-2021 results were not used, locked files retain their original SHA-256 hashes, and no dashboard file is part of the scoped change.

## Unit tests

```text
python -m pytest -q tests/test_role_validation_redevelopment.py
.............                                                            [100%]
13 passed in 1.23s

python -m pytest -q
...................                                                      [100%]
19 passed in 1.57s
```

Coverage added for:

- disjoint baseline construction;
- strict consecutive-game confirmation;
- season reset and prevention of cross-season Week 1 features;
- confirmed-versus-suspected partial policy;
- team-next-game temporal boundary rather than player-next-appearance;
- historic `LV`/`OAK` team-alias normalization and empty evidence schemas;
- direction-sensitive repeat suppression;
- four-method equal volume including zero-alert family-weeks;
- feed deduplication, RB overlap, and consecutive repeats;
- structural sample/concentration score no-op in legacy selection;
- rejection of post-2021 redevelopment requests.

## Notebook

```text
python -m nbconvert --execute --to notebook --inplace notebooks/fold_1_detector_diagnostics.ipynb --ExecutePreprocessor.timeout=300
```

- Executed code cells: 9/9
- Error outputs: 0
- Fold 2 execution flag: false
- Allowed seasons asserted: 2018, 2019, 2020, 2021

## Independent validator

```text
python scripts/validate_fold1_diagnostics.py --require-staged-scope
{
  "status": "PASS",
  "checks_passed": 59
}
```

The validator independently checks branch/tag identity, locked hashes, season limits, Fold 2 flags, canonical grain and missingness, partial evidence timing, no-return evidence, original counts, RB overlap, repeat counts, all expected methods, family-week equal volume, archive uniqueness, recommended membership, confidence intervals, relative improvement when defined, diagnostic-only gate status, manual-review hash/count, report completeness, and notebook execution.

The final staged-scope invocation additionally rejects staged dashboard files, staged locked protocol/decision/gate files, or other forbidden public-dashboard scope.
