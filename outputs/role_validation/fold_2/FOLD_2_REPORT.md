# PropWar Role Validation — Fold 2 (Untouched 2022)

## Concise judgment

RB carry produced encouraging point estimates but failed the locked 50-alert gate with 49 alerts; its improvement interval includes zero and 2022 precision fell 10.3 points from redeveloped 2021. RB opportunity failed the 10-point naive-lift and direction-consistency checks. WR failed precision, retention, evidence-volume, and direction-consistency checks. TE emitted only four alerts and is insufficient. No family passes Fold 2 and none is validated.

This was a single controlled execution of the candidate frozen at `bdff056fa625eef76152e1b9f3ef0e88fda2bbab`. No 2023–2025 result was read, no detector rule was changed, and no family is presented as validated.

## Frozen-configuration integrity

- Candidate SHA-256: `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7`
- Frozen-copy SHA-256: `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7`
- Pre-Fold-2 tag: `role-change-validation-v1-pre-fold2-checkpoint` → `bdff056fa625eef76152e1b9f3ef0e88fda2bbab`
- Exact semantic match to the Fold 1 report: **yes**
- Protected release-gate SHA-256: `e6a64afa9dcec76cf2c0ef582640c575f0f74e6f799427ff4f114699b97a086d`
- Protocol and locked-decision hashes: unchanged
- Execution lock completed: **yes**
- Alert archive SHA-256: `725e4bbc73028819dbcc754012aa49888a77826cb15ceac12f43647d1248508d`

The alert is emitted after the frozen confirmation window completes. Baseline weeks end strictly before confirmation starts; both outcome games occur strictly after the alert week. This is the protocol’s `B`, `D`, then future `F` ordering.

## 2022 data audit

| canonical rows | players | played games | weeks | duplicate keys | required null cells | identity coverage | quality pass | qualifying |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 7,478 | 555 | 271 | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% |

Source evidence:

- PBP and schedule both contain 271 played regular-season games across all 18 weeks.
- Participation play coverage is 100.0%; carry-ID coverage is 100.0%.
- Target-player ID population is 89.6% across pass attempts; target opportunities themselves require a receiver ID before entering numerator or denominator.
- Opportunity-to-identity and participating-player-to-identity joins are both 100% (41,719/41,719).
- Explicit PBP injury mentions: 872; resolved: 831 (95.3%).
- Confirmed partial family rows: 19; suspected rows retained in primary: 93.
- Every team-game has a trigger timestamp. The 32 null next-game boundaries are exactly one final regular-season game per team.

## Family and method results

| role_family | method | alerts | deduplicated_player_week_team_alerts | evaluable_alerts | precision | precision_ci_low | precision_ci_high | reversion_rate | median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | full_propwar | 49 | 49 | 39 | 64.1% | 48.7% | 79.5% | 15.0% | 61.7% |
| rb_carry_share | naive_spike | 49 | 49 | 38 | 47.4% | 31.6% | 63.2% | 40.0% | 38.8% |
| rb_carry_share | normal_game_trend | 49 | 49 | 38 | 57.9% | 42.1% | 73.7% | 17.5% | 56.4% |
| rb_carry_share | two_week_raw | 49 | 49 | 36 | 55.6% | 38.9% | 72.2% | 23.1% | 53.8% |
| rb_opportunity_share | full_propwar | 59 | 59 | 47 | 61.7% | 46.8% | 74.5% | 14.0% | 68.8% |
| rb_opportunity_share | naive_spike | 59 | 59 | 45 | 53.3% | 37.8% | 66.7% | 31.9% | 56.2% |
| rb_opportunity_share | normal_game_trend | 59 | 59 | 44 | 59.1% | 45.5% | 72.7% | 25.0% | 60.6% |
| rb_opportunity_share | two_week_raw | 59 | 59 | 45 | 60.0% | 44.4% | 73.3% | 22.9% | 55.1% |
| te_target_share | full_propwar | 4 | 4 | 3 | 0.0% | 0.0% | 0.0% | 66.7% | -5.0% |
| te_target_share | naive_spike | 4 | 4 | 3 | 33.3% | 0.0% | 100.0% | 66.7% | -13.0% |
| te_target_share | normal_game_trend | 4 | 4 | 3 | 33.3% | 0.0% | 100.0% | 66.7% | 3.0% |
| te_target_share | two_week_raw | 4 | 4 | 3 | 33.3% | 0.0% | 100.0% | 66.7% | 3.2% |
| wr_target_share | full_propwar | 30 | 30 | 22 | 36.4% | 18.2% | 59.1% | 25.0% | 44.4% |
| wr_target_share | naive_spike | 30 | 30 | 22 | 9.1% | 0.0% | 22.7% | 51.9% | 23.3% |
| wr_target_share | normal_game_trend | 30 | 30 | 23 | 39.1% | 17.4% | 60.9% | 28.6% | 45.1% |
| wr_target_share | two_week_raw | 30 | 30 | 23 | 39.1% | 21.7% | 60.9% | 39.3% | 43.7% |

