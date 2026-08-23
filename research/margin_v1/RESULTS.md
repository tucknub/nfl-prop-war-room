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

## Current research conclusion

1. **Weekly reoptimization is supported.** The locked Week-1 plan performed very poorly relative to both rolling and the simple baseline.
2. **Resource allocation appears to add real historical value.** The default rolling strategy beat Biggest Favorite by +22.25 points/season on average across 20 seasons.
3. **Slower/stabilized power ratings are safer.** Long/slow produced the best full-sample mean with a much smaller historical downside than the default model.
4. **Current market information still matters.** Prior-only versions weakened materially in the 2021–2025 era.
5. **Do not lock a single production model yet.** Default is strongest in the five-season exact 18-week sample; long/slow is stronger on full-history robustness. They should remain separate signals until a margin-distribution/risk layer is tested.
6. **Next research gate:** calibrate full game-margin distributions from spread/total buckets, then test whether expected margin + blowout probability + loss/downside controls improve championship-oriented decisions without destroying the allocation edge.
