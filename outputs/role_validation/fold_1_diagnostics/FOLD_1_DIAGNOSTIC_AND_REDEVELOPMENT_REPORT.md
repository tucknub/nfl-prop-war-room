# Fold 1 Detector Diagnostic and Redevelopment Report

## TL;DR

The original detector failed Fold 1 and remains failed. Duplicate RB family alerts inflated the public-facing count, but deduplication still leaves genuinely excessive candidate generation. The recommended symmetric-delta rules materially reduce volume and improve the 2018–2021 diagnostic point estimates, especially for RB carry share. They are recommended only as a candidate for the untouched 2022 test; this report does not claim that the detector works, is validated, or is release-ready.

Checkpoint `00d6085a55c60147e0ace46c847460ef5708e968` is preserved by tag `role-change-validation-v1-fold1-checkpoint`. Fold 2 was not executed, no post-2021 result entered this analysis, and the locked release gates were not changed.

## Integrity contract

| constraint                    | result                                 |
| ----------------------------- | -------------------------------------- |
| Seasons used                  | 2018–2021 only                         |
| Development / diagnostic test | 2018–2020 / 2021                       |
| Fold 2                        | not executed                           |
| Post-2021 results             | not used                               |
| Release gates                 | unchanged; diagnostic application only |
| Public dashboard              | outside this work and not staged       |

## Canonical data audit

| season | canonical_rows | unique_players | duplicate_key_rows | required_field_null_cells | quality_pass_rate | identity_resolved_rate | confirmed_partial_family_rows | suspected_partial_family_rows |
| ------ | -------------- | -------------- | ------------------ | ------------------------- | ----------------- | ---------------------- | ----------------------------- | ----------------------------- |
| 2018   | 6777           | 526            | 0                  | 0                         | 96.7%             | 100.0%                 | 16                            | 77                            |
| 2019   | 6816           | 529            | 0                  | 0                         | 97.2%             | 100.0%                 | 23                            | 67                            |
| 2020   | 7134           | 557            | 0                  | 0                         | 100.0%            | 100.0%                 | 23                            | 75                            |
| 2021   | 7472           | 587            | 0                  | 0                         | 100.0%            | 100.0%                 | 34                            | 79                            |

The scoped canonical table contains 28,199 family rows. Required detector fields have 0 null rows, and the canonical key has 0 duplicate rows. Carry share, RB opportunity share, WR target share, and TE target share are calculated from game-level player opportunities divided by same-team, same-game denominators. Normal-game usage is computed before weekly aggregation; baselines end before confirmation windows and reset each season, preventing future or cross-season leakage.

Player identity is GSIS-native for opportunity rows. The audit distinguishes unresolved participation from confirmed identity; no unresolved identity is allowed to pass the canonical quality gate. Confirmed partial-game evidence requires an explicit PBP injury mention, resolved identity, no later offensive appearance, at least five focal-team offensive plays after the injury, and a conservative game-end timestamp before the current team’s next scheduled game.

### Partial-game evidence coverage

| parsed_injury_mentions | resolved_injury_mentions | unresolved_injury_mentions | resolution_rate    | ambiguous_roster_universe_keys_excluded | participation_team_games | participation_coverage_below_099 | canonical_rows | confirmed_partial_rows | suspected_partial_rows | statistical_corroboration_rows_pre_promotion | suspected_corroborated_status_rows | canonical_team_games | trigger_timestamp_missing_team_games | next_boundary_missing_team_games |
| ---------------------- | ------------------------ | -------------------------- | ------------------ | --------------------------------------- | ------------------------ | -------------------------------- | -------------- | ---------------------- | ---------------------- | -------------------------------------------- | ---------------------------------- | -------------------- | ------------------------------------ | -------------------------------- |
| 3187.0                 | 2929.0                   | 258.0                      | 0.9190461248823344 | 19033.0                                 | 2080.0                   | 2.0                              | 28199.0        | 96.0                   | 298.0                  | 262.0                                        | 184.0                              | 2080.0               | 0.0                                  | 128.0                            |

| season | partial_game_status    | canonical_family_rows | distinct_player_games |
| ------ | ---------------------- | --------------------- | --------------------- |
| 2018   | confirmed              | 16                    | 11                    |
| 2018   | none                   | 6684                  | 5236                  |
| 2018   | suspected_corroborated | 44                    | 38                    |
| 2018   | suspected_statistical  | 33                    | 25                    |
| 2019   | confirmed              | 23                    | 16                    |
| 2019   | none                   | 6726                  | 5239                  |
| 2019   | suspected_corroborated | 45                    | 36                    |
| 2019   | suspected_statistical  | 22                    | 16                    |
| 2020   | confirmed              | 23                    | 19                    |
| 2020   | none                   | 7036                  | 5483                  |
| 2020   | suspected_corroborated | 49                    | 40                    |
| 2020   | suspected_statistical  | 26                    | 23                    |
| 2021   | confirmed              | 34                    | 28                    |
| 2021   | none                   | 7359                  | 5805                  |
| 2021   | suspected_corroborated | 46                    | 37                    |
| 2021   | suspected_statistical  | 33                    | 28                    |

Statistical usage collapse alone is labeled suspected and remains included in the primary analysis. Postgame injury-report evidence may corroborate suspicion but cannot independently create a confirmed exclusion.

## Original Fold 1 diagnosis

The checkpoint emitted 717 family-alert rows but only 489 unique player-week-team feed items. Deduplication removed 228 rows (31.8%).

| RB carry alerts | RB opportunity alerts | overlap | Jaccard | direction conflicts |
| --------------- | --------------------- | ------- | ------- | ------------------- |
| 273             | 324                   | 228     | 61.8%   | 0                   |

| grain                       | alerts | repeat_alerts | repeat_rate | players_with_repeat |
| --------------------------- | ------ | ------------- | ----------- | ------------------- |
| deduplicated_player_week    | 489    | 151           | 30.9%       | 70                  |
| family_player_week          | 717    | 219           | 30.5%       | 69                  |
| family:rb_carry_share       | 273    | 90            | 33.0%       | 43                  |
| family:rb_opportunity_share | 324    | 113           | 34.9%       | 50                  |
| family:te_target_share      | 35     | 6             | 17.1%       | 6                   |
| family:wr_target_share      | 85     | 10            | 11.8%       | 9                   |