## Frozen detector versus equal-volume naive

| role_family | full_alerts | full_evaluable_alerts | full_precision | naive_precision | precision_improvement | precision_improvement_ci_low | precision_improvement_ci_high | full_reversion_rate | naive_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | 49 | 39 | 64.1% | 47.4% | +16.7 pp | -0.8 pp | +33.2 pp | 15.0% | 40.0% | +25.0 pp | 61.7% |
| rb_opportunity_share | 59 | 47 | 61.7% | 53.3% | +8.4 pp | -12.4 pp | +28.1 pp | 14.0% | 31.9% | +17.9 pp | 68.8% |
| te_target_share | 4 | 3 | 0.0% | 33.3% | -33.3 pp | -100.0 pp | +0.0 pp | 66.7% | 66.7% | +0.0 pp | -5.0% |
| wr_target_share | 30 | 22 | 36.4% | 9.1% | +27.3 pp | -5.8 pp | +51.9 pp | 25.0% | 51.9% | +26.9 pp | 44.4% |

Every one of the 216 family-week-policy cells contains all four methods at exactly equal volume, including zero-alert weeks.

## Deduplicated feed and overlap

The primary full detector produced 142 family rows and 109 deduplicated player-week-team alerts. The weekly deduplicated median was 7.0, maximum 13, with 5 zero-alert weeks.

| role_family | weekly_median | weekly_maximum | zero_alert_weeks | active_weeks | weekly_mean |
| --- | --- | --- | --- | --- | --- |
| rb_carry_share | 2.5 | 7 | 5 | 13 | 2.7222222222222223 |
| rb_opportunity_share | 3.5 | 9 | 6 | 12 | 3.2777777777777777 |
| te_target_share | 0.0 | 1 | 14 | 4 | 0.2222222222222222 |
| wr_target_share | 1.0 | 5 | 6 | 12 | 1.6666666666666667 |

| partial_policy | method | carry_alerts | opportunity_alerts | overlap_alerts | union_alerts | jaccard_overlap |
| --- | --- | --- | --- | --- | --- | --- |
| PRIMARY_CONFIRMED_EXCLUDED | full_propwar | 49 | 59 | 33 | 75 | 44.0% |

| role_family | alerts | repeat_alerts | repeat_players | repeat_rate |
| --- | --- | --- | --- | --- |
| rb_carry_share | 49 | 0 | 0 | 0.0% |
| rb_opportunity_share | 59 | 0 | 0 | 0.0% |
| te_target_share | 4 | 0 | 0 | 0.0% |
| wr_target_share | 30 | 0 | 0 | 0.0% |

The frozen direction-sensitive cooldown eliminated all literal consecutive-week repeats from the emitted full-detector feed.

## Increase/decrease results

| role_family | direction | alerts | evaluable_alerts | precision | reversion_rate | median_retention |
| --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | decrease | 27 | 21 | 47.6% | 23.8% | 49.6% |
| rb_carry_share | increase | 22 | 18 | 83.3% | 5.3% | 79.1% |
| rb_opportunity_share | decrease | 32 | 24 | 54.2% | 18.5% | 59.5% |
| rb_opportunity_share | increase | 27 | 23 | 69.6% | 8.7% | 84.5% |
| te_target_share | decrease | 2 | 2 | 0.0% | 50.0% | -7.7% |
| te_target_share | increase | 2 | 1 | 0.0% | 100.0% | 18.8% |
| wr_target_share | decrease | 10 | 6 | 66.7% | 11.1% | 57.6% |
| wr_target_share | increase | 20 | 16 | 25.0% | 31.6% | 38.3% |

