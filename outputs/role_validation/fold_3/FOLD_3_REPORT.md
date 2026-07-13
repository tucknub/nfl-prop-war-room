# PropWar Role Validation — Fold 3 (Untouched 2023)

## Concise judgment

RB carry **passes the unchanged Fold 3 point gates** and should advance unchanged to Fold 4. RB opportunity **fails the unchanged Fold 3 point gates** only on cross-period direction consistency and should remain an unchanged shadow candidate. Neither family is described as validated. WR and TE remain retired, descriptive-only families and are not reinstated.

The 2023 holdout was executed exactly once. No 2024–2025 result was selected or used, no detector or gate was changed after outcome access, and Fold 4 was not executed.

## Configuration integrity

- Candidate SHA-256: `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7`
- Frozen-copy SHA-256: `4dcf389a1f8fcdd11a9277305a8372fadaabaa830185e07eff5d8fbb274a81c7`
- Required Fold 2 hash match: **yes**
- Pre-Fold-3 checkpoint tag: `role-change-validation-v1-pre-fold3-checkpoint` → `c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9`
- Starting checkpoint: `c10bb7f3e0446a3c5f85caa4adcb3175fe6be4f9`
- Protected release-gate SHA-256: `e6a64afa9dcec76cf2c0ef582640c575f0f74e6f799427ff4f114699b97a086d`
- Protocol and locked-decision hashes: unchanged
- Execution lock completed: **yes**; alert archive SHA-256: `f9c4b971c0abb15662f66f3cc2d9103df0bed257b718408c82543f4f0cc943ee`
- Equal-volume cells: 216; all exact: **yes**
- Temporal checks: **all passed** (`baseline < confirmation ≤ alert < outcomes`)

## 2023 data audit

| canonical rows | players | played games | weeks | duplicate keys | required null cells | identity | quality | qualifying |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7,448 | 531 | 272 | 18 | 0 | 0 | 100.0% | 100.0% | 100.0% |

PBP and schedule each contain 272 played games over all 18 weeks. Opportunity and participation identity joins are 100% (41,792/41,792). The primary policy excluded 17 confirmed partial family rows and retained 68 suspected rows.

## RB method results

| role_family | method | alerts | deduplicated_player_week_team_alerts | evaluable_alerts | precision | precision_ci_low | precision_ci_high | reversion_rate | median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | full_propwar | 60 | 60 | 47 | 66.0% | 53.2% | 78.7% | 23.1% | 79.5% |
| rb_carry_share | naive_spike | 60 | 60 | 49 | 53.1% | 38.8% | 67.3% | 32.7% | 52.7% |
| rb_carry_share | normal_game_trend | 60 | 60 | 49 | 63.3% | 51.0% | 75.5% | 20.8% | 75.5% |
| rb_carry_share | two_week_raw | 60 | 60 | 49 | 67.3% | 55.1% | 79.6% | 20.8% | 74.6% |
| rb_opportunity_share | full_propwar | 74 | 74 | 57 | 77.2% | 66.7% | 87.7% | 15.6% | 91.0% |
| rb_opportunity_share | naive_spike | 74 | 74 | 58 | 56.9% | 44.8% | 69.0% | 31.7% | 61.7% |
| rb_opportunity_share | normal_game_trend | 74 | 74 | 58 | 72.4% | 60.3% | 84.5% | 15.6% | 73.0% |
| rb_opportunity_share | two_week_raw | 74 | 74 | 59 | 66.1% | 54.2% | 78.0% | 18.8% | 70.2% |

## Frozen detector versus equal-volume naive

| role_family | full_alerts | full_evaluable_alerts | full_precision | naive_precision | precision_improvement | precision_improvement_ci_low | precision_improvement_ci_high | full_reversion_rate | naive_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | 60 | 47 | 66.0% | 53.1% | +12.9 pp | -3.1 pp | +26.3 pp | 23.1% | 32.7% | +9.6 pp | 79.5% |
| rb_opportunity_share | 74 | 57 | 77.2% | 56.9% | +20.3 pp | +5.8 pp | +34.4 pp | 15.6% | 31.7% | +16.1 pp | 91.0% |

Every family-week-policy comparison preserved exact method alert counts. Confidence intervals are bootstrap intervals and are reported as uncertainty, not as replacements for the locked point gates.

## Feed volume, overlap, and repeats

The complete descriptive primary feed contains 165 family rows and 124 deduplicated player-week-team alerts; 41 overlapping family rows are removed by deduplication. Its weekly median is 8.5, maximum 17, with 5 zero-alert weeks.

| role_family | weekly_median | weekly_maximum | zero_alert_weeks | active_weeks | weekly_mean |
| --- | --- | --- | --- | --- | --- |
| rb_carry_share | 4.0 | 8 | 5 | 13 | 3.333333333333333 |
| rb_opportunity_share | 4.5 | 11 | 5 | 13 | 4.111111111111111 |

