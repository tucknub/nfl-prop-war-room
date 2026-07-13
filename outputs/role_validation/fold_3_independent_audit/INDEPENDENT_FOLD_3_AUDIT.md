# Independent Methodological Audit — Fold 3

Audited branch/commit: `role-change-validation-v1` at `a18c5cc3e8c9124be4781bececea0a93f7b4faf8`

## Overall assessment: Share with caveats

The stated Fold 3 gate decisions are arithmetically and methodologically correct under the locked protocol:

- RB carry legitimately receives `PASSES_FOLD_3_POINT_GATES`.
- RB opportunity legitimately receives `FAILS_FOLD_3_POINT_GATES` solely because the pre-existing cross-period direction-consistency rule fails.
- WR and TE remain retired; nothing in this audit supports reinstatement.
- Neither RB family is validated.

No calculation, data-integrity, equal-volume, or temporal-leakage error requires overturning the decisions. RB carry's pass is nevertheless fragile: its 2023 improvement interval includes zero, only 47 of 60 alerts are persistence-evaluable, its carry-only subset is weak, and several subgroup results are materially less favorable than the aggregate. Those limitations support another untouched fold; they do not authorize a public validation claim.

## Issues and caveats

1. **Medium — RB carry's point-gate pass is fragile, although legitimate.** Three persistence-outcome flips would fail the precision gate, two would fail the naive-lift gate, and two additional immediate reversions would fail the reversion gate. The official lift interval is −3.1 to +26.3 points. This affects confidence, not the precommitted point-gate status.
2. **Medium — Carry's 2023 result depends strongly on overlap with RB opportunity alerts.** The 41 overlapping alerts have 75.8% precision; the 19 carry-only alerts have 42.9% precision and 41.2% reversion. Pooled 2022–2023 carry-only precision is 61.5%, so this is not a stable basis for a new exclusion or rule, but standalone incremental carry-family value is not established.
3. **Medium — The pre-run manifest's literal source-read claim is inaccurate.** The source files are named `*_2017_2025` and are scanned chunk-by-chunk before each chunk is filtered to 2023. Therefore `post_2023_seasons_read: false` is not literally true at file-I/O level. The scored canonical, features, injury evidence, identity joins, and outcomes are demonstrably 2023-only; no 2024–2025 values entered scoring. This is a provenance/documentation issue, not detected outcome leakage.
4. **Medium — Direction consistency is not direction-equal-volume.** The locked comparison is equal-volume by family-week, as the protocol requires. Once alerts are split by direction, method counts may differ. The failing 2021 opportunity-decrease cell is 33 detector alerts versus 34 naive alerts. This operationalization was documented before Fold 3 and cannot be changed now, but descriptions should avoid implying equal volume within direction.
5. **Low/medium — The exact Fold 3 runner was not checkpointed before execution.** The pre-Fold-3 tag contains the frozen candidate and core detector code, but not the newly created Fold 3 runner; the lock hashes the config and resulting archive, not runner source. Core selection/evaluation logic is unchanged except for admitting 2023, the committed runner is reproducible, and independent checks reconcile it. This is not evidence of tuning, but Fold 4 should checkpoint and hash the runner before holdout access.

## Independently recomputed 2023 results

All rates below were recomputed from raw archive numerators. Precision uses non-null two-game persistence outcomes; reversion uses non-null next-game outcomes; retention is the median over persistence-evaluable rows.

| Family | Method | Alerts | Evaluable | Persistent | Precision (95% CI) | Reversion | Median retention |
|---|---|---:|---:|---:|---:|---:|---:|
| Carry | Naive spike | 60 | 49 | 26 | 53.1% (38.8–67.3%) | 32.7% | 52.7% |
| Carry | Two-week raw | 60 | 49 | 33 | 67.3% (55.1–79.6%) | 20.8% | 74.6% |
| Carry | Normal-game trend | 60 | 49 | 31 | 63.3% (51.0–75.5%) | 20.8% | 75.5% |
| Carry | Frozen full detector | 60 | 47 | 31 | 66.0% (53.2–78.7%) | 23.1% | 79.5% |
| Opportunity | Naive spike | 74 | 58 | 33 | 56.9% (44.8–69.0%) | 31.7% | 61.7% |
| Opportunity | Two-week raw | 74 | 59 | 39 | 66.1% (54.2–78.0%) | 18.8% | 70.2% |
| Opportunity | Normal-game trend | 74 | 58 | 42 | 72.4% (60.3–84.5%) | 15.6% | 73.0% |
| Opportunity | Frozen full detector | 74 | 57 | 44 | 77.2% (66.7–87.7%) | 15.6% | 91.0% |

Full-versus-naive:

