# PropWar Role Validation - Fold 4 (Untouched 2024)

## Concise judgment

RB carry status: `FAILS_FOLD_4_POINT_GATES`. RB opportunity status: `FAILS_FOLD_4_POINT_GATES`. These are literal locked-gate outcomes; a failed gate remains a failure. Neither family is described as validated. WR and TE remain retired and were not evaluated on 2024.

## Frozen execution integrity

- Pre-Fold-4 checkpoint: `pre-fold-4-checkpoint` -> `603bd5159833e1ce11ca4ff261b0d88fd040ea73`
- Execution-package commit: `6446d4ef7fa554e20978c90fda6ddefbedafc4fa`
- Candidate SHA-256: `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7`
- Frozen candidate SHA-256: `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7`
- Frozen execution files: 15; every hash reverified before execution.
- Alert archive SHA-256: `9eba028998d20ba50a0616d7aa7ffa5237025d6b53593002be723675e137cb25`
- Fold 4 executed once: **yes**; 2025 results used: **no**; post-result redevelopment: **no**.

## File-access boundary

- `source_seasons_physically_available`: `[2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]`
- `source_seasons_physically_opened`: `[2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]`
- `seasons_admitted_to_feature_generation`: `[2024]`
- `seasons_admitted_to_alert_selection`: `[2024]`
- `seasons_admitted_to_outcome_evaluation`: `[2024]`

The storage layer physically opened multi-season files. Only 2024 rows entered features, partial-game classifications, alerts, or outcomes. Prior 2021-2023 archives entered cross-season reporting only.

## 2024 data audit

| rows | players | games | weeks | duplicate keys | required null cells | identity | quality | qualifying |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7,390 | 544 | 272 | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% |

Participation coverage is 100.0%; carry identity coverage is 100.0%; target identity population is 89.3%. All recorded participation and opportunity joins passed. Confirmed partial rows were excluded; suspected rows remained included in the primary policy.

## Active-family method results

| role_family | method | alerts | deduplicated_player_week_team_alerts | evaluable_alerts | persistent_alerts | precision | precision_ci_low | precision_ci_high | reversion_rate | median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | full_propwar | 48 | 48 | 35 | 22 | 62.9% | 45.7% | 77.1% | 20.0% | 66.7% |
| rb_carry_share | naive_spike | 48 | 48 | 35 | 14 | 40.0% | 25.7% | 57.1% | 32.5% | 37.3% |
| rb_carry_share | normal_game_trend | 48 | 48 | 35 | 20 | 57.1% | 40.0% | 74.3% | 19.0% | 64.6% |
| rb_carry_share | two_week_raw | 48 | 48 | 36 | 21 | 58.3% | 41.7% | 75.0% | 22.0% | 63.4% |
| rb_opportunity_share | full_propwar | 55 | 55 | 48 | 29 | 60.4% | 45.8% | 72.9% | 27.5% | 78.6% |
| rb_opportunity_share | naive_spike | 55 | 55 | 49 | 19 | 38.8% | 24.5% | 53.1% | 39.2% | 38.2% |
| rb_opportunity_share | normal_game_trend | 55 | 55 | 47 | 27 | 57.4% | 42.6% | 70.2% | 25.0% | 66.2% |
| rb_opportunity_share | two_week_raw | 55 | 55 | 48 | 30 | 62.5% | 47.9% | 75.0% | 25.5% | 66.4% |

## Frozen detector versus equal-volume naive

| role_family | full_alerts | full_evaluable_alerts | full_persistent_alerts | full_precision | precision_ci_low | precision_ci_high | naive_precision | precision_improvement | precision_improvement_ci_low | precision_improvement_ci_high | full_reversion_rate | naive_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | 48 | 35 | 22 | 62.9% | 45.7% | 77.1% | 40.0% | +22.9 pp | +5.5 pp | +41.4 pp | 20.0% | 32.5% | +12.5 pp | 66.7% |
| rb_opportunity_share | 55 | 48 | 29 | 60.4% | 45.8% | 72.9% | 38.8% | +21.6 pp | -1.2 pp | +43.9 pp | 27.5% | 39.2% | +11.8 pp | 78.6% |