| partial_policy | method | carry_alerts | opportunity_alerts | overlap_alerts | union_alerts | jaccard_overlap |
| --- | --- | --- | --- | --- | --- | --- |
| PRIMARY_CONFIRMED_EXCLUDED | full_propwar | 60 | 74 | 41 | 93 | 44.1% |

| role_family | alerts | repeat_alerts | repeat_players | repeat_rate |
| --- | --- | --- | --- | --- |
| rb_carry_share | 60 | 1 | 1 | 1.7% |
| rb_opportunity_share | 74 | 0 | 0 | 0.0% |

RB carry and RB opportunity overlap on 41 player-week-team alerts (Jaccard 44.1%). The full detector emitted one literal consecutive-week RB carry repeat and zero RB opportunity repeats.

## Directional results (diagnostic only)

| role_family | direction | alerts_full | evaluable_alerts_full | precision_full | precision_naive | naive_improvement | reversion_rate_full | median_retention_full |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | decrease | 31 | 25 | 60.0% | 50.0% | +10.0 pp | 25.9% | 70.2% |
| rb_carry_share | increase | 29 | 22 | 72.7% | 55.6% | +17.2 pp | 20.0% | 83.0% |
| rb_opportunity_share | decrease | 41 | 34 | 79.4% | 59.3% | +20.2 pp | 13.5% | 95.3% |
| rb_opportunity_share | increase | 33 | 23 | 73.9% | 54.8% | +19.1 pp | 18.5% | 86.2% |

RB carry increases are stronger than decreases, but both directions beat equal-volume naive in 2023. RB opportunity is strong in both 2023 directions; its locked gate failure comes from 2021 decreases, not its 2023 point performance. No direction-specific selection rule was introduced.

## Early-, middle-, and late-season stability

| role_family | week_block | alerts | evaluable_alerts | precision | reversion_rate | median_retention |
| --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | weeks_13_18 | 30 | 17 | 64.7% | 18.2% | 82.7% |
| rb_carry_share | weeks_1_6 | 2 | 2 | 50.0% | 0.0% | 63.5% |
| rb_carry_share | weeks_7_12 | 28 | 28 | 67.9% | 28.6% | 75.6% |
| rb_opportunity_share | weeks_13_18 | 35 | 19 | 73.7% | 15.4% | 91.0% |
| rb_opportunity_share | weeks_1_6 | 3 | 3 | 66.7% | 33.3% | 118.9% |
| rb_opportunity_share | weeks_7_12 | 36 | 35 | 80.0% | 14.3% | 88.3% |

Weeks 1–5 contain no alerts by construction while the four-game same-season baseline accrues. Block samples are small and should not be overinterpreted.

## Confirmed/suspected partial-game sensitivity

`PRIMARY_CONFIRMED_EXCLUDED` excludes confirmed cases and includes suspected cases. `ALL_INCLUDED` includes confirmed cases; `STRICT_SUSPECTED_EXCLUDED` also excludes suspected cases.

| partial_policy | role_family | full_alerts | full_evaluable_alerts | full_precision | precision_improvement | full_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL_INCLUDED | rb_carry_share | 61 | 47 | 66.0% | +10.9 pp | 24.5% | +7.5 pp | 75.5% |
| ALL_INCLUDED | rb_opportunity_share | 75 | 58 | 77.6% | +20.7 pp | 15.4% | +14.3 pp | 89.7% |
| PRIMARY_CONFIRMED_EXCLUDED | rb_carry_share | 60 | 47 | 66.0% | +12.9 pp | 23.1% | +9.6 pp | 79.5% |
| PRIMARY_CONFIRMED_EXCLUDED | rb_opportunity_share | 74 | 57 | 77.2% | +20.3 pp | 15.6% | +16.1 pp | 91.0% |
| STRICT_SUSPECTED_EXCLUDED | rb_carry_share | 59 | 48 | 64.6% | +11.5 pp | 23.1% | +9.6 pp | 79.2% |
| STRICT_SUSPECTED_EXCLUDED | rb_opportunity_share | 71 | 55 | 76.4% | +18.5 pp | 14.3% | +16.4 pp | 93.0% |

The RB recommendations do not change in either sensitivity. This robustness check does not change the primary policy.

## 2021–2023 direct comparison