The original family-row median was 38.0 per week; deduplication reduced it to 26.0, still above the 15-alert target ceiling in 18/18 weeks. The 38-alert median was inflated by duplicate RB families, but the 26-alert deduplicated median proves excessive candidate generation remained.

### Raw spike, trend, and full-detector comparison

| method            | alerts | evaluable_alerts | precision | reversion_rate | median_retention |
| ----------------- | ------ | ---------------- | --------- | -------------- | ---------------- |
| full_propwar      | 717    | 562              | 54.8%     | 32.4%          | 58.7%            |
| naive_spike       | 717    | 565              | 47.3%     | 36.3%          | 45.3%            |
| normal_game_trend | 717    | 562              | 54.1%     | 33.3%          | 56.8%            |
| two_week_raw      | 717    | 566              | 53.4%     | 33.6%          | 56.2%            |

| role_family          | alerts | evaluable_alerts | reversion_rate | median_retention | precision (95% CI)  |
| -------------------- | ------ | ---------------- | -------------- | ---------------- | ------------------- |
| rb_carry_share       | 273    | 222              | 28.2%          | 65.7%            | 57.2% (50.5%–63.5%) |
| rb_opportunity_share | 324    | 256              | 30.1%          | 64.3%            | 58.6% (52.3%–64.8%) |
| te_target_share      | 35     | 25               | 50.0%          | 16.6%            | 20.0% (4.0%–36.0%)  |
| wr_target_share      | 85     | 59               | 47.3%          | 40.0%            | 44.1% (30.5%–57.6%) |

The full detector selected 705 of the same 717 family alerts as the normal-game trend (96.7% Jaccard). Its aggregate point-estimate gain over normal-game trend was only about 0.7 percentage points of precision and 0.9 points of reversion reduction.

### Requested original breakdowns

#### Role Family

| segment              | alerts | evaluable_alerts | precision | reversion_evaluable_alerts | reversion_rate | median_retention |
| -------------------- | ------ | ---------------- | --------- | -------------------------- | -------------- | ---------------- |
| rb_carry_share       | 273    | 222              | 57.2%     | 238                        | 28.2%          | 65.7%            |
| rb_opportunity_share | 324    | 256              | 58.6%     | 282                        | 30.1%          | 64.3%            |
| te_target_share      | 35     | 25               | 20.0%     | 32                         | 50.0%          | 16.6%            |
| wr_target_share      | 85     | 59               | 44.1%     | 74                         | 47.3%          | 40.0%            |

#### Direction

| segment  | alerts | evaluable_alerts | precision | reversion_evaluable_alerts | reversion_rate | median_retention |
| -------- | ------ | ---------------- | --------- | -------------------------- | -------------- | ---------------- |
| decrease | 342    | 262              | 60.3%     | 286                        | 25.9%          | 74.5%            |
| increase | 375    | 300              | 50.0%     | 340                        | 37.9%          | 49.8%            |

#### Week Of Season

| segment | alerts | evaluable_alerts | precision | reversion_evaluable_alerts | reversion_rate | median_retention |
| ------- | ------ | ---------------- | --------- | -------------------------- | -------------- | ---------------- |
| 1       | 40     | 38               | 73.7%     | 38                         | 15.8%          | 82.7%            |
| 2       | 51     | 51               | 60.8%     | 51                         | 23.5%          | 78.7%            |
| 3       | 40     | 40               | 50.0%     | 40                         | 25.0%          | 47.6%            |
| 4       | 42     | 38               | 44.7%     | 39                         | 41.0%          | 33.0%            |
| 5       | 36     | 34               | 44.1%     | 34                         | 29.4%          | 40.8%            |
| 6       | 27     | 27               | 51.9%     | 27                         | 29.6%          | 55.3%            |
| 7       | 35     | 35               | 48.6%     | 35                         | 34.3%          | 45.4%            |
| 8       | 31     | 29               | 51.7%     | 31                         | 41.9%          | 50.7%            |
| 9       | 33     | 33               | 54.5%     | 33                         | 39.4%          | 52.9%            |
| 10      | 29     | 29               | 51.7%     | 29                         | 34.5%          | 57.4%            |
| 11      | 48     | 45               | 64.4%     | 46                         | 32.6%          | 70.1%            |
| 12      | 36     | 33               | 60.6%     | 35                         | 31.4%          | 68.6%            |
| 13      | 36     | 34               | 52.9%     | 34                         | 38.2%          | 60.1%            |
| 14      | 45     | 41               | 46.3%     | 41                         | 43.9%          | 41.3%            |
| 15      | 31     | 27               | 59.3%     | 31                         | 22.6%          | 93.5%            |
| 16      | 46     | 28               | 57.1%     | 38                         | 31.6%          | 79.6%            |
| 17      | 52     | 0                | —         | 44                         | 38.6%          | —                |
| 18      | 59     | 0                | —         | 0                          | —              | —                |

#### Baseline Sample Size

| segment | alerts | evaluable_alerts | precision | reversion_evaluable_alerts | reversion_rate | median_retention |
| ------- | ------ | ---------------- | --------- | -------------------------- | -------------- | ---------------- |
| 3       | 1      | 1                | 100.0%    | 1                          | 0.0%           | 173.8%           |
| 4       | 681    | 536              | 56.3%     | 593                        | 31.5%          | 60.5%            |
| 6       | 35     | 25               | 20.0%     | 32                         | 50.0%          | 16.6%            |

#### Baseline Sample Bin

| segment | alerts | evaluable_alerts | precision | reversion_evaluable_alerts | reversion_rate | median_retention |
| ------- | ------ | ---------------- | --------- | -------------------------- | -------------- | ---------------- |
| 3       | 1      | 1                | 100.0%    | 1                          | 0.0%           | 173.8%           |
| 4       | 681    | 536              | 56.3%     | 593                        | 31.5%          | 60.5%            |
| 5+      | 35     | 25               | 20.0%     | 32                         | 50.0%          | 16.6%            |

#### Raw Player Opportunities

| segment | alerts | evaluable_alerts | precision | reversion_evaluable_alerts | reversion_rate | median_retention |
| ------- | ------ | ---------------- | --------- | -------------------------- | -------------- | ---------------- |
| 0-2     | 162    | 124              | 58.1%     | 141                        | 24.8%          | 64.6%            |
| 10-14   | 130    | 103              | 49.5%     | 112                        | 37.5%          | 48.4%            |
| 15+     | 169    | 141              | 53.9%     | 155                        | 33.5%          | 59.1%            |
| 3-5     | 117    | 85               | 63.5%     | 98                         | 32.7%          | 79.4%            |
| 6-9     | 139    | 109              | 50.5%     | 120                        | 35.0%          | 50.3%            |