| Family | Full precision | Naive precision | Absolute lift (95% CI) | Reversion improvement |
|---|---:|---:|---:|---:|
| RB carry | 65.96% | 53.06% | +12.90 pp (−3.06 to +26.33) | +9.62 pp |
| RB opportunity | 77.19% | 56.90% | +20.30 pp (+5.78 to +34.40) | +16.12 pp |

The precision intervals reproduce the committed 2,000-draw alert-row bootstrap with seed 850. The lift intervals reproduce the committed 2,000-draw season-week cluster bootstrap. Precision intervals are not player- or week-clustered; lift intervals are week-clustered but not player-clustered.

### Weekly alert counts

- RB carry, weeks 1–18: `0, 0, 0, 0, 0, 2, 4, 6, 2, 4, 6, 6, 5, 8, 3, 4, 4, 6`; median 4.0, maximum 8, five zero weeks.
- RB opportunity, weeks 1–18: `0, 0, 0, 0, 0, 3, 6, 7, 3, 4, 11, 5, 4, 7, 5, 7, 5, 7`; median 4.5, maximum 11, five zero weeks.

Weeks 17–18 contain ten carry alerts but no two-game persistence outcomes. Removing those alerts leaves exactly 50 alerts, so late censoring does not by itself create the volume pass, but it reduces effective outcome evidence to 47 cases.

### Directional results

| Family | Direction | Full alerts/evaluable | Full precision | Naive alerts/evaluable | Naive precision | Lift | Reversion | Retention |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Carry | Decrease | 31/25 | 60.0% | 27/22 | 50.0% | +10.0 pp | 25.9% | 70.2% |
| Carry | Increase | 29/22 | 72.7% | 33/27 | 55.6% | +17.2 pp | 20.0% | 83.0% |
| Opportunity | Decrease | 41/34 | 79.4% | 32/27 | 59.3% | +20.2 pp | 13.5% | 95.3% |
| Opportunity | Increase | 33/23 | 73.9% | 42/31 | 54.8% | +19.1 pp | 18.5% | 86.2% |

Directional alert counts differ because the locked equality grain is family-week, not family-week-direction.

## Gate-by-gate verification

### RB carry

| Locked gate | Requirement | Observed | Result |
|---|---:|---:|---|
| Holdout alerts | ≥ 50 | 60 | Pass |
| Persistence precision | ≥ 60% | 65.96% | Pass |
| Absolute improvement vs naive | ≥ 10 pp | +12.90 pp | Pass |
| Immediate reversion | ≤ 25% | 23.08% | Pass |
| Reversion improvement | ≥ 8 pp | +9.62 pp | Pass |
| Median retention | ≥ 50% | 79.49% | Pass |
| Alerts per NFL week | ≥ 0.5 | 3.33 | Pass |
| Direction consistent across periods | All available cells ≥ naive | 6/6 nonnegative | Pass |
| Frozen before holdout | Required | Config/tag/hash verified | Pass |

`PASSES_FOLD_3_POINT_GATES` is correct. No gate was omitted or weakened.

### RB opportunity

| Locked gate | Requirement | Observed | Result |
|---|---:|---:|---|
| Holdout alerts | ≥ 50 | 74 | Pass |
| Persistence precision | ≥ 60% | 77.19% | Pass |
| Absolute improvement vs naive | ≥ 10 pp | +20.30 pp | Pass |
| Immediate reversion | ≤ 25% | 15.63% | Pass |
| Reversion improvement | ≥ 8 pp | +16.12 pp | Pass |
| Median retention | ≥ 50% | 91.01% | Pass |
| Alerts per NFL week | ≥ 0.5 | 4.11 | Pass |
| Direction consistent across periods | All available cells ≥ naive | 5/6 nonnegative | **Fail** |
| Frozen before holdout | Required | Config/tag/hash verified | Pass |

`FAILS_FOLD_3_POINT_GATES` is correct. The sole failed gate is direction consistency.

### Exact 2021 opportunity-decrease cell

- Detector: 33 alerts, 22 evaluable, 14 persistent; `14/22 = 63.64%`.
- Naive: 34 alerts, 23 evaluable, 15 persistent; `15/23 = 65.22%`.
- Lift: `−1.58 percentage points`.

This is the only negative opportunity direction cell across 2021–2023 and exactly causes the locked failure. The one-alert and one-evaluable-case difference is permitted by family-week equal-volume selection but makes this direction result statistically delicate. It must not be waived after 2023.

## Pooled untouched 2022–2023 verification

The pooled calculations concatenate raw 2022 and 2023 alert rows. They do not average seasonal percentages.