| period | role_family | full_alerts | full_evaluable_alerts | full_precision | naive_precision | precision_improvement | full_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| redeveloped_2021 | rb_carry_share | 56 | 43 | 74.4% | 48.8% | +25.6 pp | 18.8% | +11.0 pp | 76.2% |
| redeveloped_2021 | rb_opportunity_share | 77 | 55 | 67.3% | 52.7% | +14.5 pp | 19.0% | +11.1 pp | 68.4% |
| untouched_2022 | rb_carry_share | 49 | 39 | 64.1% | 47.4% | +16.7 pp | 15.0% | +25.0 pp | 61.7% |
| untouched_2022 | rb_opportunity_share | 59 | 47 | 61.7% | 53.3% | +8.4 pp | 14.0% | +17.9 pp | 68.8% |
| untouched_2023 | rb_carry_share | 60 | 47 | 66.0% | 53.1% | +12.9 pp | 23.1% | +9.6 pp | 79.5% |
| untouched_2023 | rb_opportunity_share | 74 | 57 | 77.2% | 56.9% | +20.3 pp | 15.6% | +16.1 pp | 91.0% |

| period | role_family | direction | alerts_full | evaluable_alerts_full | precision_full | precision_naive | precision_improvement | reversion_rate_full | median_retention_full |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| redeveloped_2021 | rb_carry_share | decrease | 24 | 19 | 78.9% | 58.8% | +20.1 pp | 15.8% | 86.4% |
| redeveloped_2021 | rb_carry_share | increase | 32 | 24 | 70.8% | 41.7% | +29.2 pp | 20.7% | 73.8% |
| redeveloped_2021 | rb_opportunity_share | decrease | 33 | 22 | 63.6% | 65.2% | -1.6 pp | 11.5% | 63.3% |
| redeveloped_2021 | rb_opportunity_share | increase | 44 | 33 | 69.7% | 43.8% | +25.9 pp | 24.3% | 71.5% |
| untouched_2022 | rb_carry_share | decrease | 27 | 21 | 47.6% | 44.4% | +3.2 pp | 23.8% | 49.6% |
| untouched_2022 | rb_carry_share | increase | 22 | 18 | 83.3% | 50.0% | +33.3 pp | 5.3% | 79.1% |
| untouched_2022 | rb_opportunity_share | decrease | 32 | 24 | 54.2% | 43.5% | +10.7 pp | 18.5% | 59.5% |
| untouched_2022 | rb_opportunity_share | increase | 27 | 23 | 69.6% | 63.6% | +5.9 pp | 8.7% | 84.5% |
| untouched_2023 | rb_carry_share | decrease | 31 | 25 | 60.0% | 50.0% | +10.0 pp | 25.9% | 70.2% |
| untouched_2023 | rb_carry_share | increase | 29 | 22 | 72.7% | 55.6% | +17.2 pp | 20.0% | 83.0% |
| untouched_2023 | rb_opportunity_share | decrease | 41 | 34 | 79.4% | 59.3% | +20.2 pp | 13.5% | 95.3% |
| untouched_2023 | rb_opportunity_share | increase | 33 | 23 | 73.9% | 54.8% | +19.1 pp | 18.5% | 86.2% |

| period | role_family | seasons | season_weeks | weekly_median | weekly_maximum | zero_alert_weeks | active_weeks | weekly_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| redeveloped_2021 | rb_carry_share | 2021 | 18 | 3.0 | 8 | 5 | 13 | 3.111111111111111 |
| redeveloped_2021 | rb_opportunity_share | 2021 | 18 | 4.0 | 11 | 5 | 13 | 4.277777777777778 |
| untouched_2022 | rb_carry_share | 2022 | 18 | 2.5 | 7 | 5 | 13 | 2.7222222222222223 |
| untouched_2022 | rb_opportunity_share | 2022 | 18 | 3.5 | 9 | 6 | 12 | 3.2777777777777777 |
| untouched_2023 | rb_carry_share | 2023 | 18 | 4.0 | 8 | 5 | 13 | 3.333333333333333 |
| untouched_2023 | rb_opportunity_share | 2023 | 18 | 4.5 | 11 | 5 | 13 | 4.111111111111111 |

RB carry's 49 alerts in untouched 2022 remain a literal gate failure—an evidence-volume miss, not a performance-point failure. The 2023 pass does not rewrite that season. RB opportunity's only cross-period direction defect is the redeveloped-2021 decrease cell: 63.6% full versus 65.2% naive, a -1.6-point improvement.

## Pooled untouched 2022–2023 evidence

| role_family | full_alerts | full_evaluable_alerts | full_precision | naive_precision | precision_improvement | precision_improvement_ci_low | precision_improvement_ci_high | full_reversion_rate | reversion_improvement | full_median_retention |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | 109 | 86 | 65.1% | 50.6% | +14.5 pp | +3.5 pp | +24.9 pp | 19.6% | +16.3 pp | 73.9% |
| rb_opportunity_share | 133 | 104 | 70.2% | 55.3% | +14.9 pp | +2.4 pp | +26.1 pp | 14.9% | +16.9 pp | 79.4% |

