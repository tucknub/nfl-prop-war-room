# PropWar Role-Change Validation Protocol

**Version:** 1.0.0  
**Status:** PRECOMMITTED — edit history must be preserved  
**Historical window:** 2018–2025  
**First prospective season:** 2026  
**Primary product claim under test:** PropWar can identify persistent NFL player-role changes more accurately than an equal-volume naive one-week spike ranking.

---

## 1. Purpose

This protocol governs the first real PropWar deliverable. No public Role-Change Feed or polished replacement UI may be built until the validation work is complete.

PropWar may always display observable facts, such as:

> A player's carry share rose from 42% to 61%.

PropWar may not publicly make an automated persistence claim, such as:

> The player gained a sustainable lead role.

unless the applicable role family passes this protocol.

---

## 2. Why 2018 Is the Starting Year

2018 is an **operational modern-era cutoff**, not a claimed single football rule-change boundary.

The data audit must document:

1. Column availability and meaning by season.
2. Player/team identity coverage.
3. Play-context coverage needed for normal-game classification.
4. Distribution shifts in team play volume and positional opportunity.
5. Whether 2017 is equally complete and comparable.

If 2017 is equally clean and materially improves evidence without introducing unacceptable era drift, it may be added during development **before rules are frozen**. The report must state whether the cutoff was driven by football comparability, data integration quality, or both.

The public product may default to 2022–present even though validation uses earlier seasons.

---

## 3. Validation Sequence

### Development folds

| Fold | Development seasons | Test season | Use of results |
|---|---|---:|---|
| 1 | 2018–2020 | 2021 | May diagnose and revise |
| 2 | 2018–2021 | 2022 | May diagnose and revise |
| 3 | 2018–2022 | 2023 | May diagnose and revise |
| 4 | 2018–2023 | 2024 | May diagnose and revise |

After Fold 4, freeze:

- Normal-game definition
- Role-family metric definitions
- Minimum samples
- Baseline windows
- Candidate scoring logic
- Alert-volume rules
- Persistence definitions
- Release gates

### Final historical holdout

| Development seasons | Holdout |
|---|---:|
| 2018–2024 | 2025 |

**Locked rule:** 2025 results may not be used to change the version being judged on 2025.

A revised method after viewing 2025 is exploratory and must be tested prospectively in 2026 or later.

### Prospective confirmation

All 2026 alerts must be generated, timestamped, and archived before their outcome games. No alert may be deleted or rewritten after publication or shadow generation.

---

## 4. Initial Role Families

### Primary release candidates

1. RB carry-share increase/decrease
2. RB opportunity-share increase/decrease
3. WR target-share increase/decrease
4. TE target-share increase/decrease

### Exploratory only until separately validated

- Inside-five role transfers
- Goal-line role transfers
- Red-zone target-share changes
- Third-down usage changes
- Two-minute usage changes
- QB role families

Each family is evaluated separately. A strong result in one family cannot rescue another.

---

## 5. Required Weekly Grain

The canonical validation input is one row per:

`season × week × player_id × team × role_family`

Required fields:

- `season`
- `week`
- `player_id`
- `player_name`
- `team`
- `position`
- `role_family`
- `metric_all`
- `metric_normal`
- `raw_opportunities_all`
- `raw_opportunities_normal`
- `team_opportunities_all`
- `team_opportunities_normal`
- `qualifying_game`
- `partial_game_flag`
- `data_quality_pass`

Optional context fields:

- `active_status`
- `starter_status`
- `teammate_availability`
- `snap_share`
- `route_share`
- `late_backup_flag`
- `source_version`

Shares must be stored as decimals in `[0, 1]`.

---

## 6. Normal-Game Classification

The pipeline must retain separate context flags. It must not overwrite or discard all-game usage.

### Primary normal-game definition

A play is eligible for `normal_game` when all are true:

- Regulation period (`qtr <= 4`)
- Not a kneel or spike
- Not classified as obvious garbage time
- Not flagged as a late-backup-only play by a trustworthy source

### Primary garbage-time rule

- Third quarter: absolute score differential `>= 24`
- Fourth quarter: absolute score differential `>= 17`

Two-minute and clock-killing plays receive separate flags. Competitive two-minute usage remains part of normal-game usage unless it also meets garbage-time criteria.

### Mandatory sensitivity checks

- Q3 threshold: 21, 24, 28
- Q4 threshold: 14, 17, 21
- Include versus exclude competitive two-minute usage
- Include versus exclude overtime

The primary definition must be frozen before the 2025 holdout. Sensitivity results do not replace the primary result.

---

## 7. Qualifying Games and Exclusions

A player-week is not eligible to trigger or evaluate an alert when:

- The player exited early and the role metric is not representative
- Identity resolution failed
- The team-opportunity denominator is zero or incomplete
- The game partition is incomplete
- The player appeared only in late-backup possessions, when reliably identified
- The required role-family metric is missing
- A join duplicated the player-week grain
- `data_quality_pass` is false

Injury-affected rows must be retained in an exclusion ledger with a reason code.

---

## 8. Detection Methods Compared

Every role family must compare:

