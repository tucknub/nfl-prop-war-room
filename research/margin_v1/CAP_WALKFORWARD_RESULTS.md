# Margin Pool V1 — Walk-Forward Cap Selection Results

Date: 2026-08-23

## Scope

This gate evaluates whether a current-week sacrifice cap can be selected without using the season being tested. The underlying Biggest-Favorite-anchored policy remains fixed at the previously selected **+0.5 remaining-season calibrated-EV deviation threshold**.

For each test season from 2016–2025, cap selection used only earlier seasons beginning in 2011. The primary rule was predeclared before the run:

> **risk95 expanding:** choose the smallest finite cap whose prior mean BW=3 calibrated EV is at least 95% of the best finite cap's prior mean BW=3 EV.

References/sensitivities were also predeclared:

- max prior EV among finite caps
- risk90 expanding (smallest cap retaining at least 90% of best finite prior EV)
- risk95 using only the most recent five prior seasons
- static cap 3
- static cap 4
- uncapped

Because earlier research had already inspected these historical seasons in other configurations, this is a leakage-safe simulated decision process but **not a pristine never-before-seen holdout**.

## 2016–2025 walk-forward results

| Strategy | BW3 EV edge vs BF | EV W-L | Mean cap | Max weekly sacrifice | Mean actual delta* |
|---|---:|---:|---:|---:|---:|
| risk95 expanding — PRIMARY | +1.99 | 6-4 | 3.4 | 3.5 | +13.1 |
| max-EV expanding | +2.25 | 6-4 | 4.0 | 4.0 | +14.0 |
| **risk90 expanding** | **+3.68** | **7-3** | **3.0** | **3.0** | **+17.7** |
| risk95 rolling-5 | +1.65 | 6-4 | 3.6 | 4.0 | +12.9 |
| static cap 3 | **+3.68** | **7-3** | 3.0 | 3.0 | +17.7 |
| static cap 4 | +3.11 | 6-4 | 4.0 | 4.0 | +16.7 |
| uncapped | **+4.00** | **7-3** | uncapped | **7.0** | +8.5 |

\*Actual score is secondary evidence because realized game margins are much noisier than market/calibrated expected margin.

## Modern 18-week era: 2021–2025

| Strategy | BW3 EV edge vs BF | EV W-L | Max weekly sacrifice | Mean actual delta* |
|---|---:|---:|---:|---:|
| risk95 expanding — PRIMARY | **-0.92** | 2-3 | 3.5 | +8.4 |
| max-EV expanding | -1.59 | 2-3 | 4.0 | +8.0 |
| **risk90 expanding** | **+2.46** | **3-2** | **2.5** | **+17.6** |
| risk95 rolling-5 | -1.59 | 2-3 | 4.0 | +8.0 |
| static cap 3 | **+2.46** | **3-2** | **2.5** | **+17.6** |
| static cap 4 | -0.45 | 2-3 | 4.0 | +10.2 |
| uncapped | **+2.87** | **3-2** | **7.0** | +3.2 |

## Primary-rule decision

The primary 95%-retention walk-forward selector does **not** clear the modern-era promotion gate. Its 2021–2025 calibrated-EV point estimate is negative.

Therefore risk95 should not be the production safeguard rule.

## Important sensitivity result: risk90 converged to cap 3 without future-season information

The predeclared 90%-retention sensitivity selected **cap 3 in every test season from 2016 through 2025**.

This matters because cap 3 was previously attractive in the fixed-cap table, but simply promoting it after seeing 2021–2025 would have been post-hoc. The walk-forward risk90 rule gives a separate reason for cap 3 to remain a serious candidate: using only prior seasons at each test point, a modest risk-regularized rule repeatedly selected it.

Its results:

- 2016–2025 BW3 calibrated-EV edge vs Biggest Favorite: **+3.68 points/season**
- 2021–2025 BW3 calibrated-EV edge: **+2.46 points/season**
- 2016–2025 EV-positive seasons: **7 of 10**
- Modern EV-positive seasons: **3 of 5**
- Maximum weekly current-spread sacrifice: **3.0 points** over 2016–2025
- Maximum modern-era sacrifice: **2.5 points**

For comparison, uncapped produced +4.00 EV/season over 2016–2025 and +2.87 in 2021–2025, but allowed a 7-point sacrifice in this test window and a 17.5-point historical sacrifice in the earlier development sample.

Thus cap 3 retained roughly **92%** of uncapped 2016–2025 expected-value edge while sharply limiting the behavioral tail risk.

## Cap choices under the primary walk-forward rule

The risk95 expanding rule selected:

- 2016: 3
- 2017: 3
- 2018: 3
- 2019: 4
- 2020: 4
- 2021: 4
- 2022: 4
- 2023: 3
- 2024: 3
- 2025: 3

The shift to cap 4 for 2019–2022 is exactly where the primary rule weakened in the modern-era evaluation.

The risk90 expanding sensitivity selected cap 3 in **all ten test seasons**.

## Research decision

1. **Reject risk95 expanding as the preferred safeguard.** It is disciplined but failed the modern-era EV point-estimate gate.
2. **Keep cap 3 / risk90 as the leading bounded-risk candidate.** It now has both the fixed-cap evidence and a prior-data-only walk-forward selection rationale.
3. **Keep uncapped as an EV ceiling/reference, not the preferred operational policy.** Its marginal EV advantage over cap 3 is small relative to the increase in possible current-week sacrifice.
4. **Do not claim cap 3 is finally proven.** The historical sample has been inspected repeatedly and only five modern 18-week seasons exist.
5. **Next gate:** compare Biggest Favorite, cap-3 anchored allocation, and uncapped allocation under the coherent empirical margin sampler in pool-level Monte Carlo. The objective should move from expected season points to **probability of finishing first** under realistic opponent inventories and score states.
