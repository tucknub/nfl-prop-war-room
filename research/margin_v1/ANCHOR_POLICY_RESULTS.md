# Biggest-Favorite-Anchored Calibrated-EV Policy

Date: 2026-08-23

## Goal

The prior future-style allocator improved future-line forecasts and full-history expected allocation, but it still trailed Biggest Favorite slightly on expected allocation in the exact 2021–2025 18-week sample.

This gate changed the decision rule rather than adding more predictive features.

Every week:

1. **Biggest Favorite among the policy's unused teams is the anchor/default.**
2. Current-week value uses the actual current sportsbook spread translated through the walk-forward residual-centered expected-margin calibration.
3. Future-week values use long/slow market power + validated frozen core style, then the same calibrated-EV transform.
4. For every current candidate, calculate:
   `current calibrated EV + optimal feasible future calibrated EV`.
5. Deviate from the anchor only when the best alternate's remaining-season total exceeds the anchor path by at least a threshold.
6. Weeks 1–3 stay on Biggest Favorite because the validated in-season style layer does not yet have enough prior games.
7. Reoptimize from scratch the next week with the new used-team inventory.

Policy calibration bandwidth was pre-set to **3.0** from the promoted empirical margin distribution rather than selected from this policy test.

## Threshold selection protocol

Thresholds tested: **0, 0.5, 1, 2, 3, 5, 8, 999** expected points.

- Threshold selection period: **2011–2020**.
- Selection criterion declared in code before inspecting later-period output: maximize mean BW=3 calibrated-EV gain versus Biggest Favorite; ties prefer the larger/more conservative threshold.
- Later reporting period: **2021–2025**.
- The later period is **not a pristine untouched holdout**, because prior research had already inspected these seasons repeatedly. It is still useful as a fixed later-period check because the threshold itself was chosen only from 2011–2020 in this gate.
- Threshold 999 is a sanity path and must exactly reproduce Biggest Favorite.

## Threshold grid

| EV threshold | 2011–20 EV gain BW3 | Avg deviations | 2021–25 EV gain BW3 | Avg deviations | Full EV gain BW3 |
|---|---:|---:|---:|---:|---:|
| 0.0 | +5.67 | 4.0 | +0.85 | 2.8 | +4.07 |
| **0.5** | **+6.47** | 3.7 | **+2.87** | 2.4 | **+5.27** |
| 1.0 | +5.63 | 3.5 | +2.77 | 2.2 | +4.67 |
| 2.0 | +3.34 | 2.6 | +2.63 | 1.8 | +3.11 |
| 3.0 | +2.29 | 1.8 | +3.06 | 1.6 | +2.55 |
| 5.0 | +0.70 | 0.3 | +1.57 | 0.4 | +0.99 |
| 8.0 | +0.52 | 0.1 | 0.00 | 0.0 | +0.35 |
| 999 | 0.00 | 0.0 | 0.00 | 0.0 | 0.00 |

**Development-selected threshold: 0.5 expected points.**

## Development period: 2011–2020

Threshold 0.5 versus Biggest Favorite:

- Selected market value: **+6.75 points/season**, bootstrap interval approximately **+3.15 to +10.30**.
- Calibrated EV BW 1.5: **+7.23**, interval +3.36 to +11.12.
- Calibrated EV BW 3.0: **+6.47**, interval +2.89 to +9.93.
- Calibrated EV BW 4.0: **+6.71**, interval +3.07 to +10.25.
- Positive EV seasons: **8 of 10**.
- Average deviations from the weekly anchor: **3.7 per season**.
- Average cumulative current-spread sacrifice: **7.05 points/season**.
- Maximum single-week current-spread sacrifice: **17.5 points**.
- Actual historical score difference: +9.8/season, but the confidence interval crosses zero and actual score is not the primary selection criterion.

## Later exact 18-week period: 2021–2025

Without changing the development-selected 0.5 threshold:

- Selected market value: **+2.80 points/season** versus Biggest Favorite.
- Calibrated EV BW 1.5: **+3.17**.
- Calibrated EV BW 3.0: **+2.87**.
- Calibrated EV BW 4.0: **+2.88**.
- EV-positive seasons: **3 of 5**.
- Average deviations: **2.4 per season**.
- Average cumulative current-spread sacrifice: **6.7 points/season**.
- Maximum single-week sacrifice: **7.0 points**.
- Actual historical score difference: +3.2/season, with extremely wide uncertainty.

Because only five seasons are available, later-period bootstrap intervals remain wide and cross zero. This is therefore **positive evidence, not statistical proof**.

## Full 2011–2025

Threshold 0.5:

- Selected market value gain: **+5.43 points/season**, interval approximately +2.30 to +8.53.
- Calibrated EV BW 1.5: **+5.87**, interval +2.63 to +9.09.
- Calibrated EV BW 3.0: **+5.27**, interval +2.15 to +8.32.
- Calibrated EV BW 4.0: **+5.43**, interval +2.24 to +8.57.
- Positive EV seasons: **11 of 15**.
- Average deviations: **3.27 per season**.

This is materially stronger expected-allocation evidence than the previous raw long/slow or unrestricted style policy.

## Sanity check

Threshold 999 reproduced Biggest Favorite exactly:

- maximum absolute selected-market difference: **0.0**;
- maximum absolute BW=3 EV difference: **0.0**;
- maximum absolute actual-score difference: **0.0**.

The anchor implementation therefore passed its baseline reproduction check.

## Remaining concern: extreme current sacrifice

The development-selected policy once accepted a **17.5-point current spread sacrifice** because the modeled remaining-season value of preserving the anchor was still higher by more than 0.5 expected points.

That behavior is mathematically possible under the current objective but operationally concerning because future-line forecasts are uncertain. The policy should not be production-locked until this tail behavior is addressed.

The modern 2021–2025 maximum sacrifice was a much smaller **7.0 points**, but that does not erase the historical failure mode.

## Research decision

1. **Biggest-Favorite anchoring is a meaningful improvement to the decision policy.** It converts the modern-era expected-allocation result from slightly negative under the unrestricted style allocator to a positive point estimate.
2. **Threshold 0.5 is the development-selected candidate**, not a final production constant.
3. **The modern result is encouraging but underpowered.** Five seasons cannot establish a narrow confidence interval.
4. **Do not use realized score to choose the policy.** Expected market value and walk-forward calibrated EV remain primary.
5. **Next gate:** retain the 0.5 development-selected EV threshold and test robustness controls on current-week sacrifice / forecast uncertainty. The goal is to remove extreme 17.5-point sacrifices without destroying the expected allocation gain. Do not retune the EV threshold from the 2021–2025 results.
