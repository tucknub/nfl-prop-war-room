# NFL Margin Pool V1 — Research Checkpoint

Date: 2026-08-23

## Scope

Historical NFL regular-season research for a pool in which one team is selected each week, each team can be used at most once, and weekly score is that team's actual game point differential.

All deployable historical decisions are reconstructed without future-week closing lines. Current-week sportsbook information may be used when it existed; future weeks must be forecast from information available at the historical decision point. Hindsight closing-line and actual-result optimizers are reference bounds only.

> **Critical research correction:** historical realized Margin Pool scores are too noisy to serve as the primary evidence of allocation skill. The raw long/slow allocator's large historical actual-score advantage was driven heavily by unusually favorable realized margins relative to the spreads of the teams it selected. The primary strategy evidence is now **selected market value + walk-forward calibrated expected margin**, with realized score retained as a secondary stress test.

## What remains strongly supported

### Weekly reoptimization

A one-time Week-1 allocation plan performed very poorly.

Across 2006–2025:

- Static Week-1 plan mean actual score: **113.8**
- Biggest Favorite: **179.65**
- Default rolling allocator: **201.9**
- Rolling beat the static plan in **19 of 20** seasons.

In 2021–2025:

- Static: **104.4**
- Biggest Favorite: **178.4**
- Default rolling: **212.6**

The preseason path is therefore a reservation map, not a commitment. Used-team inventory and future valuations should be rebuilt every week.

### Current-week sportsbook spread

The current market remains the best V1 current-game anchor.

A leakage-safe four-game entering-form model using EPA/play, passing EPA, rushing EPA, yards/play, explosive rate, and turnover form made current-game margin forecasts and loss/10+/20+/30+ probabilities worse once the sportsbook spread was already known.

**Decision:** do not use EPA/style to overrule the current week's sportsbook line.

### Game total

Adding `total_line` to spread did not materially improve out-of-sample loss or blowout probability calibration. Bootstrap intervals for the incremental Brier-score effect crossed zero.

**Decision:** exclude total from the V1 margin-distribution model unless later evidence establishes incremental value.

## Full-margin distribution

The promoted V1 simulation distribution is a **residual-centered empirical sampler**.

For historical favorite games:

`spread residual = actual favorite margin - market favorite spread`

For a target spread, residuals from historically similar spreads are weighted and re-centered on the target. This retains real NFL scoring/tail behavior while keeping the simulated distribution tied to the market expectation.

Walk-forward 2011–2025, representative bandwidth 3.0:

- Mean error: **-0.017 points**
- MAE: **10.045**
- RMSE: **12.991**
- Loss Brier: **0.21045**
- Win 10+ Brier: **0.21261**
- Win 20+ Brier: **0.12628**
- Win 30+ Brier: **0.03976**

Bandwidths 3–4 perform similarly; V1 should not over-tune this parameter.

## Realized-score results: descriptive only

Earlier tests found large historical realized-score gains for rolling allocators. For example, raw long/slow was one of the strongest realized-score variants and had a much better historical floor than the more responsive default model.

Those figures remain useful descriptions of what happened, but they no longer justify claims of equivalent expected-value edge because the selected teams' realized margins can vary enormously around sportsbook expectation.

The 2011–2025 expected-allocation audit exposed this directly:

| Strategy | Mean actual score | Mean selected market sum | Actual minus selected market |
|---|---:|---:|---:|
| Biggest Favorite | 174.33 | 176.87 | -2.53 |
| Raw long/slow | **206.07** | 177.40 | **+28.67** |
| Future-style allocator | 186.00 | **181.30** | +4.70 |

Raw long/slow's selected market value was only **+0.53 points/season** above Biggest Favorite, while its actual results ran **+28.67 points/season above its own selected spreads**. Therefore its large actual-score advantage must not be interpreted as a similarly large allocation edge.

## Future-week line forecasting

Team style does earn a narrow, important role when the future sportsbook line does **not** exist yet.

Using long/slow market power plus frozen entering team style improved prediction of eventual future closing lines in **21,822 walk-forward forecasts** from 2011–2025.

| Model | Future-line MAE | 2021–2025 MAE |
|---|---:|---:|
| Raw long/slow power | 3.723 | 3.816 |
| Recalibrated power | 3.629 | 3.717 |
| **Power + core style** | **3.292** | **3.345** |
| Power + style + turnover | 3.286 | 3.341 |

Core-style improvement versus recalibrated power was approximately **0.337 spread points per forecast**, with target-game-clustered uncertainty clearly favoring style.