| period | role_family | direction | alerts_full | evaluable_alerts_full | precision_full | reversion_rate_full | median_retention_full | alerts_naive | evaluable_alerts_naive | precision_naive | reversion_rate_naive | median_retention_naive | precision_improvement | reversion_improvement |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pooled_untouched_2022_2023 | rb_carry_share | decrease | 58 | 46 | 54.3% | 25.0% | 58.6% | 51 | 40 | 47.5% | 38.1% | 32.2% | +6.8 pp | +13.1 pp |
| pooled_untouched_2022_2023 | rb_carry_share | increase | 51 | 40 | 77.5% | 13.6% | 81.1% | 58 | 47 | 53.2% | 34.0% | 52.6% | +24.3 pp | +20.4 pp |
| pooled_untouched_2022_2023 | rb_opportunity_share | decrease | 73 | 58 | 69.0% | 15.6% | 76.9% | 64 | 50 | 52.0% | 35.8% | 53.8% | +17.0 pp | +20.2 pp |
| pooled_untouched_2022_2023 | rb_opportunity_share | increase | 60 | 46 | 71.7% | 14.0% | 85.3% | 69 | 53 | 58.5% | 28.1% | 59.0% | +13.2 pp | +14.1 pp |

| period | role_family | seasons | season_weeks | weekly_median | weekly_maximum | zero_alert_weeks | active_weeks | weekly_mean |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pooled_untouched_2022_2023 | rb_carry_share | 2022\|2023 | 36 | 3.0 | 8 | 10 | 26 | 3.0277777777777777 |
| pooled_untouched_2022_2023 | rb_opportunity_share | 2022\|2023 | 36 | 4.0 | 11 | 11 | 25 | 3.6944444444444446 |

Pooled results strengthen the descriptive evidence for both RB families, but do not erase individual-season failures. The pooled evidence is not used to reinterpret any locked status.

## Fold 3 gate decisions

| role_family | candidate_disposition | fold3_candidate_status | alerts | evaluable_alerts | precision | precision_improvement | reversion_rate | reversion_improvement | median_retention | failed_checks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | PRIMARY_CANDIDATE | PASSES_FOLD_3_POINT_GATES | 60 | 47 | 66.0% | +12.9 pp | 23.1% | +9.6 pp | 79.5% | — |
| rb_opportunity_share | SHADOW_CANDIDATE | FAILS_FOLD_3_POINT_GATES | 74 | 57 | 77.2% | +20.3 pp | 15.6% | +16.1 pp | 91.0% | direction_consistent_across_periods |
| wr_target_share | RETIRED_DESCRIPTIVE_ONLY | NOT_APPLICABLE_RETIRED | 27 | 23 | 26.1% | +4.3 pp | 42.3% | +11.5 pp | 25.0% | min_holdout_alerts \| min_persistence_precision \| min_absolute_improvement_vs_naive \| max_immediate_reversion_rate \| min_median_retention \| direction_consistent_across_periods |
| te_target_share | RETIRED_DESCRIPTIVE_ONLY | NOT_APPLICABLE_RETIRED | 4 | 4 | 50.0% | -50.0 pp | 25.0% | -25.0 pp | 47.2% | min_holdout_alerts \| min_persistence_precision \| min_absolute_improvement_vs_naive \| min_reversion_improvement_vs_naive \| min_median_retention \| min_alerts_per_week \| direction_consistent_across_periods |

WR and TE rows are archival continuity only. Their candidate status is `NOT_APPLICABLE_RETIRED`, regardless of incidental 2023 point estimates.

## Recommended next action

| role_family | recommendation | reason |
| --- | --- | --- |
| rb_carry_share | Advance unchanged to Fold 4 | Passed every unchanged Fold 3 point gate on 60 alerts; both directions beat equal-volume naive in 2023 and across available periods. This is advancement evidence, not validation. |
| rb_opportunity_share | Continue shadow evaluation unchanged | Strong 2023 and pooled untouched results, but the unchanged cross-period direction gate fails because 2021 decreases underperformed equal-volume naive by 1.6 points. |

No redevelopment was performed. Advancing RB carry means testing this exact frozen candidate in a later separately authorized Fold 4; it does not authorize that execution here.

## Limitations

- This is a historical development-fold holdout, not prospective validation.
- RB carry has 47 evaluable 2023 alerts; its +12.9-point lift interval spans -3.1 to +26.3 points.
- RB opportunity's 2023 lift is strong, but the locked all-period direction check is literal and fails on the 2021 decrease cell.
- The complete deduplicated feed includes retired WR/TE archival alerts; any production feed would need a separately authorized disposition implementation.
- Receiver-ID population is measured across pass attempts, including plays with no target; canonical target opportunities require a resolved receiver.
- nflverse source extracts can be revised upstream; source file hashes are recorded.
- The public dashboard was not changed, tested, merged, pushed, or deployed.