RB carry’s increase side remained strong, while the decrease side fell below the 60% precision gate. RB opportunity was also stronger on increases. WR flipped from a strong 2021 increase result to 25% precision on 2022 increases.

## Early/middle/late stability

| role_family | week_block | alerts | evaluable_alerts | precision | reversion_rate | median_retention |
| --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | weeks_13_18 | 19 | 11 | 63.6% | 16.7% | 74.2% |
| rb_carry_share | weeks_1_6 | 6 | 5 | 60.0% | 0.0% | 55.1% |
| rb_carry_share | weeks_7_12 | 24 | 23 | 65.2% | 17.4% | 61.7% |
| rb_opportunity_share | weeks_13_18 | 26 | 16 | 50.0% | 29.4% | 56.7% |
| rb_opportunity_share | weeks_1_6 | 6 | 6 | 83.3% | 0.0% | 65.4% |
| rb_opportunity_share | weeks_7_12 | 27 | 25 | 64.0% | 7.4% | 84.5% |
| te_target_share | weeks_13_18 | 2 | 1 | 0.0% | 100.0% | 18.8% |
| te_target_share | weeks_7_12 | 2 | 2 | 0.0% | 50.0% | -7.7% |
| wr_target_share | weeks_13_18 | 19 | 12 | 41.7% | 23.5% | 45.0% |
| wr_target_share | weeks_1_6 | 1 | 1 | 100.0% | 0.0% | 70.8% |
| wr_target_share | weeks_7_12 | 10 | 9 | 22.2% | 30.0% | 39.1% |

Weeks 1–5 have no alerts by construction because the same-season four-game baseline must accrue. Small early and late block samples make week-stability claims uncertain.

## Partial-game sensitivity

`PRIMARY_CONFIRMED_EXCLUDED` excludes confirmed focal partial games and includes suspected cases. `ALL_INCLUDED` is the confirmed-exclusion sensitivity; `STRICT_SUSPECTED_EXCLUDED` additionally excludes suspected cases.

| partial_policy | role_family | full_alerts | full_evaluable_alerts | full_precision | precision_improvement | precision_improvement_ci_low | precision_improvement_ci_high | full_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL_INCLUDED | rb_carry_share | 49 | 39 | 64.1% | +18.2 pp | +0.4 pp | +34.1 pp | 17.1% | +24.0 pp | 61.7% |
| ALL_INCLUDED | rb_opportunity_share | 59 | 47 | 61.7% | +7.2 pp | -13.9 pp | +27.9 pp | 14.0% | +18.6 pp | 68.8% |
| ALL_INCLUDED | te_target_share | 4 | 3 | 0.0% | -33.3 pp | -100.0 pp | +0.0 pp | 66.7% | +0.0 pp | -5.0% |
| ALL_INCLUDED | wr_target_share | 30 | 22 | 36.4% | +26.8 pp | -9.0 pp | +51.7 pp | 25.0% | +25.0 pp | 44.4% |
| PRIMARY_CONFIRMED_EXCLUDED | rb_carry_share | 49 | 39 | 64.1% | +16.7 pp | -0.8 pp | +33.2 pp | 15.0% | +25.0 pp | 61.7% |
| PRIMARY_CONFIRMED_EXCLUDED | rb_opportunity_share | 59 | 47 | 61.7% | +8.4 pp | -12.4 pp | +28.1 pp | 14.0% | +17.9 pp | 68.8% |
| PRIMARY_CONFIRMED_EXCLUDED | te_target_share | 4 | 3 | 0.0% | -33.3 pp | -100.0 pp | +0.0 pp | 66.7% | +0.0 pp | -5.0% |
| PRIMARY_CONFIRMED_EXCLUDED | wr_target_share | 30 | 22 | 36.4% | +27.3 pp | -5.8 pp | +51.9 pp | 25.0% | +26.9 pp | 44.4% |
| STRICT_SUSPECTED_EXCLUDED | rb_carry_share | 40 | 31 | 71.0% | +7.3 pp | -15.1 pp | +32.2 pp | 9.4% | +20.0 pp | 73.6% |
| STRICT_SUSPECTED_EXCLUDED | rb_opportunity_share | 48 | 37 | 75.7% | +11.8 pp | -6.4 pp | +28.5 pp | 7.3% | +20.2 pp | 78.4% |
| STRICT_SUSPECTED_EXCLUDED | te_target_share | 4 | 3 | 0.0% | -33.3 pp | -100.0 pp | +0.0 pp | 66.7% | +0.0 pp | -5.0% |
| STRICT_SUSPECTED_EXCLUDED | wr_target_share | 27 | 17 | 41.2% | +35.9 pp | +0.7 pp | +63.6 pp | 17.4% | +39.1 pp | 45.1% |