#### Team Opportunity Denominator

| segment | alerts | evaluable_alerts | precision | reversion_evaluable_alerts | reversion_rate | median_retention |
| ------- | ------ | ---------------- | --------- | -------------------------- | -------------- | ---------------- |
| 0-15    | 87     | 71               | 53.5%     | 84                         | 31.0%          | 52.7%            |
| 16-20   | 136    | 117              | 47.0%     | 125                        | 34.4%          | 40.8%            |
| 21-25   | 212    | 154              | 53.2%     | 178                        | 34.8%          | 55.8%            |
| 26-30   | 150    | 113              | 65.5%     | 126                        | 27.8%          | 67.7%            |
| 31-35   | 77     | 67               | 55.2%     | 70                         | 30.0%          | 59.1%            |
| 36+     | 55     | 40               | 55.0%     | 43                         | 37.2%          | 83.4%            |

#### Absolute Detected Change

| segment    | alerts | evaluable_alerts | precision | reversion_evaluable_alerts | reversion_rate | median_retention |
| ---------- | ------ | ---------------- | --------- | -------------------------- | -------------- | ---------------- |
| 0.10-0.149 | 93     | 63               | 44.4%     | 82                         | 46.3%          | 40.0%            |
| 0.15-0.199 | 251    | 206              | 47.1%     | 223                        | 39.5%          | 40.5%            |
| 0.20-0.249 | 154    | 114              | 58.8%     | 133                        | 29.3%          | 65.4%            |
| 0.25+      | 219    | 179              | 64.8%     | 188                        | 20.2%          | 80.6%            |

#### Partial Game Status

| segment                | alerts | evaluable_alerts | precision | reversion_evaluable_alerts | reversion_rate | median_retention |
| ---------------------- | ------ | ---------------- | --------- | -------------------------- | -------------- | ---------------- |
| confirmed              | 11     | 5                | 60.0%     | 7                          | 28.6%          | 141.6%           |
| none                   | 685    | 541              | 54.9%     | 603                        | 33.0%          | 58.4%            |
| suspected_corroborated | 9      | 8                | 12.5%     | 8                          | 25.0%          | 22.3%            |
| suspected_statistical  | 12     | 8                | 87.5%     | 8                          | 0.0%           | 135.0%           |

## Full-detector safeguard ablations

Every full-detector safeguard was ablated in operational and fixed-volume modes. Comparator counts remained equal within family-week; fixed-volume backfill is explicitly tagged where an ablation could not naturally supply the checkpoint count.

| ablation                         | ablated_safeguard                | alert_delta | mean_precision_delta | mean_reversion_delta | mean_retention_delta | identical_membership | no_measurable_value |
| -------------------------------- | -------------------------------- | ----------- | -------------------- | -------------------- | -------------------- | -------------------- | ------------------- |
| min_one_baseline_game            | minimum_baseline_sample          | 29          | +0.5 pp              | -0.4 pp              | +2.1 pp              | False                | False               |
| no_concentration_penalty         | concentration_penalty            | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_current_quality_or_qualifying | combined_current_quality         | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_data_quality_gate_only        | data_quality_pass                | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_denominator_component         | team_denominator                 | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_direction_consistency         | direction_consistency            | 17          | -0.7 pp              | +0.7 pp              | -1.8 pp              | False                | False               |
| no_history_quality_filter        | history_quality                  | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_identity_component            | identity_resolution              | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_late_backup_exclusion         | late_backup_exclusion            | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_minimum_absolute_delta        | minimum_absolute_delta           | 4938        | +5.2 pp              | +2.4 pp              | +5.6 pp              | False                | False               |
| no_normal_game_filter            | normal_game_filter               | -53         | -1.3 pp              | -0.0 pp              | +3.4 pp              | False                | False               |
| no_partial_game_exclusion        | partial_game_exclusion           | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_partition_component           | game_partition                   | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_qualifying_gate_only          | qualifying_game                  | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_sample_weight                 | sample_weight                    | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_score_weights                 | sample_and_concentration_weights | 0           | +0.0 pp              | +0.0 pp              | +0.0 pp              | True                 | True                |
| no_two_game_persistence          | two_game_persistence             | 694         | -7.4 pp              | +3.6 pp              | -12.2 pp             | False                | False               |

Sample weighting and the concentration penalty add no measurable selection value in the checkpoint implementation: they alter `full_score`, but alert membership is gated by the unweighted normal two-week score. Several quality safeguards are empirically no-op because they are perfectly satisfied or collinear in this dataset; they remain integrity protections and were not removed. Two-game persistence adds clear value. Direction consistency adds modest value. Removing the minimum delta explodes volume and is not treated as an improvement even when denominator-sensitive point estimates move.

## False-positive review

All 254 evaluable false positives were manually adjudicated; the source ledger hash and any overrides are recorded in the review manifest.

| manual_primary_reason_code            | cases | share |
| ------------------------------------- | ----- | ----- |
| ROLE_REVERSION_NO_OBSERVED_DATA_ISSUE | 84    | 33.1% |
| BASELINE_SMALL_OR_UNSTABLE            | 53    | 20.9% |
| LOW_TEAM_DENOMINATOR_NOISE            | 52    | 20.5% |
| MARGINAL_CHANGE_NEAR_THRESHOLD        | 35    | 13.8% |
| LOW_PLAYER_OPPORTUNITY_NOISE          | 8     | 3.1%  |
| SUSPECTED_FOCAL_PARTIAL               | 8     | 3.1%  |
| NORMAL_CONTEXT_SENSITIVE              | 7     | 2.8%  |
| SUSPECTED_TEAMMATE_EXIT_CONTEXT       | 5     | 2.0%  |
| CONFIRMED_FOCAL_PARTIAL               | 2     | 0.8%  |

Reason codes describe observed evidence, not inferred injuries. `ROLE_REVERSION_NO_OBSERVED_DATA_ISSUE` means the role outcome failed without a confirmed data defect; it does not manufacture a causal explanation.

## Candidate redevelopment