All 108 family-week-policy cells had identical counts for naive spike, two-week raw trend, normal-game trend, and the frozen full detector.

## Deduplicated volume, overlap, and repeats

| partial_policy | method | family_alert_rows | deduplicated_player_week_team_alerts | duplicate_family_rows_removed | weekly_median | weekly_maximum | zero_alert_weeks |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PRIMARY_CONFIRMED_EXCLUDED | full_propwar | 103 | 79 | 24 | 5.0 | 11 | 5 |

| role_family | weekly_median | weekly_maximum | zero_alert_weeks | active_weeks | weekly_mean |
| --- | --- | --- | --- | --- | --- |
| rb_carry_share | 3.0 | 7 | 5 | 13 | 2.6666666666666665 |
| rb_opportunity_share | 3.0 | 8 | 5 | 13 | 3.055555555555556 |

| partial_policy | method | carry_alerts | opportunity_alerts | overlap_alerts | union_alerts | jaccard_overlap |
| --- | --- | --- | --- | --- | --- | --- |
| PRIMARY_CONFIRMED_EXCLUDED | full_propwar | 48 | 55 | 24 | 79 | 30.4% |

| role_family | alerts | repeat_alerts | repeat_players | repeat_rate |
| --- | --- | --- | --- | --- |
| rb_carry_share | 48 | 0 | 0 | 0.0% |
| rb_opportunity_share | 55 | 0 | 0 | 0.0% |

## Directional evaluation

| role_family | direction | alerts_full | evaluable_alerts_full | persistent_alerts_full | precision_full | precision_naive | naive_lift | reversion_rate_full | reversion_improvement | median_retention_full |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | decrease | 25 | 19 | 14 | 73.7% | 57.9% | +15.8 pp | 8.3% | +26.7 pp | 74.9% |
| rb_carry_share | increase | 23 | 16 | 8 | 50.0% | 18.8% | +31.2 pp | 33.3% | -3.3 pp | 41.8% |
| rb_opportunity_share | decrease | 33 | 27 | 19 | 70.4% | 48.3% | +22.1 pp | 20.7% | +13.8 pp | 84.7% |
| rb_opportunity_share | increase | 22 | 21 | 10 | 47.6% | 25.0% | +22.6 pp | 36.4% | +9.1 pp | 32.5% |

No direction-specific candidate or exclusion was created. Carry decreases remain a diagnostic subgroup only.

## Confirmed and suspected partial-game sensitivity

`PRIMARY_CONFIRMED_EXCLUDED` excludes confirmed cases and includes suspected cases. `ALL_INCLUDED` adds confirmed cases; `STRICT_SUSPECTED_EXCLUDED` removes both confirmed and suspected cases.

| partial_policy | role_family | full_alerts | full_evaluable_alerts | full_precision | precision_improvement | full_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL_INCLUDED | rb_carry_share | 49 | 36 | 61.1% | +19.4 pp | 19.6% | +12.1 pp | 63.6% |
| ALL_INCLUDED | rb_opportunity_share | 57 | 50 | 60.0% | +20.8 pp | 26.4% | +11.3 pp | 78.6% |
| PRIMARY_CONFIRMED_EXCLUDED | rb_carry_share | 48 | 35 | 62.9% | +22.9 pp | 20.0% | +12.5 pp | 66.7% |
| PRIMARY_CONFIRMED_EXCLUDED | rb_opportunity_share | 55 | 48 | 60.4% | +21.6 pp | 27.5% | +11.8 pp | 78.6% |
| STRICT_SUSPECTED_EXCLUDED | rb_carry_share | 48 | 35 | 60.0% | +25.7 pp | 25.0% | +6.7 pp | 62.2% |
| STRICT_SUSPECTED_EXCLUDED | rb_opportunity_share | 55 | 49 | 61.2% | +23.2 pp | 21.6% | +13.7 pp | 71.8% |

