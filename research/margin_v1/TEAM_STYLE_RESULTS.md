# NFL Margin Pool V1 — Team-Style Residual Test

Date: 2026-08-23

## Question

Do recent team-performance/style variables improve prediction of actual margin or blowout/downside probabilities **after the current sportsbook spread is already known**?

Data source: nflverse weekly team summary stats via `nflreadpy.load_team_stats()`. Features use four-game entering form with at least three prior games and are shifted so the current game's stats are never included.

Tested style signals:

- net EPA/play differential
- passing EPA/dropback differential
- rushing EPA/carry differential
- yards/play differential
- explosive-play differential
- turnover-margin form as a separate extension

Walk-forward evaluation covers 2011–2025 and trains each test season only on earlier seasons. The usable sample is 3,198 favorite-side games after entering-form requirements.

## Margin prediction

| Model | MAE | RMSE | 2021–25 MAE |
|---|---:|---:|---:|
| Raw market spread | **10.0424** | 12.9742 | **9.7198** |
| Recalibrated market | 10.0648 | **12.9666** | 9.7480 |
| Market + style | 10.0799 | 12.9778 | 9.7676 |
| Market + style + turnover | 10.0954 | 12.9928 | 9.7685 |

Relative to the recalibrated market, style increased absolute error by **+0.0151 points/game** with a bootstrap 95% interval approximately **+0.0011 to +0.0292**. Style + turnover increased error by **+0.0307**, interval approximately **+0.0129 to +0.0485**.

## Tail probabilities

Spread-only had the best Brier score for every tested target:

| Target | Spread only | + style | + style + turnover |
|---|---:|---:|---:|
| Favorite loses | **0.20760** | 0.20827 | 0.20853 |
| Favorite wins 10+ | **0.21492** | 0.21542 | 0.21566 |
| Favorite wins 20+ | **0.13117** | 0.13147 | 0.13154 |
| Favorite wins 30+ | **0.04118** | 0.04141 | 0.04143 |

The direction was the same in the 2021–2025 subset. For loss, 20+, and 30+, the style degradation versus spread-only had bootstrap intervals above zero; turnover did not rescue it.

## Research decision

1. **Do not use recent EPA/YPP/explosive form to override the current sportsbook spread in V1.**
2. **Do not use turnover form.** It made both point and probability forecasts worse.
3. For current-game loss/blowout distributions, retain the spread-centered empirical residual sampler.
4. This test does **not** prove EPA has no value anywhere. The market already incorporates much of the information by game time. The remaining valid test is whether team-form variables improve forecasts of **future-week closing lines before those markets exist**, which is directly relevant to future-value/resource allocation.