1. **Naive one-week spike:** current metric minus prior baseline
2. **Two-week raw trend:** current two-game average minus prior baseline
3. **Normal-game filtered trend:** same calculation using `metric_normal`
4. **Full PropWar detector:** normal-game trend plus frozen sample, persistence, concentration, and quality safeguards

The naive methods and PropWar must produce the **same alert count within each family and week**. Baselines select their top-scoring eligible rows to match the number of PropWar alerts.

---

## 9. Primary Persistence Outcome

Let:

- `B` = pre-alert baseline
- `D` = detected role value
- `F` = average role value in the next two qualifying games
- `Δ = D - B`

For an increase:

`retention = (F - B) / Δ`

For a decrease:

`retention = (B - F) / (B - D)`

A role change is **persistent** when retention is at least `50%`.

### Why 50%

A weekly alert is decision-useful only when a meaningful portion of the detected role change survives beyond the triggering game. Retaining less than half means the alert mostly described a temporary spike or dip.

Mandatory sensitivity reporting: 40%, 50%, and 60%.  
The locked primary definition remains 50%.

---

## 10. Immediate Reversion

Immediate reversion occurs when the next qualifying game retains less than `25%` of the detected change.

### Why 25%

If more than one-quarter of public alerts immediately return near baseline, the feed will routinely mistake weekly variance for structural change.

---

## 11. Release Gates and Rationale

### Full public release — per role family

| Requirement | Gate | Reason |
|---|---:|---|
| Holdout alerts | `>= 50` | Enough evidence for a normal public claim |
| Persistence precision | `>= 60%` | Alert is more often persistent than misleading |
| Equal-volume improvement vs naive | `>= 10 percentage points` | Complexity must create noticeable practical value |
| Immediate reversion rate | `<= 25%` | Prevent frequent variance-as-change errors |
| Reversion improvement vs naive | `>= 8 percentage points` | Safeguards must outperform simple ranking |
| Median two-game retention | `>= 50%` | Surviving changes must remain materially large |
| Average family alert frequency | `>= 0.5 per NFL week` | Family must be useful often enough to justify a feed |
| Direction consistent across periods | Required | Avoid one-season-only success |
| Frozen before holdout | Required | Prevent hindsight tuning |

### Experimental evidence tier

- 25–49 holdout alerts
- Meets point-estimate performance gates
- Directionally consistent across development tests and holdout
- May appear only in Research/Admin with an explicit limited-evidence label

### Insufficient evidence

- Fewer than 25 holdout alerts
- Descriptive statistics are allowed
- Automated persistence claims are not allowed

### Feed-level volume

When multiple validated families are active:

- Target seasonal median: 5–15 alerts per NFL week
- Hard normal-week maximum: 20
- A partial release may produce fewer alerts and must be named narrowly

---

## 12. Statistical Reporting

Every method-family-season result must include:

- Alert count
- Persistence precision
- 95% bootstrap confidence interval
- Immediate reversion rate
- Median retention
- Equal-volume naive result
- Absolute and relative improvement
- Confidence interval for the improvement
- Weekly alert-volume distribution

Uncertainty affects wording strength but does not move the precommitted point gates.

---

## 13. Required Robustness Tests

Secondary analyses:

- Retention: 40%, 50%, 60%
- Horizon: next 1, 2, 4 qualifying games
- Baseline: prior 2, prior 4, season-to-date
- Context: all-game versus normal-game
- Injury rows: included versus excluded
- Minimum raw-opportunity thresholds

These tests diagnose fragility. They cannot override a failed primary analysis.

---

## 14. Failure Policy

### Family fails 2025

- Do not release automated role-change claims for that family in 2026
- Fold 2025 into development
- Revise using 2018–2025
- Run revised family in 2026 shadow mode
- Timestamp and preserve every alert
- Public release requires at least 25 prospective alerts across at least 8 NFL weeks and the same performance gates

### Partial success

Release only passing families. Name the product narrowly enough to match the evidence.

### Every family fails

No automated Weekly Role-Change Feed. Descriptive features may still ship:

- Actual Depth Charts
- Team Opportunity Maps
- Player Role Profiles
- Normal-game versus all-game usage
- Game Usage Box Scores
- Red-zone usage tables

### Allowed language after failure

Allowed:

> Carry share increased from 42% to 61%.

Not allowed:

> The player gained a sustainable lead role.

---

## 15. Opponent Context Policy

Opponent adjustment is excluded from the MVP and may never ship.

It may return only if it:

- Improves next-game opportunity prediction MAE by at least 3%
- Improves at least two position groups
- Improves in validation and holdout
- Beats role/team/game-script baselines
- Uses shrinkage and visible uncertainty
- Separates volume from efficiency

“Never” is an acceptable outcome.

---

## 16. Required Artifacts

1. `ROLE_CHANGE_VALIDATION_PROTOCOL.md`
2. Frozen configuration YAML and SHA-256 fingerprint
3. Reproducible notebook
4. Machine-readable alert archive
5. Exclusion ledger
6. Per-family release table
7. False-positive case review
8. 2026 prospective alert ledger

---

## 17. UI Gate

Do not build the replacement public interface before:

- Input data passes the audit
- Fold 1 executes reproducibly
- The 2025 frozen holdout is complete
- At least one family earns release or experimental status

A descriptive Detroit prototype may be built later, but it cannot imply validated persistence before the applicable family passes.
