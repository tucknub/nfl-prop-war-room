# PropWar Role-Change Validation V1 — Data Audit and Fold 1

**As of:** 2026-07-13
**Branch:** `role-change-validation-v1`
**Overall assessment:** **Needs revision**
**Detector claim:** **Not supported.** No family passes all Fold 1 point-gate diagnostics, and the combined alert volume exceeds the protocol maximum.

Fold 1 is a development test, not the frozen 2025 holdout. The release gates below are used only as diagnostics and were not changed.

## 1. Repository data inventory at start

| file | rows | seasons | status_at_start |
| --- | --- | --- | --- |
| data/raw/pbp.csv | 147928 | 2023, 2024, 2025 | present before role-validation integration |
| data/raw/weekly.csv | 57045 | 2023, 2024, 2025 | present before role-validation integration |
| data/raw/rosters.csv | 9443 | 2023, 2024, 2025 | present before role-validation integration |
| data/raw/schedules.csv | 855 | 2023, 2024, 2025 | present before role-validation integration |

The local repository initially contained only 2023–2025 raw history. It also contained derived weekly/player/model outputs, but no canonical `season × week × player_id × team × role_family` table and no 2018–2022 raw partitions.

## 2. Season and schema coverage

| season | pbp_rows | pbp_games | schedule_games | regular_weeks | player_stat_rows | player_stats_game_id_missing_rate | roster_rows | snap_rows | injury_rows | scrimmage_plays | participation_play_coverage | carry_player_id_coverage | target_player_id_coverage | complete_schema_and_games |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2017 | 45268 | 256 | 256 | 17 | 16786 | 0.000000 | 49210 | 22876 | 4949 | 32315 | 0.999938 | 1.000000 | 0.922291 | True |
| 2018 | 45120 | 256 | 256 | 17 | 16728 | 0.000000 | 50113 | 22895 | 4961 | 32124 | 0.999938 | 1.000000 | 0.909896 | True |
| 2019 | 45339 | 256 | 256 | 17 | 16663 | 0.000000 | 49561 | 22884 | 5202 | 32402 | 1.000000 | 1.000000 | 0.899895 | True |
| 2020 | 45406 | 256 | 256 | 17 | 16774 | 0.000000 | 41972 | 23790 | 5414 | 32855 | 1.000000 | 1.000000 | 0.907842 | True |
| 2021 | 47651 | 272 | 272 | 18 | 18128 | 0.000000 | 44539 | 25271 | 5348 | 34344 | 1.000000 | 1.000000 | 0.908026 | True |
| 2022 | 47157 | 271 | 271 | 18 | 17981 | 0.000000 | 44059 | 25168 | 5450 | 34028 | 1.000000 | 1.000000 | 0.896498 | True |
| 2023 | 47399 | 272 | 272 | 18 | 17806 | 0.000000 | 43545 | 25329 | 5451 | 34237 | 1.000000 | 1.000000 | 0.889352 | True |
| 2024 | 47274 | 272 | 272 | 18 | 18128 | 0.000000 | 44473 | 25398 | 5954 | 33701 | 1.000000 | 1.000000 | 0.892872 | True |
| 2025 | 46452 | 272 | 272 | 18 | 18539 | 0.000000 | 44697 | 25395 | 5783 | 33241 | 1.000000 | 1.000000 | 0.890706 | True |

- 2018–2021 and 2023–2025 have every played regular-season game in both PBP and schedules.
- 2022 has 271 played games rather than 272 because Buffalo–Cincinnati was canceled; the played-game partitions are internally complete.
- 2024 `data/raw/weekly.csv` initially had `game_id` missing on 100% of rows. The canonical builder does not mutate that public-pipeline input; it uses PBP/schedule `game_id`, where coverage is complete.
- Receiver ID presence on all pass attempts is not expected to be 100% because sacks and throwaways are pass attempts without a target. Actual target rows require a receiver ID.

### Why 2018 remains the start