The one-factor screen attempted 54 candidates: 53 passed all comparator-integrity checks and 1 failed fast. The failed one-game screen could not provide the required two-week-raw comparator count for one early family-week; it was retained as an integrity failure, not silently discarded.

| candidate_name                                | screening_axis           | screening_level | integrity_error                                                                                                                               |
| --------------------------------------------- | ------------------------ | --------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| screen_consecutive_confirmation_one_game_none | consecutive_confirmation | one_game_none   | Equal-volume selection impossible for screen_consecutive_confirmation_one_game_none rb_carry_share 2018 week 5 two_week_raw: need 10, have 0. |

Six serious candidates were rerun on 2018–2020 and revised 2021. The 2021 results are redevelopment evidence because the failed 2021 Fold 1 outcome was already observed.

| candidate                           | median feed | max | zero weeks | RB carry precision/lift | RB opp precision/lift | decision     |
| ----------------------------------- | ----------- | --- | ---------- | ----------------------- | --------------------- | ------------ |
| S1_corrected_minimal                | 27.0        | 46  | 5          | 54.5% / +5.5 pp         | 57.8% / +6.6 pp       | not selected |
| S2_balanced_directional             | 8.5         | 20  | 5          | 68.1% / +19.2 pp        | 65.5% / +11.9 pp      | not selected |
| S2_balanced_directional_no_cooldown | 10.0        | 22  | 5          | 66.1% / +15.3 pp        | 64.0% / +5.7 pp       | not selected |
| S2_symmetric_deltas                 | 7.5         | 17  | 5          | 74.4% / +25.6 pp        | 67.3% / +14.5 pp      | recommended  |
| S3_balanced_season_recent           | 9.0         | 16  | 5          | 60.4% / +12.4 pp        | 61.9% / +6.3 pp       | not selected |
| S4_high_specificity                 | 4.5         | 13  | 5          | 77.4% / +30.8 pp        | 69.8% / +9.3 pp       | not selected |

The recommendation is not based on a single best metric. The symmetric candidate uses the simplest common absolute-change threshold by family, materially improves the governing RB point estimates, preserves equal-volume comparisons, is insensitive to the partial-game policy, and reaches the operating median without weakening qualification. It does not dominate every candidate or every metric.

## Original versus recommended Fold 1

| role_family          | original_full_alerts | original_full_evaluable_alerts | original_full_precision | original_naive_precision | original_precision_improvement | original_relative_precision_improvement | original_precision_improvement_ci_low | original_precision_improvement_ci_high | original_full_reversion_rate | original_naive_reversion_rate | original_reversion_improvement | original_full_median_retention | original_naive_median_retention | revised_full_alerts | revised_full_evaluable_alerts | revised_full_precision | revised_naive_precision | revised_precision_improvement | revised_relative_precision_improvement | revised_precision_improvement_ci_low | revised_precision_improvement_ci_high | revised_full_reversion_rate | revised_naive_reversion_rate | revised_reversion_improvement | revised_full_median_retention | revised_naive_median_retention | delta_full_alerts | delta_full_evaluable_alerts | delta_full_precision | delta_precision_improvement | delta_full_reversion_rate | delta_reversion_improvement | delta_full_median_retention |
| -------------------- | -------------------- | ------------------------------ | ----------------------- | ------------------------ | ------------------------------ | --------------------------------------- | ------------------------------------- | -------------------------------------- | ---------------------------- | ----------------------------- | ------------------------------ | ------------------------------ | ------------------------------- | ------------------- | ----------------------------- | ---------------------- | ----------------------- | ----------------------------- | -------------------------------------- | ------------------------------------ | ------------------------------------- | --------------------------- | ---------------------------- | ----------------------------- | ----------------------------- | ------------------------------ | ----------------- | --------------------------- | -------------------- | --------------------------- | ------------------------- | --------------------------- | --------------------------- |
| rb_carry_share       | 273                  | 222                            | 0.5720720720720721      | 0.4932126696832579       | 0.0788594023888141             | 0.1598892470452103                      | 0.0213412292658453                    | 0.1406063637200594                     | 0.2815126050420168           | 0.3458333333333333            | 0.0643207282913165             | 0.6573276189121569             | 0.4671445557777681              | 56                  | 43                            | 0.7441860465116279     | 0.4878048780487805      | 0.2563811684628474            | 0.5255813953488372                     | 0.0068815818341378                   | 0.4839181286549707                    | 0.1875                      | 0.2978723404255319           | 0.1103723404255319            | 0.7615060530105061            | 0.404684401165319              | -217              | -179                        | 0.1721139744395557   | 0.1775217660740332          | -0.0940126050420168       | 0.0460516121342153          | 0.1041784340983492          |
| rb_opportunity_share | 324                  | 256                            | 0.5859375               | 0.5175097276264592       | 0.0684277723735408             | 0.1322250939849623                      | 0.0018074645496134                    | 0.1433175912703629                     | 0.301418439716312            | 0.3226950354609929            | 0.0212765957446808             | 0.6426345802472127             | 0.5477918730072584              | 77                  | 55                            | 0.6727272727272727     | 0.5272727272727272      | 0.1454545454545455            | 0.2758620689655173                     | -0.0214576396596374                  | 0.2770182505473453                    | 0.1904761904761904          | 0.3015873015873015           | 0.1111111111111111            | 0.6844351740744619            | 0.6278066961197972             | -247              | -201                        | 0.0867897727272727   | 0.0770267730810047          | -0.1109422492401215       | 0.0898345153664302          | 0.0418005938272492          |
| te_target_share      | 35                   | 25                             | 0.2                     | 0.2692307692307692       | -0.0692307692307692            | -0.257142857142857                      | -0.2045853269537479                   | 0.0666923076923075                     | 0.5                          | 0.4545454545454545            | -0.0454545454545454            | 0.1659512962054916             | 0.165085490548323               | 4                   | 2                             | 0.5                    | 0.0                     | 0.5                           | —                                      | 0.0                                  | 1.0                                   | 0.5                         | 0.5                          | 0.0                           | -0.1413190347883313           | -0.1189919073256889            | -31               | -23                         | 0.3                  | 0.5692307692307692          | 0.0                       | 0.0454545454545454          | -0.3072703309938229         |
| wr_target_share      | 85                   | 59                             | 0.4406779661016949      | 0.2950819672131147       | 0.1455959988885801             | 0.4934086629001883                      | 0.0151403743315508                    | 0.272533797417272                      | 0.4729729729729729           | 0.5342465753424658            | 0.0612736023694928             | 0.4002018691588783             | 0.2988374438524246              | 26                  | 16                            | 0.5625                 | 0.1764705882352941      | 0.3860294117647058            | 2.1875                                 | 0.1764705882352941                   | 0.6470588235294117                    | 0.3636363636363636          | 0.6818181818181818           | 0.3181818181818181            | 0.5513797372748699            | 0.0822879292051455             | -59               | -43                         | 0.1218220338983051   | 0.2404334128761256          | -0.1093366093366093       | 0.2569082158123253          | 0.1511778681159916          |

