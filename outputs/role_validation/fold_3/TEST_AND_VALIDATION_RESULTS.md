# Fold 3 test and validation results

## Controlled execution

- Pre-run audit: **passed**.
- Fold 3 executions: **1**.
- Test season: **2023 only**.
- 2024–2025 results used: **no**.
- Fold 4 executed: **no**.
- Frozen configuration hash: `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7` (**matches Fold 2**).
- Equal-volume verification: **216/216 family-week-policy cells passed**.
- Temporal integrity: **8/8 checks passed**.

## Automated tests

- Targeted role-validation tests: **19 passed in 7.27s**.
- Full repository suite: **25 passed in 7.61s**.
- Python compilation checks: **passed**.

## Notebook

- Notebook: `notebooks/fold_3_untouched_2023_validation.ipynb`.
- Execution engine: `python -m nbconvert`.
- Code cells: **6/6 executed**.
- Error outputs: **0**.

The default `python -m jupyter nbconvert` launcher and the bundled workspace Python did not expose a usable nbconvert command. Those environment attempts failed before notebook execution; the installed `nbconvert` module then executed the notebook successfully.

## Independent output validator

- Final result: **24/24 passed**.
- Recomputed from the machine-readable alert archive:
  - season isolation;
  - canonical row count, duplicate keys, and required nulls;
  - baseline/confirmation/outcome chronology;
  - equal-volume method counts;
  - alerts, evaluable counts, precision, reversion, and median retention for all 48 family-method-policy rows;
  - frozen and current configuration hashes and semantic equality;
  - alert-archive hash;
  - RB gate statuses;
  - WR/TE retired status.

## Staged-scope validation

- No dashboard path is in the task staging set.
- No locked protocol, locked decisions, release-gate configuration, or Fold 2 frozen candidate is in the task staging set.
- `git diff --cached --check`: recorded after final staging.
- Existing unrelated worktree changes were preserved and excluded from the commit.