## Seasonal and subgroup stability

| role_family | dimension | segment | alerts | evaluable_alerts | precision | reversion_rate | median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | week_block | weeks_13_18 | 20 | 8 | 50.0% | 29.4% | 46.9% |
| rb_carry_share | week_block | weeks_1_6 | 4 | 4 | 75.0% | 0.0% | 108.4% |
| rb_carry_share | week_block | weeks_7_12 | 24 | 23 | 65.2% | 16.7% | 66.7% |
| rb_opportunity_share | week_block | weeks_13_18 | 19 | 12 | 50.0% | 40.0% | 45.5% |
| rb_opportunity_share | week_block | weeks_1_6 | 7 | 7 | 85.7% | 14.3% | 113.1% |
| rb_opportunity_share | week_block | weeks_7_12 | 29 | 29 | 58.6% | 24.1% | 68.1% |
| rb_carry_share | absolute_role_change | 0.20-0.249 | 21 | 13 | 61.5% | 26.3% | 80.1% |
| rb_carry_share | absolute_role_change | 0.25+ | 27 | 22 | 63.6% | 15.4% | 63.6% |
| rb_opportunity_share | absolute_role_change | 0.20-0.249 | 22 | 18 | 61.1% | 28.6% | 86.1% |
| rb_opportunity_share | absolute_role_change | 0.25+ | 33 | 30 | 60.0% | 26.7% | 70.0% |
| rb_carry_share | player_opportunity_count | 0-2 | 10 | 8 | 75.0% | 10.0% | 68.0% |
| rb_carry_share | player_opportunity_count | 10-14 | 13 | 9 | 44.4% | 54.5% | -7.5% |
| rb_carry_share | player_opportunity_count | 15+ | 12 | 9 | 44.4% | 0.0% | 28.1% |
| rb_carry_share | player_opportunity_count | 3-5 | 3 | 3 | 100.0% | 0.0% | 66.7% |
| rb_carry_share | player_opportunity_count | 6-9 | 10 | 6 | 83.3% | 20.0% | 91.1% |
| rb_opportunity_share | player_opportunity_count | 0-2 | 12 | 10 | 80.0% | 10.0% | 91.2% |
| rb_opportunity_share | player_opportunity_count | 10-14 | 11 | 8 | 62.5% | 40.0% | 99.4% |
| rb_opportunity_share | player_opportunity_count | 15+ | 15 | 14 | 50.0% | 26.7% | 49.4% |
| rb_opportunity_share | player_opportunity_count | 3-5 | 8 | 8 | 62.5% | 25.0% | 76.4% |
| rb_opportunity_share | player_opportunity_count | 6-9 | 9 | 8 | 50.0% | 37.5% | 48.3% |
| rb_carry_share | team_denominator | 16-20 | 9 | 8 | 62.5% | 33.3% | 58.2% |
| rb_carry_share | team_denominator | 21-25 | 21 | 12 | 66.7% | 21.1% | 73.9% |
| rb_carry_share | team_denominator | 26-30 | 9 | 6 | 50.0% | 12.5% | 36.1% |
| rb_carry_share | team_denominator | 31-35 | 8 | 8 | 75.0% | 12.5% | 79.8% |
| rb_carry_share | team_denominator | 36+ | 1 | 1 | 0.0% | 0.0% | 28.1% |
| rb_opportunity_share | team_denominator | 16-20 | 8 | 7 | 57.1% | 42.9% | 123.4% |
| rb_opportunity_share | team_denominator | 21-25 | 18 | 17 | 52.9% | 35.3% | 64.7% |
| rb_opportunity_share | team_denominator | 26-30 | 20 | 16 | 75.0% | 21.1% | 92.9% |
| rb_opportunity_share | team_denominator | 31-35 | 7 | 6 | 33.3% | 16.7% | 25.5% |
| rb_opportunity_share | team_denominator | 36+ | 2 | 2 | 100.0% | 0.0% | 87.1% |
| rb_carry_share | baseline_stability | high_gap_less_stable | 24 | 19 | 68.4% | 23.8% | 73.0% |
| rb_carry_share | baseline_stability | low_gap_more_stable | 24 | 16 | 56.2% | 16.7% | 61.2% |
| rb_opportunity_share | baseline_stability | high_gap_less_stable | 27 | 26 | 65.4% | 26.9% | 87.2% |
| rb_opportunity_share | baseline_stability | low_gap_more_stable | 28 | 22 | 54.5% | 28.0% | 66.4% |