## Recommended candidate results

### Development, 2018–2020

| role_family          | full_alerts | full_evaluable_alerts | full_reversion_rate | reversion_improvement | full_median_retention | precision (95% CI)     | improvement (95% CI)            |
| -------------------- | ----------- | --------------------- | ------------------- | --------------------- | --------------------- | ---------------------- | ------------------------------- |
| rb_carry_share       | 157         | 122                   | 21.2%               | +10.9 pp              | 72.3%                 | 66.4% (58.2% to 74.6%) | +21.9 pp (+12.5 pp to +31.8 pp) |
| rb_opportunity_share | 219         | 167                   | 24.2%               | +5.6 pp               | 70.4%                 | 62.3% (54.5% to 69.5%) | +9.4 pp (-0.4 pp to +18.4 pp)   |
| te_target_share      | 4           | 4                     | 25.0%               | +25.0 pp              | 49.1%                 | 50.0% (0.0% to 100.0%) | +50.0 pp (+0.0 pp to +100.0 pp) |
| wr_target_share      | 78          | 61                    | 23.9%               | +27.5 pp              | 46.3%                 | 47.5% (34.4% to 60.7%) | +25.0 pp (+8.6 pp to +42.2 pp)  |

### Revised Fold 1, 2021

| role_family          | full_alerts | full_evaluable_alerts | full_reversion_rate | reversion_improvement | full_median_retention | precision (95% CI)     | improvement (95% CI)            |
| -------------------- | ----------- | --------------------- | ------------------- | --------------------- | --------------------- | ---------------------- | ------------------------------- |
| rb_carry_share       | 56          | 43                    | 18.8%               | +11.0 pp              | 76.2%                 | 74.4% (60.5% to 86.0%) | +25.6 pp (+0.7 pp to +48.4 pp)  |
| rb_opportunity_share | 77          | 55                    | 19.0%               | +11.1 pp              | 68.4%                 | 67.3% (54.5% to 78.2%) | +14.5 pp (-2.1 pp to +27.7 pp)  |
| te_target_share      | 4           | 2                     | 50.0%               | +0.0 pp               | -14.1%                | 50.0% (0.0% to 100.0%) | +50.0 pp (+0.0 pp to +100.0 pp) |
| wr_target_share      | 26          | 16                    | 36.4%               | +31.8 pp              | 55.1%                 | 56.2% (31.2% to 81.2%) | +38.6 pp (+17.6 pp to +64.7 pp) |

The precision interval is a seeded 2,000-draw bootstrap over evaluable alerts, matching the locked workflow. Improvement intervals use a seeded season-week cluster bootstrap. Uncertainty does not move the locked point gates.

RB carry is the strongest candidate. RB opportunity advances with development precision-improvement and reversion-improvement caveats: its 2018–2020 point lifts miss the locked 10- and 8-point diagnostics, and its improvement intervals include zero. WR and TE remain shadow-only because evidence and/or absolute performance are insufficient. No family is declared validated.

### Direction

| period                | role_family          | direction | alerts | evaluable_alerts | precision | reversion_rate | median_retention |
| --------------------- | -------------------- | --------- | ------ | ---------------- | --------- | -------------- | ---------------- |
| development_2018_2020 | rb_carry_share       | decrease  | 66     | 50               | 66.0%     | 22.8%          | 77.7%            |
| development_2018_2020 | rb_carry_share       | increase  | 91     | 72               | 66.7%     | 20.0%          | 67.7%            |
| development_2018_2020 | rb_opportunity_share | decrease  | 108    | 84               | 63.1%     | 26.8%          | 70.8%            |
| development_2018_2020 | rb_opportunity_share | increase  | 111    | 83               | 61.4%     | 21.6%          | 70.4%            |
| development_2018_2020 | te_target_share      | decrease  | 1      | 1                | 0.0%      | 0.0%           | -16.2%           |
| development_2018_2020 | te_target_share      | increase  | 3      | 3                | 66.7%     | 33.3%          | 67.9%            |
| development_2018_2020 | wr_target_share      | decrease  | 34     | 28               | 42.9%     | 25.0%          | 44.8%            |
| development_2018_2020 | wr_target_share      | increase  | 44     | 33               | 51.5%     | 23.1%          | 51.1%            |
| fold_1_2021           | rb_carry_share       | decrease  | 24     | 19               | 78.9%     | 15.8%          | 86.4%            |
| fold_1_2021           | rb_carry_share       | increase  | 32     | 24               | 70.8%     | 20.7%          | 73.8%            |
| fold_1_2021           | rb_opportunity_share | decrease  | 33     | 22               | 63.6%     | 11.5%          | 63.3%            |
| fold_1_2021           | rb_opportunity_share | increase  | 44     | 33               | 69.7%     | 24.3%          | 71.5%            |
| fold_1_2021           | te_target_share      | decrease  | 2      | 0                | —         | —              | —                |
| fold_1_2021           | te_target_share      | increase  | 2      | 2                | 50.0%     | 50.0%          | -14.1%           |
| fold_1_2021           | wr_target_share      | decrease  | 9      | 6                | 16.7%     | 57.1%          | 28.8%            |
| fold_1_2021           | wr_target_share      | increase  | 17     | 10               | 80.0%     | 26.7%          | 75.1%            |

WR direction results are unstable in 2021 (strong increases, weak decreases on small samples); TE is too sparse for inference.

### 2021 week blocks

