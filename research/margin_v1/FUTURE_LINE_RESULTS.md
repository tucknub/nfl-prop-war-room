# Future-Week Closing-Line Forecast Research

Date: 2026-08-23

## Question

Can team performance information available at an origin week improve forecasts of **future NFL closing spreads that do not exist yet**, beyond the current long/slow market-power model used by the Margin Pool allocator?

This is intentionally separate from current-week prediction. A prior research gate found that EPA/YPP/explosive/turnover form made current-game margin and tail predictions worse once a current sportsbook spread already existed. The only remaining justified use case for team style was forecasting future weeks for save/burn allocation.

## Leakage controls

For every historical origin week:

- current and prior market lines were available to the long/slow power rating;
- team style was frozen using only games completed **before** the origin week;
- four prior games were used when available, with at least three required;
- later games in the same season were never used to construct the origin-week team form;
- the target was the eventual future game's closing spread;
- walk-forward evaluation used test seasons 2011–2025, with each test season's correction model trained only on earlier seasons;
- paired uncertainty was clustered by target game because the same future game is forecast at multiple origin weeks.

Long/slow market-power configuration remained fixed at 32 periods, half-life 8, ridge 3.

## Features tested

Core style:

- net EPA/play difference
- passing EPA/dropback difference
- rushing EPA/carry difference
- yards/play difference
- explosive-play rate difference

Optional turnover layer:

- turnover-margin difference

The correction model also received the baseline power forecast and forecast horizon so style was compared against a recalibrated market-power baseline rather than a straw-man raw forecast.

## Walk-forward results, 2011–2025

Sample: **21,822 origin-week → future-game forecasts**.

| Model | MAE | RMSE | Bias | 2021–2025 MAE |
|---|---:|---:|---:|---:|
| Raw long/slow power | 3.723 | 4.677 | +0.143 | 3.816 |
| Recalibrated long/slow power | 3.629 | 4.615 | -0.024 | 3.717 |
| **Power + core style** | **3.292** | **4.243** | +0.127 | **3.345** |
| **Power + style + turnover** | **3.286** | **4.237** | +0.124 | **3.341** |

Relative to recalibrated long/slow power, core style improved absolute future-line error by **0.337 points per forecast**. The target-game-clustered bootstrap interval was approximately **-0.428 to -0.336 points**, entirely favoring style. In 2021–2025 the mean improvement was **0.373 points**.

Adding turnover produced a total improvement of **0.343 points** versus recalibrated power, only about **0.006 points** better than core style overall. Therefore turnover has not yet earned a distinct production role.

## Performance by horizon

Core-style MAE versus recalibrated power:

| Weeks ahead | Recalibrated power MAE | Power + style MAE | Improvement |
|---|---:|---:|---:|
| 1 | 2.955 | **2.520** | **0.436** |
| 2 | 3.137 | **2.762** | **0.375** |
| 3–5 | 3.451 | **3.107** | **0.344** |
| 6–9 | 3.923 | **3.602** | **0.321** |
| 10+ | 4.613 | **4.398** | **0.215** |

The target-game-clustered bootstrap interval favored core style at every tested horizon:

- 1 week: roughly **-0.492 to -0.378**
- 2 weeks: **-0.434 to -0.314**
- 3–5 weeks: **-0.408 to -0.293**
- 6–9 weeks: **-0.382 to -0.247**
- 10+ weeks: **-0.319 to -0.116**

The effect decays with horizon, as expected, but remains measurable even 10+ weeks out.

## Research decision

**Team style earns a role in the future-week forecasting layer.**

The architecture should therefore distinguish two very different jobs:

1. **Current week:** use the sportsbook spread directly; do not override it with EPA/style.
2. **Future weeks:** use the long/slow market-power forecast plus a leakage-safe, walk-forward-validated team-style correction.

The next gate is end-to-end: determine whether the future-line MAE improvement actually improves Margin Pool save/burn decisions and season scores. A better forecast is not sufficient by itself; it must translate into better one-use team allocation before being promoted to the strategy engine.

## Caveats

- The style feature family was inspected during this research process, so these results are not a pristine untouched holdout.
- Repeated forecasts of the same target game are correlated; the reported uncertainty therefore clusters by target game rather than treating every origin-target pair as independent.
- Closing spread is a market target, not actual game margin. This layer is intended to improve future resource allocation, not to claim independent current-game betting edge.
