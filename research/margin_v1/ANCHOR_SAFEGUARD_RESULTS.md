# Margin Pool V1 — Anchored Current-Sacrifice Safeguard Results

Date: 2026-08-23

## Scope

This gate keeps the previously development-selected **+0.5 remaining-season calibrated-EV deviation threshold fixed** and adds a hard maximum current-week spread sacrifice. The goal is to eliminate the rare extreme save/burn behavior (17.5 spread points in the uncapped historical development sample) without sacrificing the expected-value benefit of the Biggest-Favorite-anchored allocator.

Candidate caps were 2, 3, 4, 5, 6, 7, 8, 10, 12 spread points plus an uncapped control (`999`). Cap selection for the formal fixed-cap test used **2011–2020 only**; 2021–2025 was reported afterward as a later evaluation period.

The +0.5 anchor threshold itself was not retuned in this gate.

## Summary

| Max current sacrifice | 2011–20 BW3 EV edge vs BF | 2021–25 BW3 EV edge vs BF | Full BW3 EV edge | Dev max sacrifice | Later max sacrifice |
|---:|---:|---:|---:|---:|---:|
| 2 | +5.27 | +1.38 | +3.98 | 2.0 | 2.0 |
| 3 | **+6.63** | **+2.46** | **+5.24** | 3.0 | 2.5 |
| 4 | **+7.24** | **-0.45** | +4.68 | 3.5 | 4.0 |
| 5 | +6.12 | +2.77 | +5.00 | 5.0 | 4.5 |
| 6 | +6.12 | +2.77 | +5.00 | 5.0 | 4.5 |
| 7 | +6.12 | +2.87 | +5.04 | 5.0 | 7.0 |
| 8 | +6.12 | +2.87 | +5.04 | 5.0 | 7.0 |
| 10 | +6.12 | +2.87 | +5.04 | 5.0 | 7.0 |
| 12 | +6.12 | +2.87 | +5.04 | 5.0 | 7.0 |
| Uncapped | +6.47 | +2.87 | **+5.27** | **17.5** | 7.0 |

All figures above are calibrated expected-margin points per season using the BW=3 residual-centered empirical model.

## Formal development-only winner

The predeclared fixed-cap selection rule was: **maximize 2011–2020 mean BW=3 calibrated-EV gain among finite caps; ties prefer the smaller cap.**

That rule selected **cap 4**:

- Development BW3 EV edge: **+7.24 points/season**
- Development market-value edge: **+9.0**
- Development maximum weekly sacrifice: **3.5 points**
- Development EV retention vs uncapped: **111.8%**

However, without retuning, cap 4 produced in 2021–2025:

- BW3 EV edge vs Biggest Favorite: **-0.45 points/season**
- Market-value edge: **-0.3 points/season**
- 2 EV-positive seasons, 3 EV-negative seasons
- Maximum weekly sacrifice: **4.0 points**

The five-season bootstrap interval is wide and crosses zero, but the point estimate is negative. Therefore the formal cap-4 rule does **not** clear the modern-era promotion gate.

## Cap 3 is a strong post-hoc risk candidate, not a locked policy

After seeing the full safeguard table, cap 3 is clearly attractive:

- Development BW3 EV edge: **+6.63**
- Later 2021–2025 BW3 EV edge: **+2.46**
- Full 2011–2025 BW3 EV edge: **+5.24**
- Uncapped full BW3 EV edge: **+5.27**
- Development maximum weekly sacrifice: **3.0**
- Later maximum weekly sacrifice: **2.5**

Thus cap 3 retained essentially all of the uncapped full-period expected value while eliminating the 17.5-point historical sacrifice failure mode.

But **cap 3 cannot be promoted simply because its 2021–2025 line is attractive**. The later period has now been inspected. Treating it as an untouched holdout after selecting cap 3 would be invalid.

## Other observations

- Cap 2 is genuinely conservative but gives up meaningful expected value: full BW3 edge falls to **+3.98**.
- Caps 5–12 behave similarly because the policy rarely wanted sacrifices in those ranges; they retain positive later EV but do not solve the policy-selection question as cleanly as a smaller cap.
- The uncapped `999` control exactly reproduced the original fixed +0.5 anchor policy: maximum absolute market, EV, and actual-score differences were all **0.0**.
- Realized-score differences remain secondary evidence because individual game margins are extremely noisy relative to market expectation.

## Research decision

1. **Do not production-lock cap 4.** It won the formal development optimization but failed the later point-estimate EV gate.
2. **Do not production-lock cap 3 from this table alone.** It is an attractive post-hoc risk-control candidate but the later sample has already been observed.
3. **Reject the uncapped policy as the preferred risk architecture.** The 17.5-point historical sacrifice is an avoidable failure mode, and finite caps can preserve nearly all expected value.
4. **Next gate:** simulate cap selection walk-forward. For each historical test season, choose the safeguard using only prior seasons, then apply that choice to the unseen next season. Favor a risk-regularized selection rule rather than simply maximizing historical EV if the walk-forward evidence supports it.