The player/team detail is preserved in `subgroup_stability_2024.csv` and `concentration_entities_2024.csv`. Baseline stability is a descriptive median split of the pre-alert absolute recent-versus-season baseline gap; it does not affect selection.

| role_family | dimension | alerts | unique_entities | top_entity | top_entity_alerts | top_entity_share | hhi | effective_entities |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | player | 48 | 35 | 00-0036984 | 3 | 6.2% | 0.0338541666666666 | 29.53846153846154 |
| rb_carry_share | team | 48 | 21 | DEN | 5 | 10.4% | 0.0651041666666666 | 15.36 |
| rb_opportunity_share | player | 55 | 39 | 00-0036984 | 3 | 5.5% | 0.0314049586776859 | 31.842105263157908 |
| rb_opportunity_share | team | 55 | 22 | IND | 6 | 10.9% | 0.0611570247933884 | 16.351351351351354 |

### RB-family overlap dependence

| role_family | overlap_status | alerts | evaluable_alerts | evaluable_rate | persistent_alerts | precision | reversion_evaluable_alerts | immediate_reversions | reversion_rate | median_retention | mean_retention | unique_players | active_weeks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | family_only | 24 | 14 | 0.5833333333333334 | 9 | 64.3% | 21 | 6 | 28.6% | 77.2% | 0.7010275405123794 | 20 | 11 |
| rb_carry_share | overlapping_rb_family | 24 | 21 | 0.875 | 13 | 61.9% | 24 | 3 | 12.5% | 55.8% | 0.4788435396965406 | 20 | 11 |
| rb_opportunity_share | family_only | 31 | 27 | 0.8709677419354839 | 17 | 63.0% | 27 | 10 | 37.0% | 84.7% | 0.5903193972764428 | 26 | 12 |
| rb_opportunity_share | overlapping_rb_family | 24 | 21 | 0.875 | 12 | 57.1% | 24 | 4 | 16.7% | 68.1% | 0.5386930383852135 | 20 | 11 |

### Retention outlier diagnostics

| role_family | evaluable_retention_values | minimum | p05 | median | mean | trimmed_mean_10pct | clipped_0_1_mean | p95 | maximum |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | 35 | -0.5968211680978829 | -0.3930760469383446 | 0.6667472585550115 | 0.567717140022876 | 0.5833753452069139 | 0.5727119035410096 | 1.312225685891588 | 1.709745263917882 |
| rb_opportunity_share | 48 | -2.621448567942 | -0.4817221251873648 | 0.785663698417834 | 0.56773286526153 | 0.6393814388554955 | 0.596789978771695 | 1.3728121532825952 | 1.8976355421374471 |

No new exclusions were introduced from any subgroup, overlap, denominator, partial-game, or outlier finding.

## 2021-2024 direct comparison

