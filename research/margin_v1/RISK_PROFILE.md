# NFL Margin Pool V1 — Realized Strategy Risk Profile

Date: 2026-08-23

This checkpoint compares realized historical season outcomes for three strategies over 2006–2025: Biggest Unused Favorite, unconstrained long/slow rolling allocation, and a long/slow rolling allocator with a 3-point current-market sacrifice cap.

## Full-period profile

| Strategy | Mean score | Score SD | Mean edge vs baseline | Edge SD | 10th pct edge | 25th pct edge | 75th pct edge | 90th pct edge | Seasons below baseline | Edge <= -20 | Edge >= +20 | Edge >= +50 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Biggest Favorite | 179.65 | 43.23 | 0.00 | 0.00 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | 0 | 0 | 0 |
| Long/slow unconstrained | **206.30** | 50.28 | **+26.65** | 40.21 | **-17.8** | -6.5 | **+57.25** | **+73.0** | 7 | **2** | **11** | **6** |
| Long/slow cap-3 | 198.40 | **44.58** | +18.75 | **33.07** | -25.8 | **+1.25** | +43.25 | +58.2 | **5** | 4 | 10 | 3 |

Interpretation:

- Unconstrained long/slow has the best average and upper-tail results.
- Cap-3 lowers realized variance and finishes below the baseline less often.
- However, cap-3 does **not** improve the deep historical lower tail: its 10th-percentile edge (-25.8) is worse than unconstrained (-17.8), and it had four seasons at -20 or worse versus two for unconstrained.
- Therefore a hard current-spread sacrifice cap is not a reliable downside-control mechanism by itself.

## Paired cap-3 vs unconstrained

- Mean cap-3 minus unconstrained: **-7.9 points/season**
- Median: **-1.0**
- Cap-3 better: **6 seasons**
- Tied: **4 seasons**
- Unconstrained better: **10 seasons**
- Bootstrap 95% interval for mean difference: approximately **-18.3 to +2.25**
- Worst cap-3 relative season: **-49**
- Best: **+38**

This does not establish cap-3 as superior. It is better treated as an alternate policy signal for situations where current standings or opponent inventory make a different risk posture desirable.

## Modern 18-week era, 2021–2025

| Strategy | Mean score | Mean edge | Score SD | Edge SD | 10th pct edge | 90th pct edge |
|---|---:|---:|---:|---:|---:|---:|
| Biggest Favorite | 178.4 | 0.0 | 34.70 | 0.0 | 0.0 | 0.0 |
| Long/slow unconstrained | 199.0 | +20.6 | 56.33 | 43.54 | -25.0 | +61.0 |
| Long/slow cap-3 | **210.4** | **+32.0** | **44.29** | **23.82** | **+6.4** | +53.6 |

Cap-3 is notably stronger and more stable in this five-season modern sample, but this is a small sample and the cap was investigated after historical results were already visible. It is evidence worth carrying forward, not an untouched validation result.

## Research decision

1. Keep **unconstrained long/slow** as the central expected-value allocation strategy.
2. Keep **cap-3** as an alternate/risk-policy candidate, not the default.
3. Do not use a fixed cap as the final definition of risk control.
4. Build future risk decisions from a coherent simulated remaining-season score distribution and, once pool context is available, probability of finishing first.
5. Next test: determine whether pregame team-performance/style signals explain large margin residuals beyond the sportsbook spread. If they do, those signals can make the Monte Carlo tails team-specific instead of treating every team at the same spread as equivalent.