The qualitative Fold 2 decision does not change under either sensitivity. Excluding suspected games materially reduces RB sample sizes and is not the primary policy.

## 2021 redevelopment versus untouched 2022

| role_family | development_2021_full_alerts | untouched_2022_full_alerts | development_2021_full_precision | untouched_2022_full_precision | delta_2022_minus_2021_full_precision | development_2021_precision_improvement | untouched_2022_precision_improvement | delta_2022_minus_2021_precision_improvement | development_2021_full_reversion_rate | untouched_2022_full_reversion_rate | development_2021_full_median_retention | untouched_2022_full_median_retention | generalization_classification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | 56 | 49 | 74.4% | 64.1% | -10.3 pp | +25.6 pp | +16.7 pp | -8.9 pp | 18.8% | 15.0% | 76.2% | 61.7% | MATERIAL_DETERIORATION |
| rb_opportunity_share | 77 | 59 | 67.3% | 61.7% | -5.6 pp | +14.5 pp | +8.4 pp | -6.2 pp | 19.0% | 14.0% | 68.4% | 68.8% | STABLE_GENERALIZATION |
| te_target_share | 4 | 4 | 50.0% | 0.0% | -50.0 pp | +50.0 pp | -33.3 pp | -83.3 pp | 50.0% | 66.7% | -14.1% | -5.0% | INSUFFICIENT_SAMPLE |
| wr_target_share | 26 | 30 | 56.2% | 36.4% | -19.9 pp | +38.6 pp | +27.3 pp | -11.3 pp | 36.4% | 25.0% | 55.1% | 44.4% | INSUFFICIENT_SAMPLE |

Descriptive classification criteria, frozen in the execution code before reading outcomes:

- `INSUFFICIENT_SAMPLE`: fewer than 25 evaluable 2022 full-detector alerts.
- `MATERIAL_DETERIORATION`: otherwise, precision or naive lift declines by at least 10 points, reversion rises by at least 10 points, retention falls by at least 20 points, or 2022 naive lift becomes negative.
- `STABLE_GENERALIZATION`: otherwise, precision and lift changes remain within ±10 points, reversion rises by less than 10 points, retention falls by less than 20 points, and naive lift remains non-negative.
- `MIXED_OR_UNCERTAIN`: all remaining cases.

RB carry is mechanically classified `MATERIAL_DETERIORATION` because precision declined 10.3 points, just beyond the descriptive cutoff. This does not mean it failed badly: all performance point checks passed, but the family missed the locked alert-count gate by one and its improvement CI includes zero. The result is encouraging repeated historical evidence, not a Fold 2 pass.

## Direction-level generalization