| period | role_family | full_alerts | full_evaluable_alerts | full_precision | naive_precision | precision_improvement | full_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| redeveloped_2021 | rb_carry_share | 56 | 43 | 74.4% | 48.8% | +25.6 pp | 18.8% | +11.0 pp | 76.2% |
| redeveloped_2021 | rb_opportunity_share | 77 | 55 | 67.3% | 52.7% | +14.5 pp | 19.0% | +11.1 pp | 68.4% |
| untouched_2022 | rb_carry_share | 49 | 39 | 64.1% | 47.4% | +16.7 pp | 15.0% | +25.0 pp | 61.7% |
| untouched_2022 | rb_opportunity_share | 59 | 47 | 61.7% | 53.3% | +8.4 pp | 14.0% | +17.9 pp | 68.8% |
| untouched_2023 | rb_carry_share | 60 | 47 | 66.0% | 53.1% | +12.9 pp | 23.1% | +9.6 pp | 79.5% |
| untouched_2023 | rb_opportunity_share | 74 | 57 | 77.2% | 56.9% | +20.3 pp | 15.6% | +16.1 pp | 91.0% |
| untouched_2024 | rb_carry_share | 48 | 35 | 62.9% | 40.0% | +22.9 pp | 20.0% | +12.5 pp | 66.7% |
| untouched_2024 | rb_opportunity_share | 55 | 48 | 60.4% | 38.8% | +21.6 pp | 27.5% | +11.8 pp | 78.6% |

| period | season | role_family | archived_status | frozen_before_holdout | interpretation |
| --- | --- | --- | --- | --- | --- |
| redeveloped_2021 | 2021 | rb_carry_share | POINT_GATES_PASS | False | development diagnostic; not untouched |
| redeveloped_2021 | 2021 | rb_opportunity_share | POINT_GATES_PASS | False | development diagnostic; not untouched |
| untouched_2022 | 2022 | rb_carry_share | FAILS_FOLD_2_POINT_GATES | True | preserved archived Fold 2 decision |
| untouched_2022 | 2022 | rb_opportunity_share | FAILS_FOLD_2_POINT_GATES | True | preserved archived Fold 2 decision |
| untouched_2023 | 2023 | rb_carry_share | PASSES_FOLD_3_POINT_GATES | True | preserved archived Fold 3 decision |
| untouched_2023 | 2023 | rb_opportunity_share | FAILS_FOLD_3_POINT_GATES | True | preserved archived Fold 3 decision |
| untouched_2024 | 2024 | rb_carry_share | FAILS_FOLD_4_POINT_GATES | True | Fold 4 locked point-gate decision |
| untouched_2024 | 2024 | rb_opportunity_share | FAILS_FOLD_4_POINT_GATES | True | Fold 4 locked point-gate decision |

Every archived season status is preserved. The redeveloped 2021 row remains a development diagnostic, not an untouched holdout. A pooled result does not erase an individual failure.

## Pooled untouched results

### 2022-2023

| period | role_family | full_alerts | full_evaluable_alerts | full_precision | naive_precision | precision_improvement | precision_improvement_ci_low | precision_improvement_ci_high | full_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pooled_untouched_2022_2023 | rb_carry_share | 109 | 86 | 65.1% | 50.6% | +14.5 pp | +3.5 pp | +24.9 pp | 19.6% | +16.3 pp | 73.9% |
| pooled_untouched_2022_2023 | rb_opportunity_share | 133 | 104 | 70.2% | 55.3% | +14.9 pp | +2.4 pp | +26.1 pp | 14.9% | +16.9 pp | 79.4% |

### 2022-2024

| period | role_family | full_alerts | full_evaluable_alerts | full_precision | naive_precision | precision_improvement | precision_improvement_ci_low | precision_improvement_ci_high | full_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pooled_untouched_2022_2024 | rb_carry_share | 157 | 121 | 64.5% | 47.5% | +16.9 pp | +8.2 pp | +26.2 pp | 19.7% | +15.1 pp | 73.0% |
| pooled_untouched_2022_2024 | rb_opportunity_share | 188 | 152 | 67.1% | 50.0% | +17.1 pp | +6.1 pp | +28.3 pp | 18.8% | +15.4 pp | 79.4% |

