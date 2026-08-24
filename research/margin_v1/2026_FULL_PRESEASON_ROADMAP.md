# 2026 Margin Pool — Full Preseason Roadmap

## Status

**Planning only. Not an 18-week pick sheet.**

This route combines genuinely posted 2026 market lines with a simple market-implied team-rating model for games that are not yet priced. Only the current week's eventual live decision is binding.

## Inputs

- 272 scheduled 2026 regular-season games
- 112 games currently carrying posted spread/total/moneyline data
- 160 currently unpriced games
- Posted lines are retained unchanged.
- Unpriced games are estimated from a ridge-regularized market-implied team rating fit to the 112 currently posted 2026 spreads.
- Neutral-site games receive no home-field adjustment.

Implied home-field adjustment from the current posted market set: **1.73 points**.

Five-fold reconstruction MAE on currently posted lines: **1.81 spread points**.

This cross-validation measures internal coherence of the current market-rating representation. It is **not** evidence that a preseason rating predicts December closing lines to 1.81 points.

## Current optimal provisional route

Raw projected spread objective: **+137.72**

| Week | Team | Opponent | Projected margin | Source |
| ---: | --- | --- | ---: | --- |
| 1 | **LAC** | ARI | **+10.5** | POSTED MARKET |
| 2 | SF | MIA | +10.5 | POSTED MARKET |
| 3 | DET | NYJ | +9.5 | POSTED MARKET |
| 4 | CHI | NYJ | +8.5 | POSTED MARKET |
| 5 | NE | LV | +8.5 | POSTED MARKET |
| 6 | LA | ARI | +13.5 | POSTED MARKET |
| 7 | HOU | NYG | +5.5 | POSTED MARKET |
| 8 | DAL | ARI | +7.81 | MARKET-RATING INFERRED |
| 9 | SEA | ARI | +9.49 | MARKET-RATING INFERRED |
| 10 | IND | MIA | +4.32 | MARKET-RATING INFERRED |
| 11 | KC | ARI | +8.98 | MARKET-RATING INFERRED |
| 12 | CIN | NO | +4.70 | MARKET-RATING INFERRED |
| 13 | DEN | MIA | +5.89 | MARKET-RATING INFERRED |
| 14 | PHI | IND | +4.64 | MARKET-RATING INFERRED |
| 15 | GB | MIA | +7.22 | MARKET-RATING INFERRED |
| 16 | BAL | CLE | +7.58 | MARKET-RATING INFERRED |
| 17 | JAX | WAS | +3.14 | MARKET-RATING INFERRED |
| 18 | BUF | NYJ | +7.46 | MARKET-RATING INFERRED |

Current route composition:
- 7 slots from actually posted markets
- 11 slots from inferred preseason market ratings

The 11 inferred slots are reservations only and should be expected to move substantially as the season develops.

## Forced Week-1 comparison

| Week-1 team | Week-1 current spread | Best full-roadmap objective | Gap to unrestricted |
| --- | ---: | ---: | ---: |
| **LAC** | **+10.5** | **137.72** | **0.00** |
| JAX | +7.5 | 135.75 | -1.97 |
| DET | +7.0 | 134.22 | -3.50 |
| PHI | +4.5 | 133.34 | -4.38 |

Even after extending the planning horizon through Week 18, the current model finds **no opportunity cost to using LAC in Week 1**.

## Current market-implied team ratings

These are latent ratings fitted to the currently posted 2026 game markets, not subjective power rankings.

Top group:
1. LA +3.85
2. BAL +2.86
3. SEA +2.56
4. BUF +2.47
5. DET +2.27
6. KC +2.05
7. SF +1.93
8. PHI +1.64
9. GB +1.62
10. NE +1.43

Bottom group:
- TEN -2.26
- CLE -2.99
- LV -3.02
- NYJ -3.27
- MIA -3.87
- **ARI -5.20**

Arizona's extreme market-implied weakness explains why so many current high-value roadmap spots target ARI with different teams.

## Interpretation

The full preseason roadmap and the stronger six-week posted-market roadmap agree on the only decision that currently matters:

**Week 1 provisional PICK / ANCHOR = Los Angeles Chargers vs Arizona.**

The late-season route should not be defended when new information arrives. Beginning after every completed week, rebuild the path from scratch with:
- actual used teams
- current standings
- newly posted markets
- current-season team style
- current QB/injury state
- opponent inventories
- championship first-place simulation when useful

The purpose of this roadmap is to identify valuable future reservations and likely weak-opponent clusters, not to predict September-through-January picks in August.
