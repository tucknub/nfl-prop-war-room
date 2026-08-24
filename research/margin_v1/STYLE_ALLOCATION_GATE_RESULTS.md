# Margin V1 — End-to-End Style Allocation Gate

Date: 2026-08-23

## Decision

**DO NOT promote the team-style correction into the V1 one-use Margin Pool allocator.**

The style model materially improved forecasts of future closing spreads, but that improvement did **not** translate into better contest decisions. When the style-corrected future forecasts were fed into the rolling one-use allocator, realized season Margin scores were materially worse than with the raw long/slow market-power future forecast.

Decision utility outranks intermediate forecast accuracy. Therefore the prior future-line MAE result is retained as valid forecasting evidence, but it is insufficient for production strategy promotion.

## End-to-end test

Historical seasons: 2011–2025.

Compared:
- raw long/slow market-power rolling allocator;
- recalibrated long/slow future-line forecast;
- long/slow + core style correction;
- long/slow + style + turnover correction.

The current week always used the sportsbook market available that week. Future games used snapshot-available forecasts only. The test preserved the one-team-per-week and one-use-per-team constraints.

## Results

| Model | Mean season score | Mean vs Biggest Favorite | Mean vs raw long/slow | Recent 2021–25 vs Biggest Favorite | Recent vs raw long/slow |
| --- | ---: | ---: | ---: | ---: | ---: |
| Raw long/slow | **206.07** | **+31.73** | 0.00 | **+20.60** | 0.00 |
| Recalibrated long/slow | 188.13 | +13.80 | -17.93 | -23.00 | -43.60 |
| Long/slow + core style | 186.00 | +11.67 | **-20.07** | +5.60 | **-15.00** |
| Long/slow + style + turnover | 186.47 | +12.13 | -19.60 | -0.20 | -20.80 |

Paired season-score delta for core style versus raw long/slow:
- mean: **-20.07 points/season**
- median: **-5.0**
- bootstrap 95% interval: approximately **[-34.87, -6.20]**
- recent 2021–2025 mean: **-15.0**

Style changed the selected team in 67 of 260 historical weeks (25.8%) versus the recalibrated strategy, including 23 of 90 weeks (25.6%) in 2021–2025.

Recent-season examples:

| Season | Biggest Favorite | Raw long/slow | Core style |
| --- | ---: | ---: | ---: |
| 2021 | 204 | 240 | 240 |
| 2022 | 137 | 112 | 51 |
| 2023 | 202 | 177 | 181 |
| 2024 | 144 | 215 | 215 |
| 2025 | 205 | 251 | 233 |

## Interpretation

The future closing-line target is not the contest objective. A forecast can be closer to the eventual closing spread on average while still changing the timing of team burns in ways that reduce realized season point differential.

This falsifies the proposed direct production use of style in the V1 allocation layer.

It does **not** invalidate the earlier finding that style predicts future closing lines better. That finding remains useful research, but the V1 promotion standard requires improvement in the final decision objective.

## Production consequence

1. Keep current-week sportsbook spreads authoritative.
2. Do not use EPA/YPP/explosive/turnover style to alter current-week expectation.
3. Do not feed the validated style correction directly into the one-use allocator.
4. Keep the production Week-4 safety gate active until the raw long/slow future-power model is tested under the exact frozen cap-3/+0.5 expected-points policy.
5. If raw long/slow passes that exact policy gate, promote it for unpriced future games and label it clearly as an inferred market-power forecast.
6. Posted future/look-ahead market lines always take precedence over inferred forecasts when genuinely available at the live snapshot.

## Audit trail

Clean reproduction was run in temporary research PR #14. The workflow completed successfully, then reran and passed the unchanged production engine, route invariants, Week-4 safety gate, and rendered dashboard validation. PR #14 was closed without merge.