Both pooled tables are calculated from concatenated raw alert rows and their raw numerators and denominators, never by averaging seasonal percentages.

## Locked Fold 4 gates

| role_family | gate | observed | threshold | passed |
| --- | --- | --- | --- | --- |
| rb_carry_share | min_holdout_alerts | 48 | >= 50 | False |
| rb_carry_share | min_persistence_precision | 62.9% | >= 0.6 | True |
| rb_carry_share | min_absolute_improvement_vs_naive | 22.9% | >= 0.1 | True |
| rb_carry_share | max_immediate_reversion_rate | 20.0% | <= 0.25 | True |
| rb_carry_share | min_reversion_improvement_vs_naive | 12.5% | >= 0.08 | True |
| rb_carry_share | min_median_retention | 66.7% | >= 0.5 | True |
| rb_carry_share | min_alerts_per_week | 2.6666666666666665 | >= 0.5 | True |
| rb_carry_share | direction_consistent_across_periods | True | all available period-direction lifts >= 0 | True |
| rb_carry_share | frozen_before_holdout | True | required | True |
| rb_opportunity_share | min_holdout_alerts | 55 | >= 50 | True |
| rb_opportunity_share | min_persistence_precision | 60.4% | >= 0.6 | True |
| rb_opportunity_share | min_absolute_improvement_vs_naive | 21.6% | >= 0.1 | True |
| rb_opportunity_share | max_immediate_reversion_rate | 27.5% | <= 0.25 | False |
| rb_opportunity_share | min_reversion_improvement_vs_naive | 11.8% | >= 0.08 | True |
| rb_opportunity_share | min_median_retention | 78.6% | >= 0.5 | True |
| rb_opportunity_share | min_alerts_per_week | 3.0555555555555554 | >= 0.5 | True |
| rb_opportunity_share | direction_consistent_across_periods | False | all available period-direction lifts >= 0 | False |
| rb_opportunity_share | frozen_before_holdout | True | required | True |

| role_family | candidate_disposition | fold4_candidate_status | failed_checks |
| --- | --- | --- | --- |
| rb_carry_share | PRIMARY_CANDIDATE | FAILS_FOLD_4_POINT_GATES | min_holdout_alerts |
| rb_opportunity_share | SHADOW_CANDIDATE | FAILS_FOLD_4_POINT_GATES | max_immediate_reversion_rate \| direction_consistent_across_periods |
| wr_target_share | RETIRED_DESCRIPTIVE_ONLY | NOT_APPLICABLE_RETIRED | retired_before_fold4 |
| te_target_share | RETIRED_DESCRIPTIVE_ONLY | NOT_APPLICABLE_RETIRED | retired_before_fold4 |

## Exact recommendations

| role_family | fold4_status | recommendation |
| --- | --- | --- |
| rb_carry_share | FAILS_FOLD_4_POINT_GATES | CONTINUE_SHADOW_ONLY |
| rb_opportunity_share | FAILS_FOLD_4_POINT_GATES | CONTINUE_SHADOW_ONLY_WITHOUT_HOLDOUT_CLAIM |
| wr_target_share | NOT_APPLICABLE_RETIRED | REMAIN_RETIRED |
| te_target_share | NOT_APPLICABLE_RETIRED | REMAIN_RETIRED |

## Uncertainty and limitations

- This is a historical development-fold test, not final historical or prospective validation.
- Point gates govern the locked decision; confidence intervals govern wording strength and are not used to waive or move a gate.
- Late-season alerts can lack two future qualifying games and therefore reduce outcome evaluability.
- Subgroup samples can be small and are descriptive diagnostics only.
- Multi-season source files were physically scanned, although only 2024 values were admitted to the Fold 4 calculation.
- Source extracts can be revised upstream; exact source hashes and materialized 2024 explicit-injury inputs are archived.
- No dashboard, detector rule, threshold, release gate, 2025 result, merge, push, or deployment entered this task.