| week_block  | role_family          | full_alerts | full_evaluable_alerts | full_precision | precision_improvement | full_reversion_rate | reversion_improvement | full_median_retention |
| ----------- | -------------------- | ----------- | --------------------- | -------------- | --------------------- | ------------------- | --------------------- | --------------------- |
| weeks_13_18 | rb_carry_share       | 32          | 19                    | 68.4%          | +15.5 pp              | 33.3%               | -7.2 pp               | 76.2%                 |
| weeks_13_18 | rb_opportunity_share | 46          | 25                    | 76.0%          | +26.0 pp              | 21.9%               | +12.5 pp              | 77.8%                 |
| weeks_13_18 | te_target_share      | 3           | 1                     | 0.0%           | +0.0 pp               | 100.0%              | -100.0 pp             | -81.3%                |
| weeks_13_18 | wr_target_share      | 15          | 6                     | 66.7%          | +38.1 pp              | 45.5%               | +36.4 pp              | 72.7%                 |
| weeks_1_6   | rb_carry_share       | 3           | 3                     | 33.3%          | -66.7 pp              | 0.0%                | +0.0 pp               | 0.1%                  |
| weeks_1_6   | rb_opportunity_share | 4           | 4                     | 50.0%          | -50.0 pp              | 25.0%               | -25.0 pp              | 30.8%                 |
| weeks_1_6   | wr_target_share      | 2           | 2                     | 50.0%          | +0.0 pp               | 0.0%                | +0.0 pp               | 75.0%                 |
| weeks_7_12  | rb_carry_share       | 21          | 21                    | 85.7%          | +47.6 pp              | 4.8%                | +33.3 pp              | 86.4%                 |
| weeks_7_12  | rb_opportunity_share | 27          | 26                    | 61.5%          | +13.4 pp              | 14.8%               | +14.8 pp              | 68.2%                 |
| weeks_7_12  | te_target_share      | 1           | 1                     | 100.0%         | +100.0 pp             | 0.0%                | +100.0 pp             | 53.1%                 |
| weeks_7_12  | wr_target_share      | 9           | 8                     | 50.0%          | +50.0 pp              | 33.3%               | +33.3 pp              | 43.2%                 |

Weeks 1–5 have no alerts by construction after season reset and a four-game disjoint baseline. Weeks 1–6 therefore represent only tiny Week 6 samples. RB precision lift is positive in both post-accrual blocks, but RB-carry reversion improvement becomes negative late in the season; full multi-metric weekly stability is not established.

### Deduplicated weekly feed

| week | family_alert_rows | deduplicated_feed_alerts | duplicate_family_rows_removed |
| ---- | ----------------- | ------------------------ | ----------------------------- |
| 1    | 0                 | 0                        | 0                             |
| 2    | 0                 | 0                        | 0                             |
| 3    | 0                 | 0                        | 0                             |
| 4    | 0                 | 0                        | 0                             |
| 5    | 0                 | 0                        | 0                             |
| 6    | 9                 | 6                        | 3                             |
| 7    | 10                | 7                        | 3                             |
| 8    | 4                 | 3                        | 1                             |
| 9    | 13                | 10                       | 3                             |
| 10   | 8                 | 6                        | 2                             |
| 11   | 11                | 8                        | 3                             |
| 12   | 12                | 11                       | 1                             |
| 13   | 19                | 11                       | 8                             |
| 14   | 10                | 8                        | 2                             |
| 15   | 13                | 11                       | 2                             |
| 16   | 21                | 14                       | 7                             |
| 17   | 12                | 10                       | 2                             |
| 18   | 21                | 17                       | 4                             |

| candidate_name                      | partial_policy             | family_alert_rows | deduplicated_feed_alerts | duplicate_family_rows_removed | median_all_18_weeks | median_active_weeks | mean_all_18_weeks | p90_all_18_weeks   | max_week | zero_alert_weeks | weeks_above_15 | weeks_above_20 | within_5_15_median_target |
| ----------------------------------- | -------------------------- | ----------------- | ------------------------ | ----------------------------- | ------------------- | ------------------- | ----------------- | ------------------ | -------- | ---------------- | -------------- | -------------- | ------------------------- |
| fold2_candidate_v1_symmetric_deltas | PRIMARY_CONFIRMED_EXCLUDED | 163               | 122                      | 41                            | 7.5                 | 10.0                | 6.777777777777778 | 11.900000000000002 | 17       | 5                | 1              | 0              | True                      |

The primary feed has a 7.5 all-week median, 10 active-week median, 17 maximum, five zero-alert weeks, one week above 15, and no week above 20. It meets the seasonal median target but does not produce 5–15 alerts every week.

### Locked-gate diagnostic

| role_family          | point_gate_result | alerts | precision | precision_improvement | reversion_rate | reversion_improvement | median_retention | failed_checks                                                                                                                                              |
| -------------------- | ----------------- | ------ | --------- | --------------------- | -------------- | --------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| rb_carry_share       | POINT_GATES_PASS  | 56     | 74.4%     | +25.6 pp              | 18.8%          | +11.0 pp              | 76.2%            | —                                                                                                                                                          |
| rb_opportunity_share | POINT_GATES_PASS  | 77     | 67.3%     | +14.5 pp              | 19.0%          | +11.1 pp              | 68.4%            | —                                                                                                                                                          |
| te_target_share      | POINT_GATES_FAIL  | 4      | 50.0%     | +50.0 pp              | 50.0%          | +0.0 pp               | -14.1%           | min_holdout_alerts, min_persistence_precision, max_immediate_reversion_rate, min_reversion_improvement_vs_naive, min_median_retention, min_alerts_per_week |
| wr_target_share      | POINT_GATES_FAIL  | 26     | 56.2%     | +38.6 pp              | 36.4%          | +31.8 pp              | 55.1%            | min_holdout_alerts, min_persistence_precision, max_immediate_reversion_rate                                                                                |

`point_gate_result` is descriptive only. The revised rules were developed after observing 2021, so they were not frozen before this test and cannot authorize release. Fold 2 is the next untouched test.

### Persistence-threshold sensitivity