The actual schema does **not** create a quality break at 2018. 2017 has 256/256 games, the same 372-column PBP schema, and 99.9938% offensive-play participation coverage versus 99.9938% in 2018. The cutoff therefore remains an operational/precommitted modern-era boundary, not a data-availability boundary. This Fold did not add 2017 because `LOCKED_DECISIONS.md` fixes 2018–2025 and Fold 1 explicitly develops on 2018–2020. A 2017 sensitivity can be considered only with an explicit documented protocol amendment before rules are frozen.

## 3. Canonical metric definitions and leakage controls

- `rb_carry_share`: player RB non-kneel, non-two-point carries / all team non-kneel, non-two-point carries.
- `rb_opportunity_share`: player RB carries + targets / all team RB carries + targets.
- `wr_target_share` and `te_target_share`: player targets / all team targets.
- `metric_all` retains competitive, garbage-time, and overtime usage; kneels, spikes, aborted/deleted plays, and two-point attempts are not role opportunities.
- `metric_normal` excludes overtime, Q3 absolute score differential ≥24, Q4 differential ≥17, kneels/spikes, and trustworthy late-backup flags when available. Competitive two-minute usage remains included.
- Baselines use only prior qualifying games. Fold tuning reads 2018–2020 only. Future outcomes are restricted to later qualifying games in the same 2021 season; no 2022 outcome can enter Fold 1.
- Player identity uses season-week-team GSIS joins from player stats and weekly rosters. Participation creates the player universe, retaining zero-opportunity players and preventing survivorship bias.

## 4. 2018–2020 data audit

- Canonical rows: **20,727**.
- Duplicate canonical keys: **0 (0.0000%)**.
- Required key/metric missingness: **0** for player ID, name, team, position, `metric_all`, and `metric_normal`.
- Quality/qualifying pass: **97.9930%** (20,311/20,727).
- Excluded canonical rows: **416**; all are conservative `INCOMPLETE_GAME_PARTITION` exclusions caused by sub-99% participation coverage in affected team-games (225 rows in 2018, 191 in 2019, none in 2020).
- Opportunity-to-identity joins: **100%** in each audited season. Participating-player identity coverage: 99.0464% (2018), 99.0077% (2019), and 100% (2020); unmatched participants were non-role/metadata rows and never became canonical role rows.
- PBP versus weekly stat reconciliation is 99.58%–99.97% exact by player row after the confirmed two-point-conversion fix. Remaining count differences are 1–11 season-total opportunities and reflect upstream stat correction/lateral attribution differences, not join multiplication.
- Primary normal-game definition retains **88,047/97,381** scrimmage plays; the threshold sensitivity table is preserved in `normal_game_sensitivity_2018_2020.csv`.

### Required-field limitations

- **High blocker — partial-game exits:** no trustworthy in-game exit field exists in PBP, participation, snaps, weekly rosters, or injury reports. `partial_game_flag` is present and conservatively false but is explicitly marked unreliable. Using next-week injury reports creates look-ahead; using outcome-correlated snap drops risks excluding genuine role decreases.
- **Medium caveat — late backups:** no trustworthy late-backup-only flag exists. The protocol allows this exclusion only when reliably identified, so it remains false and marked unreliable.
- Optional `active_status` is missing on 2.94% of 2018 canonical rows and 2.80% of 2019 rows; identity, position, opportunity, and share fields are complete.

## 5. Fold 1 setup

Development-selected parameters (selected only on 2018–2020):

| role_family | baseline_window | min_baseline_games | min_abs_delta | development_evaluable_alerts | development_precision_improvement |
| --- | --- | --- | --- | --- | --- |
| rb_carry_share | 4 | 4 | 0.1500 | 474 | 0.1434 |
| rb_opportunity_share | 4 | 4 | 0.1500 | 534 | 0.1125 |
| wr_target_share | 4 | 3 | 0.1200 | 170 | 0.2412 |
| te_target_share | 6 | 4 | 0.1100 | 52 | 0.1735 |

The development selector required at least 25 evaluable alerts and ranked candidates by equal-volume precision improvement, precision, lower reversion, retention, and evidence count. This is a development-selection rule only; it does not alter any release gate.