| Family | Raw precision numerator | Precision | Naive numerator | Naive | Lift (95% CI) | Reversion numerator | Reversion | Raw retention median |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Carry | 56/86 | 65.12% | 44/87 | 50.57% | +14.54 pp (+3.53 to +24.93) | 18/92 | 19.57% | 73.86% |
| Opportunity | 73/104 | 70.19% | 57/103 | 55.34% | +14.85 pp (+2.39 to +26.13) | 17/114 | 14.91% | 79.38% |

The committed rounded claims—109 carry alerts and 133 opportunity alerts, 65.1%/+14.5/19.6/73.9 and 70.2%/+14.9/14.9/79.4—are verified without discrepancy. These results are supportive, but they cannot erase carry's 49-alert 2022 failure or opportunity's 2022 +8.4-point lift failure.

## Subgroup-dependence findings

### Direction and season

- Carry is materially stronger on increases. Pooled 2022–2023 increases are 77.5% precise with +24.3-point lift; decreases are 54.3% with +6.8-point lift.
- Carry nevertheless beats naive in every available season-direction cell, which is the locked consistency definition.
- Aggregate carry performance is positive in both untouched seasons: 64.1% precision/+16.7 points in 2022 and 66.0%/+12.9 points in 2023. It is not a one-season-only aggregate effect.
- Opportunity is strong in both 2023 directions, but the historical 2021 decrease failure remains controlling.

### Early, middle, and late season

- Carry: weeks 1–6 `2 alerts/50.0%`; weeks 7–12 `28/67.9%`; weeks 13–18 `30 alerts, 17 evaluable/64.7%`.
- Opportunity: weeks 1–6 `3/66.7%`; weeks 7–12 `36/80.0%`; weeks 13–18 `35 alerts, 19 evaluable/73.7%`.
- No single week dominates carry volume; the largest week contributes 13.3%. Late-season outcome censoring is the larger concern.

### Teams, players, and repeats

- Carry spans 24 teams and 39 players. The top team contributes 10.0%; the top player 6.7%. Team and player effective-group counts are 18.0 and 31.0.
- Carry leave-one-team-out precision ranges 62.8–68.9%; leave-one-player-out precision 64.4–68.2%. No single entity creates the precision pass.
- Fifteen carry players have multiple alerts and account for 36/60 alerts, but only one alert is a literal consecutive-week repeat. No one player has more than four alerts.
- Opportunity has zero consecutive-week repeats. Ordinary within-player correlation remains a reason not to overread IID precision intervals.

### RB-family overlap

| Carry subset | 2023 alerts/evaluable | Precision | Reversion | Retention |
|---|---:|---:|---:|---:|
| Also opportunity alert | 41/33 | 75.8% | 14.3% | 83.9% |
| Carry only | 19/14 | 42.9% | 41.2% | 38.8% |

The relationship reverses in 2022, and pooled carry-only precision is 61.5%. Therefore this is a material dependence and a reason for caution, not a defensible post hoc rule change.

### Partial-game policy

| Policy | Carry alerts | Precision | Naive lift | Reversion | Reversion improvement | Retention |
|---|---:|---:|---:|---:|---:|---:|
| Include all | 61 | 66.0% | +10.9 pp | 24.5% | **+7.5 pp** | 75.5% |
| Primary confirmed-excluded | 60 | 66.0% | +12.9 pp | 23.1% | +9.6 pp | 79.5% |
| Also exclude suspected | 59 | 64.6% | +11.5 pp | 23.1% | +9.6 pp | 79.2% |

The primary and strict policies pass their aggregate numeric checks. Including confirmed partials would miss the 8-point reversion-improvement gate by 0.5 points. Sensitivity analyses cannot override the locked primary, but the prior report's statement that the recommendation is unchanged should not be read as saying every sensitivity passes every gate.

No confirmed partial alert remains under the primary policy. Suspected rows remain included as required. Reconstructed injury evidence timestamps occur after the triggering game and before the next game.

### Retention outliers and low-opportunity games

- Carry retention median is 79.5%; 10%-trimmed mean is 72.0% and `[0,1]`-clipped mean is 63.8%. Extreme positive values do not manufacture the median pass.
- Carry alerts with 6–9 current raw opportunities are weak in 2023: 3/12 persistent (25.0%) and 46.2% reversion. This was not monotonic across opportunity bands and was not stable in 2022.
- Carry's 18–20 team-denominator band is 8/13 persistent (61.5%) but has 38.5% reversion. Other denominator bands are non-monotonic.

These are diagnostics only. They do not justify a new exclusion or threshold.

## Equal-volume and comparator-integrity verification