| role_family | direction | alerts_full_2021 | evaluable_alerts_full_2021 | precision_full_2021 | reversion_rate_full_2021 | median_retention_full_2021 | alerts_naive_2021 | evaluable_alerts_naive_2021 | precision_naive_2021 | reversion_rate_naive_2021 | median_retention_naive_2021 | precision_improvement_2021 | alerts_full_2022 | evaluable_alerts_full_2022 | precision_full_2022 | reversion_rate_full_2022 | median_retention_full_2022 | alerts_naive_2022 | evaluable_alerts_naive_2022 | precision_naive_2022 | reversion_rate_naive_2022 | median_retention_naive_2022 | precision_improvement_2022 | delta_2022_minus_2021_alerts_full | delta_2022_minus_2021_evaluable_alerts_full | delta_2022_minus_2021_precision_full | delta_2022_minus_2021_precision_improvement | delta_2022_minus_2021_reversion_rate_full | delta_2022_minus_2021_median_retention_full |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | decrease | 24 | 19 | 0.7894736842105263 | 0.1578947368421052 | 0.864067665622978 | 27.0 | 17.0 | 0.5882352941176471 | 0.2 | 0.7738067559039428 | 0.20123839009287925 | 27 | 21 | 0.4761904761904761 | 0.238095238095238 | 0.4956928918274689 | 24.0 | 18.0 | 0.4444444444444444 | 0.4210526315789473 | 0.2776508886483156 | 0.03174603174603169 | 3 | 2 | -0.3132832080200502 | -0.16949235834684756 | 0.0802005012531328 | -0.3683747737955091 |
| rb_carry_share | increase | 32 | 24 | 0.7083333333333334 | 0.2068965517241379 | 0.7381735103696704 | 29.0 | 24.0 | 0.4166666666666667 | 0.3703703703703703 | 0.3188501196461667 | 0.2916666666666667 | 22 | 18 | 0.8333333333333334 | 0.0526315789473684 | 0.7912462685975917 | 25.0 | 20.0 | 0.5 | 0.3809523809523809 | 0.4621254652578277 | 0.33333333333333337 | -10 | -6 | 0.125 | 0.041666666666666685 | -0.1542649727767695 | 0.053072758227921346 |
| rb_opportunity_share | decrease | 33 | 22 | 0.6363636363636364 | 0.1153846153846153 | 0.6332221736919412 | 34.0 | 23.0 | 0.6521739130434783 | 0.1481481481481481 | 0.8021136577965476 | -0.015810276679841917 | 32 | 24 | 0.5416666666666666 | 0.1851851851851851 | 0.5950907424338369 | 32.0 | 23.0 | 0.4347826086956521 | 0.4 | 0.2737322467101264 | 0.10688405797101452 | -1 | 2 | -0.09469696969696972 | 0.12269433465085644 | 0.0698005698005698 | -0.038131431258104365 |
| rb_opportunity_share | increase | 44 | 33 | 0.696969696969697 | 0.2432432432432432 | 0.7151350012385436 | 43.0 | 32.0 | 0.4375 | 0.4166666666666667 | 0.385041326665934 | 0.259469696969697 | 27 | 23 | 0.6956521739130435 | 0.0869565217391304 | 0.8445708464215979 | 27.0 | 22.0 | 0.6363636363636364 | 0.2272727272727272 | 0.612590714247125 | 0.059288537549407105 | -17 | -10 | -0.0013175230566535578 | -0.2001811594202899 | -0.1562867215041128 | 0.1294358451830543 |
| te_target_share | decrease | 2 | 0 | — | — | — | — | — | — | — | — | — | 2 | 2 | 0.0 | 0.5 | -0.0769514859827821 | 2.0 | 1.0 | 0.0 | 1.0 | -0.3812292304535943 | 0.0 | 0 | 2 | — | — | — | — |
| te_target_share | increase | 2 | 2 | 0.5 | 0.5 | -0.1413190347883313 | 4.0 | 2.0 | 0.0 | 0.5 | -0.1189919073256889 | 0.5 | 2 | 1 | 0.0 | 1.0 | 0.1875277981207959 | 2.0 | 2.0 | 0.5 | 0.5 | 0.2274326829821243 | -0.5 | 0 | -1 | -0.5 | -1.0 | 0.5 | 0.3288468329091272 |
| wr_target_share | decrease | 9 | 6 | 0.1666666666666666 | 0.5714285714285714 | 0.2877717383340599 | 5.0 | 4.0 | 0.25 | 0.5 | 0.0798499808721402 | -0.0833333333333334 | 10 | 6 | 0.6666666666666666 | 0.1111111111111111 | 0.5762258290024761 | 10.0 | 5.0 | 0.0 | 0.6666666666666666 | 0.2317788333684858 | 0.6666666666666666 | 1 | 0 | 0.5 | 0.75 | -0.4603174603174603 | 0.2884540906684162 |
| wr_target_share | increase | 17 | 10 | 0.8 | 0.2666666666666666 | 0.7505574683301929 | 21.0 | 13.0 | 0.1538461538461538 | 0.7222222222222222 | 0.0822879292051455 | 0.6461538461538463 | 20 | 16 | 0.25 | 0.3157894736842105 | 0.3830318582932053 | 20.0 | 17.0 | 0.1176470588235294 | 0.4444444444444444 | 0.2440120730080184 | 0.13235294117647062 | 3 | 6 | -0.55 | -0.5138009049773757 | 0.0491228070175439 | -0.3675256100369876 |

