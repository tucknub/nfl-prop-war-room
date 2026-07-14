# PropWar Phase Gates

## Phase A — Targeted Correctness Audit

Phase A passes only when all of the following are true:

- [ ] The audit executes reproducibly.
- [ ] There is no unresolved Critical issue.
- [ ] There is no unresolved High issue.
- [ ] Season, Last 8, Last 4, and Last 2 windows are independently verified.
- [ ] Displayed shares reconcile to summed player opportunities divided by summed same-context team opportunities.
- [ ] Home comparison periods, counts, shares, ordering, and leakage controls reconcile.
- [ ] Cross-page values agree where filters and definitions are identical.
- [ ] Public player and team links resolve correctly.
- [ ] Explorer filters and Reset behavior are correct and free from stale hidden state.
- [ ] Required edge cases are documented.
- [ ] Public language remains factual and non-predictive.
- [ ] Protected files are unchanged from the production baseline.
- [ ] Targeted tests, full tests, compilation, data validation, audit validators, and Git whitespace checks pass.

Any unresolved Critical or High correctness issue makes Phase A **FAILED**. Missing source evidence that prevents a required check makes Phase A **BLOCKED**. A pooled or aggregate pass cannot erase an individual failed gate.

## Later phases

No later phase is authorized by this document. Phase transitions require explicit user authorization.