## 6. Fold 1 results — 2021

| role_family | full_alerts | full_evaluable_alerts | full_precision | naive_precision | precision_improvement | precision_improvement_ci_low | precision_improvement_ci_high | full_reversion_rate | reversion_improvement | full_median_retention | all_point_gates_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rb_carry_share | 273 | 222 | 0.5721 | 0.4932 | 0.0789 | 0.0213 | 0.1406 | 0.2815 | 0.0643 | 0.6573 | False |
| rb_opportunity_share | 324 | 256 | 0.5859 | 0.5175 | 0.0684 | 0.0018 | 0.1433 | 0.3014 | 0.0213 | 0.6426 | False |
| te_target_share | 35 | 25 | 0.2000 | 0.2692 | -0.0692 | -0.2046 | 0.0667 | 0.5000 | -0.0455 | 0.1660 | False |
| wr_target_share | 85 | 59 | 0.4407 | 0.2951 | 0.1456 | 0.0151 | 0.2725 | 0.4730 | 0.0613 | 0.4002 | False |

- Equal-volume verification: **True** across **72** family-weeks; every full-detector count exactly matches each baseline count.
- Full-detector alerts: **717** total; **562** evaluable for the two-game outcome.
- Combined alert volume: mean **39.83**, median **38**, range **27–59** per week. This fails the protocol target of 5–15 and hard normal-week maximum of 20.

Interpretation by family:

- RB carry share: precision 57.21%, +7.89 pp versus naive, 28.15% immediate reversion. It misses the 60%, +10 pp, ≤25%, and +8 pp gates.
- RB opportunity share: precision 58.59%, +6.84 pp, 30.14% reversion. It misses the same four gates.
- WR target share: +14.56 pp improvement, but only 44.07% precision, 47.30% reversion, and 40.02% median retention.
- TE target share: 35 alerts, 20.00% precision, negative improvement, 50.00% reversion, and 16.60% median retention.

**Conclusion:** Fold 1 does not support saying that the detector works. Normal-game filtering is directionally useful for some RB/WR comparisons, but the full detector adds little over the normal-game trend and fails multiple precommitted point gates.

## 7. Confirmed fixes only

1. Excluded two-point conversions from carries/targets after reconciliation proved they inflated PBP counts.
2. Separated all-game raw, normal-game trend, and full-detector method inputs; the supplied scaffold mislabeled the same normal metric as raw and normal.
3. Retention now uses the actual detected role value, not the penalized ranking score.
4. Future outcomes cannot cross into the next season/fold.
5. Prior baselines skip nonqualifying rows and use prior qualifying games.
6. Source-cache and gzip artifact writes are atomic/deterministic.

No release gate changed. Integrity check: **True**.

## 8. Blockers and next decisions

1. Obtain or precommit a defensible contemporaneous partial-game exit source/rule before any public persistence claim.
2. Diagnose excessive alert volume and revise only in later development folds; do not tune on 2025.
3. Investigate why full safeguards barely improve on `normal_game_trend`, especially for RB families.
4. Keep WR and TE persistence claims disabled; TE is both low-evidence and materially poor in Fold 1.
5. Complete Folds 2–4, freeze rules, then run the untouched 2025 holdout. This report makes no 2025 release judgment.

## 9. Artifact integrity

- Canonical rows/hash: `57928` / `11d57cdde92238024da8afbedabe124da746250aa9a2026422014382ccc14e90`
- Protocol SHA-256: `b9fcc357e98388bb15c2d7ae853620f8ccd6c2e60e491a6cfcb990bbfbfcadbe`
- Locked decisions SHA-256: `57da1e3ebed077bd52709fb3331eb99e719c056e9e840d8c6913b512d7e4ba00`
- Reproducible notebook: `notebooks/role_change_validation.ipynb`
- Alert archive: `outputs/role_validation/fold_1/alerts_2021.csv.gz`
- Exclusion ledger: `outputs/role_validation/exclusion_ledger.csv`
