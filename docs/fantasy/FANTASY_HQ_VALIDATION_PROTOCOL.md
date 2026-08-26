# Fantasy League HQ — Validation Protocol

**Status:** Pre-implementation validation contract  
**Purpose:** Prevent hindsight leakage and require evidence that Fantasy HQ recommendations add decision value beyond simple baselines.

## Principle

Fantasy HQ may always display factual league/NFL evidence. It may not claim that a recommendation method is superior merely because its component signals correlate with historical production.

The unit of validation is the **decision available at the historical timestamp**, using only information that existed then.

## Primary decision families

Validate separately:

1. **Waiver add / hold / pass**
2. **Drop candidate**
3. **Start / sit between genuinely plausible lineup options**
4. **Roster-risk / bye-week planning**

Do not allow strong performance in one family to rescue another.

## Historical replay grain

Recommended base row:

`season × week × league_rules_profile × decision_id`

Each replay stores:

- simulated `as_of_utc`
- league/rules profile
- player identities
- candidate set that would have been known then
- ownership/availability assumptions used
- all source timestamps or historical cutoffs
- recommendation method/version
- recommendation
- evidence available at recommendation time
- outcome window
- realized outcome

## Point-in-time rule

For a Week N recommendation, no feature may use Week N outcome data or any information first available after the simulated recommendation timestamp.

Existing PropWar utilities such as `before_target_mask`, shifted rolling features, history-window audits, role-validation folds, and Week-N-uses-through-N-1 backtests should be reused rather than reimplemented.

Any feature whose historical timestamp cannot be reconstructed reliably must either:

- be excluded from the historical test, or
- be explicitly labeled unavailable for that validation slice.

Never backfill modern knowledge into an older replay.

## Comparison ladder

Where evidence is available, compare at least:

### Baseline A — simple historical production / projection

A deliberately simple reasonable baseline without PropWar role-change intelligence.

### Challenger B — baseline + PropWar role evidence

Adds validated role/change information available at the decision timestamp.

### Challenger C — baseline + role + market context

Adds sportsbook market context only when historical market timestamps/lines can be reconstructed without leakage.

### Challenger D — baseline + role + market + contextual evidence

Adds only separately sourced context such as opponent fit or injury/availability when point-in-time evidence exists.

Do not compare challengers at different candidate volumes without controlling for selection volume or decision difficulty.

## Waiver validation

### Candidate set

A historical waiver replay should operate on players plausibly available under the simulated league depth/rules.

If exact historical league ownership is unavailable, use transparent simulated ownership rules (for example roster-rate/depth constraints) and label the result as a **synthetic-league replay**, not a replay of a real user league.

Once 2026 real league history exists, run a separate real-league prospective audit using actual Sleeper/Yahoo ownership and transaction state.

### Outcomes

No single outcome is sufficient. Track a window such as next 1, 2, 3 and 4 qualifying games where appropriate:

- fantasy points under the tested scoring profile
- starter-level weeks
- role persistence
- roster utility over replacement-level available alternatives
- immediate reversion / bust rate
- missed-opportunity cost for passed players

A waiver recommendation should not be judged only by whether the player had one spike week.

## Start/sit validation

Only evaluate decisions where both players were reasonable lineup candidates at the recommendation timestamp.

Avoid inflating accuracy with obvious decisions such as elite healthy starters versus non-startable bench players.

Track:

- win/loss/tie of the head-to-head decision
- fantasy-point difference
- expected decision value when projection distributions are available
- whether the chosen player was available/active at lock
- late injury/inactive states separately

Report accuracy by margin/difficulty bucket so easy calls do not hide poor close-call performance.

## Drop validation

A drop recommendation is successful only if the released player was expendable relative to alternatives and did not produce meaningful near-term regret that the evidence should reasonably have anticipated.

Track:

- next 1–4 week production
- role resurgence
- re-add / opponent add where real league history is available
- replacement player's value
- roster-slot opportunity cost

## Role evidence validation inheritance

Fantasy HQ does not redefine role persistence.

Use the existing PropWar role-validation methodology for supported role families. A factual weekly screening category such as `OPPORTUNITY_GAINED` is not automatically a persistent-role claim.

Fantasy recommendation evidence should distinguish:

- factual role screen
- detector alert
- persistence pending
- historically persistent / reverted after outcome is known

## Early-season prior testing

Do not assume the existing research weights (for example fixed 25%/50%/70% current-season weighting) are optimal for fantasy.

Test alternative prior-decay schedules using historical replay, while preserving a final holdout/prospective period.

Candidate state labels may include:

- `PRIOR_HEAVY`
- `CURRENT_BLEND`
- `CURRENT_STRONG`
- `DISRUPTED`

The state labels are explanatory. Exact weights must be empirically justified.

## Recommendation volume

A method that emits far more recommendations can appear better merely by finding more easy wins.

For fair comparisons:

- match candidate/alert volume where practical
- stratify by position and decision family
- report no-action rate
- report suppressed recommendations due to stale/unresolved evidence

## Data-quality gates

A historical or prospective recommendation is not eligible for the primary audit if a required input has:

- unresolved canonical player identity
- future leakage
- incomplete league ownership when ownership is essential
- incomplete NFL week under the role pipeline's completion policy
- confirmed partial-game distortion not handled by policy
- stale provider state beyond the decision's safety threshold

Excluded rows remain in an exclusion ledger with reason codes.

## 2026 prospective ledger

All live Fantasy HQ recommendations must be append-only and retain:

- recommendation ID
- generated timestamp
- league ID / scoring-rules version
- player IDs
- action
- evidence schema version
- evidence snapshot or reproducible evidence references
- source freshness
- rules/model version
- safety/quality status
- superseded recommendation ID if the recommendation later changes

Never delete or rewrite a prior recommendation after the result is known.

## Promotion gates

Do not promote a recommendation family from experimental to trusted solely because it is directionally promising.

Before a stronger label, require:

- adequate historical sample
- consistent improvement versus a simple baseline
- acceptable immediate-regret/reversion behavior
- consistency across multiple seasons/periods or a credible prospective sample
- no evidence of leakage
- no one-component dominance that contradicts the intended method
- transparent failure cases

Exact numerical gates should be set after the first replay distribution is generated, then frozen before the final holdout/prospective evaluation.

## Reporting

Every validation report should include:

- sample size
- seasons/weeks
- decision-family breakdown
- position breakdown
- easy/close decision breakdown where applicable
- baseline and challenger results
- exclusions and missing evidence
- confidence intervals/uncertainty where appropriate
- known limitations
- recommendation-volume comparison

A result is research evidence, not a profitability or guaranteed fantasy-performance claim.