| persistence_threshold | period                | role_family          | full_evaluable_alerts | full_precision | precision_improvement | improvement 95% CI    |
| --------------------- | --------------------- | -------------------- | --------------------- | -------------- | --------------------- | --------------------- |
| 40.0%                 | development_2018_2020 | rb_carry_share       | 122                   | 71.3%          | +18.3 pp              | +7.6 pp to +28.5 pp   |
| 40.0%                 | development_2018_2020 | rb_opportunity_share | 167                   | 69.5%          | +10.2 pp              | +1.5 pp to +19.2 pp   |
| 40.0%                 | development_2018_2020 | te_target_share      | 4                     | 50.0%          | +16.7 pp              | -75.0 pp to +100.0 pp |
| 40.0%                 | development_2018_2020 | wr_target_share      | 61                    | 57.4%          | +25.1 pp              | +6.5 pp to +42.6 pp   |
| 40.0%                 | fold_1_2021           | rb_carry_share       | 43                    | 76.7%          | +25.5 pp              | -0.2 pp to +48.9 pp   |
| 40.0%                 | fold_1_2021           | rb_opportunity_share | 55                    | 74.5%          | +18.2 pp              | +1.9 pp to +30.0 pp   |
| 40.0%                 | fold_1_2021           | te_target_share      | 2                     | 50.0%          | +50.0 pp              | +0.0 pp to +100.0 pp  |
| 40.0%                 | fold_1_2021           | wr_target_share      | 16                    | 62.5%          | +39.0 pp              | +23.5 pp to +53.6 pp  |
| 50.0%                 | development_2018_2020 | rb_carry_share       | 122                   | 66.4%          | +21.9 pp              | +12.5 pp to +31.8 pp  |
| 50.0%                 | development_2018_2020 | rb_opportunity_share | 167                   | 62.3%          | +9.4 pp               | -0.4 pp to +18.4 pp   |
| 50.0%                 | development_2018_2020 | te_target_share      | 4                     | 50.0%          | +50.0 pp              | +0.0 pp to +100.0 pp  |
| 50.0%                 | development_2018_2020 | wr_target_share      | 61                    | 47.5%          | +25.0 pp              | +8.6 pp to +42.2 pp   |
| 50.0%                 | fold_1_2021           | rb_carry_share       | 43                    | 74.4%          | +25.6 pp              | +0.7 pp to +48.4 pp   |
| 50.0%                 | fold_1_2021           | rb_opportunity_share | 55                    | 67.3%          | +14.5 pp              | -2.1 pp to +27.7 pp   |
| 50.0%                 | fold_1_2021           | te_target_share      | 2                     | 50.0%          | +50.0 pp              | +0.0 pp to +100.0 pp  |
| 50.0%                 | fold_1_2021           | wr_target_share      | 16                    | 56.2%          | +38.6 pp              | +17.6 pp to +64.7 pp  |
| 60.0%                 | development_2018_2020 | rb_carry_share       | 122                   | 59.8%          | +20.5 pp              | +8.9 pp to +33.5 pp   |
| 60.0%                 | development_2018_2020 | rb_opportunity_share | 167                   | 55.7%          | +9.8 pp               | +0.6 pp to +18.4 pp   |
| 60.0%                 | development_2018_2020 | te_target_share      | 4                     | 50.0%          | +50.0 pp              | +0.0 pp to +100.0 pp  |
| 60.0%                 | development_2018_2020 | wr_target_share      | 61                    | 41.0%          | +28.1 pp              | +11.6 pp to +45.9 pp  |
| 60.0%                 | fold_1_2021           | rb_carry_share       | 43                    | 62.8%          | +16.4 pp              | -0.7 pp to +34.0 pp   |
| 60.0%                 | fold_1_2021           | rb_opportunity_share | 55                    | 58.2%          | +7.3 pp               | -12.5 pp to +21.6 pp  |
| 60.0%                 | fold_1_2021           | te_target_share      | 2                     | 0.0%           | +0.0 pp               | +0.0 pp to +0.0 pp    |
| 60.0%                 | fold_1_2021           | wr_target_share      | 16                    | 43.8%          | +37.9 pp              | +22.8 pp to +53.3 pp  |

### Partial-game sensitivity

| partial_policy             | family_alert_rows | deduplicated_feed_alerts | median_all_18_weeks | max_week | zero_alert_weeks |
| -------------------------- | ----------------- | ------------------------ | ------------------- | -------- | ---------------- |
| PRIMARY_CONFIRMED_EXCLUDED | 163               | 122                      | 7.5                 | 17       | 5                |
| ALL_INCLUDED               | 167               | 125                      | 7.5                 | 17       | 5                |
| STRICT_SUSPECTED_EXCLUDED  | 160               | 121                      | 6.0                 | 15       | 5                |

| partial_policy             | role_family          | full_alerts | full_evaluable_alerts | full_precision | precision_improvement | full_reversion_rate | full_median_retention |
| -------------------------- | -------------------- | ----------- | --------------------- | -------------- | --------------------- | ------------------- | --------------------- |
| ALL_INCLUDED               | rb_carry_share       | 58          | 44                    | 75.0%          | +27.4 pp              | 20.0%               | 76.5%                 |
| ALL_INCLUDED               | rb_opportunity_share | 78          | 56                    | 69.6%          | +15.1 pp              | 18.8%               | 69.4%                 |
| ALL_INCLUDED               | te_target_share      | 4           | 2                     | 50.0%          | +50.0 pp              | 50.0%               | -14.1%                |
| ALL_INCLUDED               | wr_target_share      | 27          | 16                    | 56.2%          | +39.6 pp              | 36.4%               | 55.1%                 |
| PRIMARY_CONFIRMED_EXCLUDED | rb_carry_share       | 56          | 43                    | 74.4%          | +25.6 pp              | 18.8%               | 76.2%                 |
| PRIMARY_CONFIRMED_EXCLUDED | rb_opportunity_share | 77          | 55                    | 67.3%          | +14.5 pp              | 19.0%               | 68.4%                 |
| PRIMARY_CONFIRMED_EXCLUDED | te_target_share      | 4           | 2                     | 50.0%          | +50.0 pp              | 50.0%               | -14.1%                |
| PRIMARY_CONFIRMED_EXCLUDED | wr_target_share      | 26          | 16                    | 56.2%          | +38.6 pp              | 36.4%               | 55.1%                 |
| STRICT_SUSPECTED_EXCLUDED  | rb_carry_share       | 53          | 42                    | 71.4%          | +23.9 pp              | 21.3%               | 76.3%                 |
| STRICT_SUSPECTED_EXCLUDED  | rb_opportunity_share | 78          | 56                    | 67.9%          | +15.2 pp              | 20.0%               | 68.5%                 |
| STRICT_SUSPECTED_EXCLUDED  | te_target_share      | 4           | 2                     | 50.0%          | +50.0 pp              | 50.0%               | -14.1%                |
| STRICT_SUSPECTED_EXCLUDED  | wr_target_share      | 25          | 16                    | 62.5%          | +39.0 pp              | 33.3%               | 55.7%                 |

