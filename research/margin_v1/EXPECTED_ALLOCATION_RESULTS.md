# NFL Margin Pool — Expected Allocation Audit

Date: 2026-08-23

## Why this audit was necessary

Earlier Margin Pool research showed large historical **realized-score** gains for the rolling long/slow allocator. That result is descriptive, but realized game margin is extremely noisy over only 17–18 selections per season. A strategy can look excellent because its chosen teams happened to outperform their sportsbook spreads by unusually large amounts.

This audit separates three quantities:

1. **Selected market sum** — the sum of the actual current-week closing spreads on teams the strategy ultimately selected.
2. **Walk-forward calibrated expected margin** — each selected spread translated through the residual-centered historical margin model using only earlier-season data.
3. **Realized residual** — actual selected point differential minus selected market sum.

The first two are the primary allocation-quality measures. Realized score remains a useful stress test, but it is not sufficient evidence of strategy edge by itself.

## Test period

2011–2025, because the expected-margin calibration and future-line correction models require earlier seasons for walk-forward training.

Calibrated expected margin was evaluated at empirical-sampler bandwidths **1.5, 3.0, and 4.0** to avoid depending on one tuned bandwidth.

## Allocation-quality summary

| Strategy | Actual score | Selected market sum | Realized minus market | EV BW 1.5 | EV BW 3.0 | EV BW 4.0 |
|---|---:|---:|---:|---:|---:|---:|
| Biggest Favorite | 174.33 | 176.87 | -2.53 | 185.83 | 185.16 | 183.92 |
| Raw long/slow | **206.07** | 177.40 | **+28.67** | 185.01 | 184.22 | 183.55 |
| Recalibrated long/slow | 188.13 | 178.40 | +9.73 | 186.09 | 185.11 | 184.50 |
| **Long/slow + core future style** | 186.00 | **181.30** | +4.70 | **188.82** | **188.28** | **187.64** |
| Long/slow + style + turnover | 186.47 | 181.07 | +5.40 | 188.54 | 188.04 | 187.40 |
| Closing-line hindsight allocator | 182.73 | 195.20 | -12.47 | 201.67 | 202.09 | 201.83 |

## Critical correction to the earlier long/slow headline

Raw long/slow's historical actual score of **206.07** was not supported by a similarly large market-allocation advantage. Its selected current-week spreads summed to only **177.40**, just **0.53 points/season** above Biggest Favorite's **176.87**.

Raw long/slow instead realized **+28.67 points/season above its own selected market expectation**. Biggest Favorite was approximately centered around the market at **-2.53 points/season**.

Therefore the previously reported large realized-score advantage for raw long/slow **must not be interpreted as proof of allocation skill**. Much of that historical result came from favorable realized game-margin residuals.

This changes the research standard: production strategy decisions should be judged primarily by leakage-safe expected allocation value and later championship simulation, with historical realized score as a secondary robustness check.

## Does future style improve allocation versus raw long/slow?

Yes.

Core future style improved the eventual selected market sum by **+3.90 points/season** versus raw long/slow. The season-bootstrap interval was approximately **+1.13 to +6.90**, entirely positive.

Walk-forward calibrated EV gains versus raw long/slow were also positive at every tested sampler bandwidth:

| Calibration | Mean EV gain | 95% bootstrap interval | 2021–2025 gain |
|---|---:|---:|---:|
| BW 1.5 | **+3.81** | +0.92 to +6.76 | +5.65 |
| BW 3.0 | **+4.06** | +1.25 to +7.07 | +5.99 |
| BW 4.0 | **+4.09** | +1.26 to +7.17 | +6.00 |

The style allocator had worse historical **realized** outcomes than raw long/slow, but raw long/slow's extreme positive realized residual explains the conflict. On the measures intended to represent allocation quality in expectation, style clearly improved the raw allocator.

## Does style beat Biggest Favorite?

Across the full 2011–2025 audit, yes in expected allocation value:

- Selected market sum: **+4.43 points/season** versus Biggest Favorite; bootstrap interval approximately **+0.73 to +8.67**.
- Calibrated EV BW 1.5: **+2.99**, interval +0.35 to +6.02.
- Calibrated EV BW 3.0: **+3.11**, interval +0.25 to +6.27.
- Calibrated EV BW 4.0: **+3.72**, interval +0.48 to +7.26.

However, the exact modern 18-week era is a serious caution.

### 2021–2025

Core style versus Biggest Favorite:

- Selected market sum: **-1.10 points/season**.
- Calibrated EV BW 1.5: **-0.68**.
- Calibrated EV BW 3.0: **-1.05**.
- Calibrated EV BW 4.0: **-1.13**.

So the advanced allocator has **not yet demonstrated expected-value superiority over Biggest Favorite in the five-season exact 18-week sample**.

The same style layer did improve raw long/slow by roughly **+6 EV points/season** in 2021–2025. The remaining problem is the allocator's decision rule, not the usefulness of the future-line style forecast itself.

## How much allocation opportunity remains?

A hindsight optimizer using every eventual closing line had an average selected-market advantage of **+18.33 points/season** over Biggest Favorite.

- Raw long/slow captured only **+0.53 points**, about **2.9%** of that hindsight market-allocation gap.
- Core style captured **+4.43 points**, about **24.2%** of the hindsight gap.

The hindsight optimizer is not deployable and is not a fair performance benchmark; it only establishes that meaningful one-use allocation opportunity exists.

## Turnover decision

Turnover form added only a tiny improvement to future-line forecast MAE and did not improve full-period expected allocation over core style. Its stronger 2021–2025 numbers come from only five seasons.

**Decision: do not add turnover as a production feature yet.** Core EPA/pass/rush/YPP/explosive style remains the simpler validated future-line layer.

## Research decision

1. **Retract the interpretation that raw long/slow's large realized historical score proves a large allocation edge.** It does not.
2. **Keep weekly reoptimization.** The locked Week-1 plan remains clearly inferior and future team values change materially over the season.
3. **Keep sportsbook spread as the current-week truth.** Current-game EPA/style failed to improve it.
4. **Keep core team style for future-week line forecasting.** It materially improves future closing-line MAE and expected allocation versus raw long/slow.
5. **Do not production-lock the current style allocator yet.** It improves full-history expected allocation versus Biggest Favorite but does not beat Biggest Favorite on expected value in 2021–2025.
6. **Next gate:** build a Biggest-Favorite-anchored allocator that deviates only when the modeled remaining-season calibrated-EV advantage is large enough to justify the deviation. Thresholds must be evaluated with a development/later-period split rather than chosen from the same full sample.
