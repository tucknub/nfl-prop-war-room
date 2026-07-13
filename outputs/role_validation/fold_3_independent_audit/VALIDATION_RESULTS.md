# Independent Fold 3 audit validation results

## Audit calculations

- Independent audit manifest: **passed**.
- Audited commit: `a18c5cc3e8c9124be4781bececea0a93f7b4faf8`.
- Headline method rows independently recomputed: **8/8 reconciled**.
- Committed headline metric reconciliation: **7 metric groups matched**, maximum floating difference `8.9e-16`.
- Pooled calculations: recomputed from raw 2022–2023 alert numerators, denominators, and retention values.
- Equal-volume cells: **216/216 passed**.
- Comparator eligibility/ranking replay: **648/648 passed**.
- Full-alert frozen-rule compliance: **all 12 policy-family groups passed with zero violations**.
- Temporal checks: **10/10 passed**.
- Outcome-label reconstruction: **9/9 fields matched across 660 primary alert-method rows**.
- Recorded input hashes: **6/6 matched**.
- Duplicate alert-grain rows: **0**.
- Fold 4 executed: **no**.

## Tests

- Targeted role-validation suite: **19 passed in 7.45s**.
- Full repository suite: **25 passed in 7.97s**.
- Python compilation checks: **passed**.

## Notebook

- Notebook: `notebooks/fold_3_independent_methodological_audit.ipynb`.
- Code cells executed: **8/8**.
- Error outputs: **0**.

## Independent audit validator

- Final result: **22/22 checks passed**.
- Validated raw numerators, headline lifts, both family decisions, pooled numerators, equal volume, comparator replay, full-rule compliance, temporal order, outcome reconstruction, input hashes, report recommendations, notebook execution, and protected detector/config scope.

## Scope

- No existing detector configuration, role-validation source, Fold 3 result, or dashboard file was changed by this audit.
- Existing unrelated worktree changes remain outside the audit staging set.
- No merge, push, deployment, tuning, detector rule change, 2024/2025 result use, or Fold 4 execution occurred.
