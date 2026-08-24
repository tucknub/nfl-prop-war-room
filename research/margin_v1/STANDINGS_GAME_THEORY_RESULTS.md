# Margin V1 Standings-Aware Game Theory Results

## Purpose

Test whether the expected-points-first cap-3 policy should ever be overridden when the actual contest objective is probability of finishing first.

The test compares alternative current-week selections from the **same already-used-team inventory**. It therefore isolates the value of the current decision rather than comparing strategies that arrived at the week with different histories.

## Method

Modern NFL seasons only: 2021-2025.

Historical snapshots:
- Week 10
- Week 13
- Week 16

This produces 15 season-week snapshots.

Pool sizes:
- 10
- 25
- 50
- 100

Controlled position relative to the current field leader:
- 30 points behind
- 15 points behind
- tied
- 15 points ahead

Simulation:
- 20,000 trials per snapshot/state
- mixed synthetic opponent profile: 35% Biggest-Favorite family, 30% anchored, 20% randomized top-2 favorite, 15% randomized top-3 favorite
- hero begins with the exact teams already burned by the historical cap-3 path
- candidate set is the six strongest available current-market teams, with the cap-3 selection always included
- current week uses the actual market available that week
- future games use only the future spread forecast available at the historical snapshot
- eventual future closing lines are not used
- each forced current candidate is followed by the best feasible remaining-season calibrated-EV assignment
- opponent future paths are rebuilt from the same snapshot-frozen information
- simulated game outcomes are shared across candidates and opponents
- objective is expected first-place share, splitting ties for first

## Aggregate result by standings gap

| Gap to leader | Cap-3 first share | Championship-optimal first share | Lift | Switch rate | Avg current-spread change | Avg remaining-plan EV change |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| -30 | 5.69% | 10.74% | **+5.05 pp** | **86.7%** | -2.78 | -3.59 |
| -15 | 20.43% | 24.17% | **+3.75 pp** | **48.3%** | -1.40 | -1.08 |
| 0 | 38.84% | 41.92% | **+3.08 pp** | **30.0%** | -0.78 | -0.21 |
| +15 | 62.85% | 63.38% | +0.54 pp | 16.7% | -0.44 | -0.03 |

The value of a championship-aware override rises sharply as the player falls behind. When 15 points ahead, the cap-3 expected-points path is already very close to championship-optimal.

## By field size

### 10-player pool

| Gap | Cap 3 | Championship | Lift | Switch |
| ---: | ---: | ---: | ---: | ---: |
| -30 | 6.55% | 12.94% | +6.39 pp | 93.3% |
| -15 | 23.56% | 27.72% | +4.16 pp | 33.3% |
| 0 | 42.94% | 46.81% | +3.87 pp | 20.0% |
| +15 | 66.98% | 68.55% | +1.57 pp | 26.7% |

### 25-player pool

| Gap | Cap 3 | Championship | Lift | Switch |
| ---: | ---: | ---: | ---: | ---: |
| -30 | 6.01% | 11.49% | +5.48 pp | 80.0% |
| -15 | 22.56% | 26.43% | +3.87 pp | 40.0% |
| 0 | 39.43% | 43.90% | +4.47 pp | 33.3% |
| +15 | 65.10% | 65.37% | +0.27 pp | 13.3% |

### 50-player pool

| Gap | Cap 3 | Championship | Lift | Switch |
| ---: | ---: | ---: | ---: | ---: |
| -30 | 5.25% | 9.66% | +4.42 pp | 86.7% |
| -15 | 18.40% | 22.01% | +3.61 pp | 60.0% |
| 0 | 37.54% | 39.55% | +2.01 pp | 33.3% |
| +15 | 60.88% | 61.03% | +0.15 pp | 13.3% |

### 100-player pool

| Gap | Cap 3 | Championship | Lift | Switch |
| ---: | ---: | ---: | ---: | ---: |
| -30 | 4.96% | 8.87% | +3.91 pp | 86.7% |
| -15 | 17.20% | 20.54% | +3.34 pp | 60.0% |
| 0 | 35.45% | 37.43% | +1.98 pp | 33.3% |
| +15 | 58.43% | 58.59% | +0.16 pp | 13.3% |

## Critical conceptual finding

The correct championship rule is **not**:

> trailing = choose a more volatile team.

The championship-optimal alternatives did not, on average, have higher simulated season variance. Their standard-deviation differences from cap 3 were close to zero and were often slightly lower.

The advantage primarily came from:
- differentiation from likely opponent selections
- different remaining-team inventories
- correlation with opponent paths
- preserving or consuming teams that change future uniqueness
- exploiting a different route to first place even when it sacrifices a small amount of expected margin

Therefore the championship layer should maximize simulated first-place share directly rather than apply an arbitrary variance multiplier.

## Concrete historical examples

### 2021 Week 10

Cap-3 selection: PIT, approximately +9 current market.

When substantially behind, some simulated states preferred LAC around +3, accepting a six-point current-market sacrifice and lower remaining EV because PIT-heavy paths had poor catch-up differentiation. When tied or leading, PIT generally remained correct.

### 2023 Week 10

Cap-3 selection: CIN around +5.5.

When behind or, in some fields, tied, PIT/TB/DET around +2.5 to +3 sometimes produced materially higher first-place share despite lower expected margin. With a 15-point lead, CIN generally remained optimal.

### 2024 Week 13

Cap-3 selection: DAL around +4.5.

Some championship states preferred BUF or TB around +6.5. This is important because championship awareness did **not** always mean taking a smaller favorite or more downside. The different inventory/correlation path itself created value.

### 2024 Week 16

Cap-3 selection: BUF around +14.

In some 25-player states, GB was also around +14. Changing from BUF to GB cost almost no current-week market value but materially improved simulated first-place share because it differentiated the remaining path. This is a pure ownership/correlation effect.

### 2023 Week 16

Cap-3 selection: PHI around +14.

When badly behind, CHI around +4.5 could become championship-optimal despite sacrificing roughly 9.5 current spread points. When ahead, PHI remained the correct choice. This is the type of state where a hard three-point cap should be overridden only because direct first-place simulation supports it.

## Production interpretation

### Default mode

Use the cap-3 expected-points allocator:
- sportsbook spread for the current week
- validated future-line forecast for later weeks
- +0.5 remaining-season calibrated-EV threshold before deviating from Biggest Favorite
- maximum three-point current-week sacrifice
- full weekly reoptimization

### Championship mode

Once actual pool standings and opponent inventories are meaningful, compute first-place probability directly for plausible current candidates.

The championship layer may override cap 3 when the simulated first-place-share improvement is material. It should not use a fixed rule such as “if 20 points behind, remove the cap.”

The amount of acceptable expected-margin sacrifice should emerge from the first-place simulation itself.

## Limitations

- Only five modern seasons were available.
- Only Weeks 10, 13, and 16 were sampled.
- Opponent behavior is synthetic, not the user's actual 2026 pool.
- The controlled standings gaps are simplified states.
- Historical field composition and actual 2026 pool behavior may differ.

These results justify the architecture, not a universal numeric switch rule.

## Status

Promote a two-layer V1 design:

1. **Cap-3 expected-points engine** as the default.
2. **Championship Override engine** that uses actual pool standings, burned-team inventories, projected opponent behavior, and correlated Monte Carlo to maximize first-place share.

Do not tune more arbitrary risk parameters before live 2026 data exists.
