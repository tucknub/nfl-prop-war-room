# Margin V1 Joint Monte Carlo Results

## Purpose

Evaluate Biggest Favorite, the fixed +0.5 EV anchored policy with a 3-point current-spread sacrifice cap, and the same anchored policy without a sacrifice cap under correlated season-level NFL margin uncertainty.

## Method

- Historical evaluation seasons: 2011-2025.
- Modern 18-week subset: 2021-2025.
- 100,000 simulations per season.
- Residual-centered empirical margin sampler, bandwidth 3.0.
- Each evaluation season is simulated using historical residual information from seasons before that season.
- Game outcomes are shared across strategies within each simulation. If two strategies select the same game, they receive the same simulated margin rather than independent draws.
- These are strategy-vs-strategy simulations only. They are not yet simulations of a realistic 10/25/50/100-person field.

## Mean simulated season scores

| Strategy | 2011-2025 | 2021-2025 |
| --- | ---: | ---: |
| Biggest Favorite | 185.15 | 189.27 |
| Cap-3 anchor | 190.39 | 191.71 |
| Uncapped anchor | 190.38 | 192.08 |

The cap-3 and uncapped anchored strategies are essentially tied over the full 2011-2025 sample. In the modern five-season sample, uncapped leads cap 3 by only about 0.37 simulated points per season.

## Pairwise simulated results

### 2011-2025

- Cap 3 vs Biggest Favorite: win 54.13%, tie 1.11%, loss 44.76%.
- Uncapped vs Biggest Favorite: win 53.88%, tie 1.04%, loss 45.08%.
- Cap 3 vs uncapped: win 26.25%, tie 47.40%, loss 26.35%.

### 2021-2025

- Cap 3 vs Biggest Favorite: win 51.66%, tie 1.43%, loss 46.91%.
- Uncapped vs Biggest Favorite: win 51.69%, tie 1.26%, loss 47.04%.
- Cap 3 vs uncapped: win 38.74%, tie 21.13%, loss 40.13%.

## Interpretation

1. The anchored allocation concept survives realistic NFL margin variance better than raw realized-score backtests alone suggested.
2. A 3-point sacrifice cap preserves essentially all of the full-sample simulated score of the uncapped policy while eliminating extreme current-week sacrifices.
3. The uncapped policy retains a very small modern-era expected-score advantage, but the difference is minor compared with the operational risk reduction from cap 3.
4. Three-way first-place share among these three archetypes is not an appropriate championship metric because the two anchored strategies frequently make identical or highly correlated selections and therefore split the allocator side of the field.
5. The next valid test is a heterogeneous field simulation with realistic opponent strategies, different used-team inventories, and pool standings.

## Status

Cap 3 is the leading V1 risk-control candidate, but not yet the final championship policy. The expected-points engine should not be tuned further until field/game-theory simulations test whether standings-dependent risk taking improves probability of finishing first.