The gain persisted by horizon:

- 1 week ahead: **0.436 points**
- 2 weeks: **0.375**
- 3–5 weeks: **0.344**
- 6–9 weeks: **0.321**
- 10+ weeks: **0.215**

**Decision:**

- current week → sportsbook spread directly;
- future weeks → long/slow market-power forecast + validated core style correction.

Turnover adds too little full-history improvement to justify a separate production feature yet.

## Expected-allocation audit

The correct strategy question is whether forecasting improvements translate into better one-use allocation **in expectation**.

Across 2011–2025, core future style improved raw long/slow by:

- selected market value: **+3.90 points/season**, bootstrap interval approximately **+1.13 to +6.90**;
- calibrated EV, bandwidth 1.5: **+3.81**, interval +0.92 to +6.76;
- calibrated EV, bandwidth 3.0: **+4.06**, interval +1.25 to +7.07;
- calibrated EV, bandwidth 4.0: **+4.09**, interval +1.26 to +7.17.

So style meaningfully improves the raw allocator's save/burn decisions even though its realized historical game outcomes were colder.

### Versus Biggest Favorite

Across 2011–2025, core style also produced positive expected allocation gains versus Biggest Favorite:

- selected market sum: **+4.43 points/season**, bootstrap interval +0.73 to +8.67;
- calibrated EV: approximately **+3.0 to +3.7 points/season** across tested empirical bandwidths, with all intervals positive.

However the exact modern 18-week era remains unresolved.

### 2021–2025 caution

Core style versus Biggest Favorite:

- selected market sum: **-1.10 points/season**;
- calibrated EV BW 1.5: **-0.68**;
- BW 3.0: **-1.05**;
- BW 4.0: **-1.13**.

At the same time, style improved raw long/slow by roughly **+6 calibrated EV points/season** in this period.

Interpretation: the future-style forecast is useful, but the current allocator still deviates from Biggest Favorite too aggressively or at the wrong moments for the exact modern format.

## Hindsight allocation opportunity

The closing-line hindsight assignment has an average selected-market advantage of approximately **+18.33 points/season** over Biggest Favorite in 2011–2025.

This is not deployable; it establishes only that one-use schedule allocation has meaningful theoretical value.

- Raw long/slow captured about **+0.53 points**, roughly **2.9%** of that gap.
- Core future style captured about **+4.43 points**, roughly **24.2%**.

There is therefore room to improve the decision policy without inventing more current-game predictive features.

## Sacrifice-cap / risk research

A hard rule limiting how many current spread points the optimizer may sacrifice did not produce a robust winner.

The 3-point cap reduced overall variance and looked strong in 2021–2025, but it surrendered full-history expected performance and had a worse deep historical tail than unconstrained long/slow. Because cap=3 was also identified after inspecting historical results, it is not production-locked.

**Decision:** risk control should eventually come from remaining-season distributions and championship probability, not an arbitrary spread cutoff.

## Current V1 architecture

The evidence currently supports this structure:

1. **Current-week game value:** sportsbook spread is the primary expectation.
2. **Future-week game value:** long/slow market-power forecast plus leakage-safe core style correction.
3. **Expected margin transform:** residual-centered empirical calibration.
4. **Inventory:** each team is a one-use asset.
5. **Planning:** optimize remaining weeks, then rerun from scratch every week.
6. **Uncertainty:** use the coherent empirical margin sampler for later Monte Carlo.
7. **Risk policy:** not yet production-locked.

## Current research conclusion

1. **Weekly reoptimization remains strongly supported.**
2. **Do not claim raw long/slow's large historical actual-score edge as proven allocation edge.** Favorable realized residuals explain much of it.
3. **Biggest Favorite is a very strong benchmark and remains unbeaten on expected allocation in the small 2021–2025 exact-format sample.**
4. **Core team style is validated for future-line forecasting, not current-game override.**
5. **Core style materially improves expected allocation versus raw long/slow and versus Biggest Favorite over 2011–2025.**
6. **The current style allocator is not yet production-ready because its modern-era expected advantage versus Biggest Favorite is slightly negative.**
7. **Turnover and game total do not currently justify added complexity.**
8. **Next gate:** use Biggest Favorite as the weekly anchor and deviate only when the modeled remaining-season calibrated-EV advantage of an alternate current choice clears a predefined threshold. Evaluate threshold policy on an earlier development period and report 2021–2025 separately; the latter is not a pristine holdout because it has already been inspected repeatedly.
