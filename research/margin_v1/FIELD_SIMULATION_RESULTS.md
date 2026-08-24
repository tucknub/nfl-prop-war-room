# Margin V1 Heterogeneous Field Simulation

## Purpose

Test whether the leading Margin strategies improve probability of finishing first against heterogeneous synthetic fields rather than only against one benchmark strategy.

## Field model

This is a sensitivity model, not a claim about the actual user's pool composition.

Historical seasons: 2011-2025. Modern subset: 2021-2025. 50,000 correlated NFL outcome simulations per season. Pool sizes: 10, 25, 50, 100.

Opponent path library per season:
- 1 Biggest Favorite path
- cap-2, cap-3, cap-4, and uncapped anchored paths
- 6 randomized top-2-current-favorite paths
- 6 randomized top-3-current-favorite paths

Synthetic profiles:
- Chalk-heavy: 55% Biggest Favorite family, 20% anchored, 15% top-2, 10% top-3.
- Mixed: 35% Biggest Favorite, 30% anchored, 20% top-2, 15% top-3.
- Sharp-heavy: 20% Biggest Favorite, 50% anchored, 15% top-2, 15% top-3.

Duplicate strategy paths are allowed because real entrants can independently arrive at the same selections. Ties for first are split when computing expected first-place share.

## Modern 2021-2025 expected first-place share

| Field profile | Size | Biggest Favorite | Cap 3 | Uncapped |
| --- | ---: | ---: | ---: | ---: |
| Chalk-heavy | 10 | 3.99% | 15.40% | 18.67% |
| Chalk-heavy | 25 | 0.72% | 5.25% | 7.49% |
| Chalk-heavy | 50 | 0.21% | 2.17% | 3.27% |
| Chalk-heavy | 100 | 0.07% | 0.92% | 1.40% |
| Mixed | 10 | 4.30% | 10.12% | 13.24% |
| Mixed | 25 | 0.82% | 3.18% | 4.74% |
| Mixed | 50 | 0.25% | 1.32% | 2.01% |
| Mixed | 100 | 0.10% | 0.58% | 0.89% |
| Sharp-heavy | 10 | 6.95% | 7.17% | 9.96% |
| Sharp-heavy | 25 | 1.52% | 2.10% | 3.18% |
| Sharp-heavy | 50 | 0.47% | 0.83% | 1.26% |
| Sharp-heavy | 100 | 0.17% | 0.36% | 0.54% |

## Full 2011-2025 direction

Cap 3 increased expected first-place share versus Biggest Favorite in all chalk-heavy and mixed field-size comparisons and was directionally positive in sharp-heavy fields. Uncapped generally exceeded cap 3 on expected first-place share.

The full-period mean simulated scores remained nearly identical for cap 3 and uncapped (about 190.47 vs 190.51 in this run), so the first-place-share difference is primarily about path differentiation/tail behavior rather than a large mean-score gap.

## Interpretation

1. Cap 3 remains a strong default expected-points/risk-control policy and materially outperforms Biggest Favorite in most heterogeneous field scenarios.
2. When the objective changes from expected points to probability of finishing first, uncapped allocation frequently has an advantage over cap 3.
3. This does not imply using uncapped all season. A season-long uncapped policy permits larger current sacrifices and is operationally less robust.
4. The correct next question is standings-dependent: from the same used-team inventory, when does a trailing player gain enough first-place probability by accepting a more aggressive current/future path to justify departing from cap 3?
5. First-place probabilities depend strongly on assumed field composition. The field profiles are sensitivity scenarios and should eventually be replaced or reweighted with the actual pool's observed entrant behavior.

## Status

Promote cap 3 as the V1 default risk policy, but do not lock it as the championship objective. Proceed to late-season snapshot simulations that force alternative current selections from the same inventory and compare first-place share at controlled standings gaps.
