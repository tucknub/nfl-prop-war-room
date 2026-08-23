# NFL Margin Pool V1 — Research Checkpoint

Date: 2026-08-23

## Scope

Historical regular-season backtest using nflverse game results and market spreads, 2006–2025. The pool rule is one NFL team per week, each team usable at most once, with weekly score equal to that team's actual point differential.

The rolling models use the current week's market line when the pick is made and estimate future weeks from market-derived team power ratings. They do **not** use future closing lines when making historical rolling decisions. Future closing-line and actual-result optimizers are retained only as hindsight/reference benchmarks.

## Baseline vs rolling

Across 20 seasons (2006–2025):

- Biggest Unused Favorite mean actual score: **179.65**
- Default Rolling Allocator mean actual score: **201.90**
- Mean rolling improvement: **+22.25 points/season**
- Median rolling improvement: **+26.0**
- Rolling beat baseline in **14 of 20** seasons
- Worst default-rolling season vs baseline: **-72**
- Best default-rolling season vs baseline: **+99**
- 2006 baseline checksum: **+132**, matching the independently hand-checked path

## Static Week-1 allocation test

A one-time Week-1 snapshot plan was created using the same market-power framework available at Week 1 and then left unchanged for the entire season.

Across 2006–2025:

- Static Week-1 plan mean: **113.8**
- Static minus Biggest Favorite: **-65.85 points/season**
- Rolling minus Static: **+88.1 points/season**
- Rolling beat Static in **19 of 20** seasons

In the exact 18-week era (2021–2025):

- Biggest Favorite mean: **178.4**
- Static mean: **104.4**
- Rolling mean: **212.6**
- Rolling minus Biggest Favorite: **+34.2 points/season**
- Rolling minus Static: **+108.2 points/season**

Interpretation: a preseason/Week-1 path should be treated as a reservation map, not a locked plan. Weekly reoptimization is a central part of the observed edge.

Caveat: this static benchmark is a Week-1 market-power snapshot, not a full professional preseason forecasting system with independently sourced preseason win totals, player projections, injuries, and future-game lines.

## 2010 and 2017 failure autopsy

The two worst default-rolling seasons were primarily outcome variance rather than excessive sacrifice of current market value.

### 2010

- Biggest Favorite actual: **153**; selected-market sum: **161.5**
- Rolling actual: **81**; selected-market sum: **168.5**
- Rolling selected-market advantage: **+7.0**
- Actual-score deficit: **-72**
- Relative outcome-residual deficit: **-79**
- Total deliberate current-market sacrifice vs the best available team from rolling's own inventory: only **4.0 points** across the season

### 2017

- Biggest Favorite actual: **233**; selected-market sum: **171.0**
- Rolling actual: **162**; selected-market sum: **180.0**
- Rolling selected-market advantage: **+9.0**
- Actual-score deficit: **-71**
- Relative outcome-residual deficit: **-80**
- Total deliberate current-market sacrifice vs the best available team from rolling's own inventory: **8.0 points**

Interpretation: these failures do not support abandoning allocation/reoptimization. They support adding calibrated margin distributions and downside/risk controls, because teams selected with at least as much aggregate market expectation produced much worse realized margins.

## Rating sensitivity

Selected full-period results vs Biggest Favorite:

| Model | Mean improvement | Wins-Losses | Worst season |
|---|---:|---:|---:|
| Default (20 periods, half-life 6, ridge 3) | +22.25 | 14-6 | -72 |
| High ridge | +16.75 | 13-7 | -29 |
| Long/slow (32 periods, half-life 8, ridge 3) | **+26.65** | 13-7 | **-25** |
| Strict long prior-only | +19.85 | 14-6 | -60 |

Very reactive / weakly regularized variants were substantially less stable.

## Temporal robustness

The temporal split is a robustness check, **not a pristine untouched holdout**, because the configuration family had already been inspected over the full historical sample before this split was run.

Results vs Biggest Favorite:

| Model | 2006–2015 | 2016–2020 | 2021–2025 |
|---|---:|---:|---:|
| Default | +10.5 | +33.8 | **+34.2 (5-0)** |
| High ridge | +17.7 | +24.6 | +7.0 |
| Long/slow | +19.0 | **+48.0** | **+20.6** |
| Strict long prior-only | +21.2 | +40.6 | **-3.6** |

A development-only rule using 2006–2015 would have selected strict-long, which then performed poorly in the 2021–2025 18-week era. This is evidence against removing current-week market information and against choosing a model solely from older NFL regimes.

## Responsive + long/slow ensemble

Blending future forecasts did not improve on the long/slow model. The best tested blend was 25% default / 75% long-slow:

- Full 2006–2025 mean improvement: **+23.3**
- Worst season: **-25**
- 2021–2025 mean improvement: **+10.8**