The recommendation is not driven by suspected partial games. Suspected cases remain included in the primary policy; excluding them is sensitivity only.

## Exact candidate recommended for Fold 2

```yaml
candidate_version: fold2-candidate-v1
status: recommended_for_untouched_2022_test_not_executed
derived_from_checkpoint: 00d6085a55c60147e0ace46c847460ef5708e968
analysis_contract:
  allowed_development_data:
  - 2018
  - 2019
  - 2020
  - 2021
  fold_1_development_seasons:
  - 2018
  - 2019
  - 2020
  fold_1_test_season: 2021
  fold_2_test_season: 2022
  fold_2_executed: false
  post_2021_results_used: false
  release_gates_changed: false
  release_gates_source: config/role_change_validation.yaml
  release_gates_source_sha256: e6a64afa9dcec76cf2c0ef582640c575f0f74e6f799427ff4f114699b97a086d
  protocol_sha256: b9fcc357e98388bb15c2d7ae853620f8ccd6c2e60e491a6cfcb990bbfbfcadbe
  locked_decisions_sha256: 57da1e3ebed077bd52709fb3331eb99e719c056e9e840d8c6913b512d7e4ba00
candidate:
  name: fold2_candidate_v1_symmetric_deltas
  metric: metric_normal
  baseline:
    type: recent
    recent_games: 4
    min_games: 4
    exclude_confirmation_games: true
    reset_each_season: true
    recent_weight: 1.0
    season_weight: 0.0
  confirmation:
    default_games: 2
    mode: strict
    require_each_game_same_direction: true
    te_target_share_games: 3
  thresholds:
    rb_carry_share:
      increase:
        min_abs_delta: 0.2
        min_player_opportunities: 6
        player_opportunity_reference: confirmation_min
        min_team_denominator: 18
      decrease:
        min_abs_delta: 0.2
        min_player_opportunities: 6
        player_opportunity_reference: baseline_mean
        min_team_denominator: 18
    rb_opportunity_share:
      increase:
        min_abs_delta: 0.2
        min_player_opportunities: 6
        player_opportunity_reference: confirmation_min
        min_team_denominator: 18
      decrease:
        min_abs_delta: 0.2
        min_player_opportunities: 6
        player_opportunity_reference: baseline_mean
        min_team_denominator: 18
    wr_target_share:
      increase:
        min_abs_delta: 0.15
        min_player_opportunities: 4
        player_opportunity_reference: confirmation_min
        min_team_denominator: 20
      decrease:
        min_abs_delta: 0.15
        min_player_opportunities: 4
        player_opportunity_reference: baseline_mean
        min_team_denominator: 20
    te_target_share:
      increase:
        min_abs_delta: 0.15
        min_player_opportunities: 3
        player_opportunity_reference: confirmation_min
        min_team_denominator: 20
      decrease:
        min_abs_delta: 0.15
        min_player_opportunities: 3
        player_opportunity_reference: baseline_mean
        min_team_denominator: 20
  safeguards:
    require_data_quality: true
    require_qualifying_game: true
    history_uses_exclusion_policy: true
    require_min_abs_delta: true
    require_player_opportunity_floor: true
    require_team_denominator_floor: true
  partial_game_policy:
    primary: PRIMARY_CONFIRMED_EXCLUDED
    confirmed_focal_games: exclude from trigger, baseline, and outcome history
    suspected_focal_games: include in primary
    sensitivities:
    - ALL_INCLUDED
    - STRICT_SUSPECTED_EXCLUDED
  repeat_suppression:
    enabled: true
    scope: player_role_family
    cooldown_calendar_weeks: 1
    direction_sensitive: true
  feed_deduplication:
    key:
    - season
    - week
    - player_id
    - team
    preserve_role_family_tags: true
    deduplication_affects_volume_only: true
  comparison:
    methods:
    - naive_spike
    - two_week_raw
    - normal_game_trend
    - full_propwar
    equal_volume_within:
    - role_family
    - season
    - week
    deterministic_ties:
    - absolute_score_desc
    - player_id_asc
    - team_asc
family_disposition_after_fold_1:
  rb_carry_share:
    fold_2_status: recommended_for_untouched_test
    detector_claim_supported_now: false
  rb_opportunity_share:
    fold_2_status: recommended_for_untouched_test_with_development_precision_and_reversion_caveats
    detector_claim_supported_now: false
  wr_target_share:
    fold_2_status: shadow_test_only_insufficient_fold_1_evidence
    detector_claim_supported_now: false
  te_target_share:
    fold_2_status: shadow_test_only_insufficient_fold_1_evidence
    detector_claim_supported_now: false
```

## Limitations and blockers

- Revised 2021 is not an untouched holdout; it is redevelopment evidence.
- RB carry is the strongest candidate, but its revised-2021 50% improvement interval is only narrowly above zero (+0.7 pp lower bound), and its 40%/60% persistence-threshold sensitivity intervals include zero.
- RB opportunity misses both the locked development precision-improvement and reversion-improvement point gates; its improvement intervals include zero, and one development season is negative.
- WR and TE evidence is insufficient; TE has only four family alerts in each aggregate period.
- Week-level stability is incomplete, and early-season coverage is intentionally zero until the baseline accrues.
- Historical PBP has no immutable publication timestamp. Confirmed evidence uses a conservative kickoff-plus-six-hours availability proxy and a strict next-team-game boundary.
- The explicit nflverse PBP, roster, and schedule pulls are not independently snapshotted in this commit; future rebuilds can differ if upstream historical files are revised. The executed evidence ledger and derived artifacts are committed.
- Equal-volume comparison is exact within family-week, but small family samples still produce wide intervals.
- Fold 2 was not executed. No claim that the detector works is supported yet.

## Machine-readable evidence

The report tables are backed by CSV/GZIP artifacts in this directory, including the full original diagnostics, requested breakdowns, every safeguard ablation, 53 valid/1 failed candidate screen, six serious-candidate archives, equal-volume verification, partial-game evidence, sensitivity analyses, and the original-versus-recommended comparison.

Exact material commands are recorded in `COMMANDS_RUN.md`. Unit-test, notebook, and independent-validation results are recorded in `TEST_AND_VALIDATION_RESULTS.md` and `final_validation.json`.