## Locked release-gate judgment

| role_family | status | alerts | evaluable_alerts | precision | precision_improvement | reversion_rate | reversion_improvement | median_retention | failed_checks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | FAILS_FOLD_2_POINT_GATES | 49 | 39 | 64.1% | +16.7 pp | 15.0% | +25.0 pp | 61.7% | min_holdout_alerts |
| rb_opportunity_share | FAILS_FOLD_2_POINT_GATES | 59 | 47 | 61.7% | +8.4 pp | 14.0% | +17.9 pp | 68.8% | min_absolute_improvement_vs_naive \| direction_consistent_across_periods |
| wr_target_share | FAILS_FOLD_2_POINT_GATES | 30 | 22 | 36.4% | +27.3 pp | 25.0% | +26.9 pp | 44.4% | min_holdout_alerts \| min_persistence_precision \| min_median_retention \| direction_consistent_across_periods |
| te_target_share | INSUFFICIENT_EVIDENCE | 4 | 3 | 0.0% | -33.3 pp | 66.7% | +0.0 pp | -5.0% | min_holdout_alerts \| min_persistence_precision \| min_absolute_improvement_vs_naive \| max_immediate_reversion_rate \| min_reversion_improvement_vs_naive \| min_median_retention \| min_alerts_per_week \| direction_consistent_across_periods |

The direction-consistency check requires every available 2021/2022 increase/decrease comparison to have full-detector precision at least as high as its equal-volume naive comparator. This operationalizes—without changing—the protocol’s required direction consistency across periods.

Family statuses:

- `rb_carry_share`: `FAILS_FOLD_2_POINT_GATES`
- `rb_opportunity_share`: `FAILS_FOLD_2_POINT_GATES`
- `wr_target_share`: `FAILS_FOLD_2_POINT_GATES`
- `te_target_share`: `INSUFFICIENT_EVIDENCE`

No confidence interval is used to turn a failed point gate into a pass. Conversely, positive point estimates with intervals crossing zero remain explicitly uncertain.

## Recommended next action

| role_family | next_action | reason |
| --- | --- | --- |
| rb_carry_share | Keep in shadow evaluation unchanged | All performance point checks passed, but only 49 alerts and the lift CI includes zero; it cannot advance. |
| rb_opportunity_share | Keep in shadow evaluation unchanged | Stable point performance, but naive lift was 8.4 pp and direction consistency failed. |
| wr_target_share | Retire the family from the automated detector | Shadow family failed precision, retention, sample, and direction-consistency checks. |
| te_target_share | Retire the family from the automated detector | Only four alerts in both 2021 and 2022; 2022 had zero persistent alerts among three evaluable cases. |

No replacement candidate was created. Any later redevelopment using these results means 2022 can no longer be an untouched test for that revised candidate.

## Limitations

- Fold 2 is a development-fold test, not the locked 2025 final holdout or 2026 prospective confirmation.
- RB carry has only 39 evaluable alerts and its lift CI is -0.8 pp to +33.2 pp.
- RB opportunity’s 8.4-point naive improvement misses the locked 10-point gate; its CI includes zero.
- WR and TE were shadow-only before execution and remain unsupported for automated claims.
- Historical nflverse extracts can be revised upstream; input hashes are recorded for this run.
- The 89.6% receiver-ID field is measured across pass attempts, which include plays with no target; target-share opportunities require a resolved receiver.
- No public-dashboard behavior was tested or changed because the dashboard was explicitly out of scope.