Long/slow alone was better on full-period mean (**+26.65**) and recent-era mean (**+20.6**) with the same -25 historical worst season. Therefore no ensemble complexity is justified yet.

## Walk-forward margin probability calibration

Favorite-side regular-season data from 2006–2025 contains **5,199 games**. Probability models were evaluated walk-forward from 2011–2025, so each test season was trained only on earlier seasons.

Observed event rates over the walk-forward test period:

- Favorite loses outright: **33.35%**
- Favorite wins by 10+: **34.55%**
- Favorite wins by 20+: **15.64%**
- Favorite wins by 30+: **4.24%**

### Does game total help beyond spread?

No meaningful out-of-sample improvement was found from adding total. Across loss, 10+, 20+, and 30+ targets, spread+total was essentially flat-to-worse than spread-only, and paired bootstrap intervals for the Brier-score difference crossed zero in every case.

Therefore **`total_line` is excluded from the V1 margin-distribution layer** unless a later model demonstrates incremental value.

## Coherent full-margin distribution for Monte Carlo

A raw-margin kernel sampler initially regressed extreme favorite spreads too strongly toward the middle. The corrected model samples **historical spread residuals**:

`residual = actual favorite margin - market favorite spread`

For a target projected spread, historical residuals from similar spreads are weighted and re-centered on the target spread. This preserves historical NFL tail/scoring behavior while keeping the simulated distribution centered near the current market expectation.

Walk-forward 2011–2025 results for the residual-centered sampler are competitive with or better than specialized binary probability models. Representative bandwidth 3.0 results:

- Mean margin error: **-0.017 points**
- MAE: **10.045**
- RMSE: **12.991**
- Loss Brier: **0.21045**
- 10+ Brier: **0.21261**
- 20+ Brier: **0.12628**
- 30+ Brier: **0.03976**

Bandwidth 4.0 gives near-zero overall mean error (**+0.003**) and similar probability calibration. Differences between 3.0 and 4.0 are small enough that V1 should not over-tune the bandwidth.

**Research decision:** promote the residual-centered empirical model as the coherent V1 Monte Carlo margin sampler. Keep specialized logistic/normal models as calibration references, not separate production probabilities.

## Current-market sacrifice-cap test

A practical safeguard was tested on the long/slow rolling optimizer: restrict the current-week choice to teams no more than X spread points worse than the largest currently available favorite, while still choosing the candidate with the best optimized remaining-season path.

| Max current spread sacrifice | Mean edge vs baseline | W-L-T | Worst season | 2021–2025 mean |
|---|---:|---:|---:|---:|
| 0.0 | +1.55 | 8-7-5 | -54 | +0.4 |
| 0.5 | +8.55 | 11-8-1 | -54 | +3.8 |
| 1.0 | +12.25 | 11-9 | -47 | +3.2 |
| 1.5 | +13.85 | 10-10 | -47 | +7.6 |
| 2.0 | +11.75 | 11-9 | -72 | 0.0 |
| **3.0** | **+18.75** | **15-5** | -51 | **+32.0 (5-0)** |
| Unconstrained | **+26.65** | 13-7 | **-25** | +20.6 |

Important conclusions:

1. A tighter weekly cap does **not** automatically create a safer season. Inventory changes cascade into later weeks.
2. Unconstrained long/slow retains the best mean historical edge and best observed worst season.
3. A **3-point cap is a promising candidate** because it improved season win frequency to 15-5 and went 5-0 in 2021–2025, but it sacrifices expected historical edge and has a worse historical floor than unconstrained.
4. Cap=3 was identified after inspecting historical results, so it is **not production-locked**. It should be treated as a candidate policy/risk signal and evaluated further rather than promoted because of its recent record.

## Current research conclusion

1. **Weekly reoptimization is supported.** The locked Week-1 plan performed very poorly relative to both rolling and the simple baseline.
2. **Resource allocation appears to add real historical value.** The rolling family materially outperformed Biggest Favorite across the historical sample.
3. **Long/slow is the strongest current core optimizer.** It combines the best full-history mean edge with the best observed downside among the main tested rating models.
4. **Current market information still matters.** Prior-only versions weakened materially in the 2021–2025 era.
5. **Game total does not earn a V1 role in margin probabilities.** Spread-only is sufficient until further evidence says otherwise.
6. **The residual-centered empirical margin sampler is promoted for Monte Carlo research.** It gives one coherent full-margin distribution while retaining NFL tail behavior.
7. **No hard sacrifice cap is production-locked.** The 3-point cap is worth carrying as an alternate/risk-policy candidate, but unconstrained long/slow remains the strongest central strategy.
8. **Next research gate:** compare season-level risk distributions for Biggest Favorite, unconstrained long/slow, and the cap-3 candidate, then use the empirical margin sampler to build championship-oriented Monte Carlo logic without sacrificing the proven allocation edge.