- All 216 policy × family × week cells have identical counts for all four methods, including zero-alert weeks.
- Independent archive grouping found zero unequal cells and zero duplicate alert-grain keys.
- Every selected RB row has resolved identity, `data_quality_pass`, qualifying-game status, at least four baseline games, and a complete method-specific confirmation window.
- Naive outcome evaluability is slightly higher than full-detector evaluability for both RB families, so missing outcomes do not artificially depress naive precision.
- A secondary replay rebuilt all 648 comparator policy × family × method × week eligibility/ranking cells from the 2023 canonical archive. Every pool was large enough and every archived comparator set exactly matched deterministic top-absolute-score selection.
- Every full alert satisfies the frozen delta, raw-opportunity, denominator, confirmation, quality, and partial-policy rules.

Comparator methods intentionally use their predeclared one-game/two-game and all-game/normal-game definitions. They do not inherit the full detector's threshold safeguards; that is the protocol's intended naive comparison, not an outcome-derived eligibility filter.

## Temporal and leakage verification

- Ten independent temporal/data-order checks pass.
- All baselines end before confirmation starts.
- Confirmation ends on the alert week.
- Future game one is after the alert; future game two is after future game one.
- All nine stored outcome fields—future counts/values/weeks, retention, persistence, and reversion—were reconstructed from the 2023 canonical archive with zero mismatches.
- Alert and enriched canonical archives contain only season 2023.
- The primary policy has no confirmed partial rows and retains suspected rows.
- All six recorded source hashes still match the execution manifest.
- Candidate, Fold 2 frozen copy, and Fold 3 frozen copy share SHA-256 `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7`.
- Protocol, locked decisions, and release-gate hashes are unchanged.
- Core alert selection occurs before future outcomes are attached.
- Explicit injury/roster/schedule sources are requested for 2023, and scoring enforces `allowed_seasons=[2023]`.

No 2024–2025 value enters features, exclusions, injury classifications, identity resolution, or outcomes. The only caveat is literal I/O: multi-season cache files are scanned before 2023 rows are selected. Future runs should stage season-partitioned inputs and use a manifest label such as `post_2023_values_selected=false`.

## Uncertainty assessment

RB carry's 2023 interval is compatible with both a practically meaningful advantage and no advantage: its lift CI is −3.1 to +26.3 points. The point estimate clears the frozen gate, and the protocol explicitly says intervals do not move point gates. Pooled untouched lift is positive with a +3.5-point lower bound, which strengthens the evidence, but it remains historical development-fold evidence.

RB opportunity's 2023 and pooled aggregate evidence is stronger than carry's. It must still remain shadow-only because the locked direction rule was defined before 2023 and fails on 2021 decreases. Waiving that cell after seeing 2023 would be hindsight reinterpretation.

The Fold 3 report's central claims are not stronger than the gate evidence because it repeatedly says “point-gate pass” and “not validated.” It underemphasizes carry/opportunity overlap, late censoring, partial-sensitivity gate fragility, the literal source-read nuance, and the uncheckpointed runner. Those are required caveats for the next handoff.

## Final family recommendations

- RB carry: `ADVANCE_UNCHANGED_TO_FOLD_4`
- RB opportunity: `CONTINUE_UNCHANGED_SHADOW_FOLD_4`
- WR target: `REMAIN_RETIRED`
- TE target: `REMAIN_RETIRED`

These recommendations do not authorize Fold 4 execution in this task.

## Blockers

No blocker invalidates the Fold 3 decisions. Before a later Fold 4 run, the exact runner and all input partition manifests should be committed and hashed before holdout access; that is a forward provenance control, not a detector redesign.

## Files inspected

- `ROLE_CHANGE_VALIDATION_PROTOCOL.md`
- `LOCKED_DECISIONS.md`
- `config/role_change_validation.yaml`
- `config/role_change_fold2_candidate.yaml`
- `src/role_validation/evaluation.py`
- `src/role_validation/redevelopment.py`
- `src/role_validation/partial_game.py`
- `src/role_validation/fold2.py`
- `src/role_validation/fold3.py`
- `scripts/run_fold3_validation.py`
- `scripts/validate_fold3_outputs.py`
- All committed Fold 3 manifests, reports, audit/source/join tables, canonical archive, and alert archive
- Fold 2 alert archive and Fold 1 2021 recommended-candidate alert archive

## Tests and calculations executed

- Independent raw-numerator aggregation for every RB family/method.
- Independent 2,000-draw precision and clustered-lift bootstrap reproduction.
- Raw pooled 2022–2023 numerator/denominator and retention-median calculation.
- Nine-gate verification for each RB family.
- Direction, season, week, team, player, repeat, overlap, partial-policy, retention-outlier, opportunity, and denominator diagnostics.
- 216-cell equal-volume reconstruction and 648-cell comparator-selection replay.
- Full-alert frozen-rule compliance check.
- Ten temporal checks and nine-field outcome-label reconstruction.
- Source/config hash reconciliation.
- Executed audit notebook and repository tests, recorded separately in `VALIDATION_RESULTS.md`.
