# Margin V1 — Raw Long/Slow Power + Cap-3 Promotion Gate

Date: 2026-08-23

## Decision

Promote the **raw long/slow market-power forecast** as the conservative V1 source for future games that do not yet have a genuinely posted sportsbook/look-ahead line, beginning in Week 4.

This is a monitored production promotion, not a claim of statistical proof. The historical point-estimate and win-rate evidence are favorable, especially in the modern 18-week era, but bootstrap uncertainty still crosses zero.

## Exact tested policy

- Weeks 1–3: Biggest Favorite default.
- Current week: actual sportsbook market is authoritative.
- Future genuinely posted look-ahead lines: authoritative when available live.
- Future unpriced games: raw long/slow market-power forecast.
- Long/slow power configuration: 32 market periods, half-life 8, ridge 3, current-week market included.
- Candidate evaluation: calibrated current EV + optimal remaining one-use assignment.
- Deviate from Biggest Favorite only when remaining-season calibrated EV improves by at least +0.5.
- Maximum current-week spread sacrifice: 3 points.
- Exactly one pick per week; each NFL team at most once.

The raw model was invoked through the same existing anchored policy path used by the style research, with an empty style lookup so the future valuation function fell back to raw long/slow power.

## Results

### Full 2011–2025

- Mean realized Margin score delta vs Biggest Favorite: **+13.27 points/season**
- Median realized delta: **+23**
- Seasons better / worse: **10 / 5**
- Bootstrap 95% interval for mean actual delta: approximately **[-3.6, +29.13]**
- Mean selected-market delta vs Biggest Favorite: **+1.97**
- Mean calibrated-EV delta: **+1.77**
- Average deviations per season: **2.33**
- Maximum observed current-week spread sacrifice: **2.5 points**

### Modern 2021–2025

- Mean realized Margin score delta vs Biggest Favorite: **+25.0 points/season**
- Median realized delta: **+32**
- Seasons better / worse: **4 / 1**
- Bootstrap interval: approximately **[-3.6, +50.4]**
- Mean selected-market delta: **+0.4**
- Mean calibrated-EV delta: **+0.26**
- Average deviations per season: **1.8**
- Maximum observed sacrifice: **2.5 points**

Modern per-season realized deltas vs Biggest Favorite:
- 2021: +5
- 2022: +32
- 2023: -22
- 2024: +67
- 2025: +43

## Invariants

All passed:
- Weeks 1–3 remain Biggest Favorite.
- Exactly one pick per week.
- No team reused.
- Current-week sacrifice never exceeded the three-point cap.

The unchanged production Week-1 engine and Streamlit dashboard also passed their validation after the historical gate ran.

## Why this supersedes the prior style proposal

The style correction improved future closing-line forecast MAE, but the separate end-to-end allocation gate showed that feeding style into the allocator reduced realized season scores by about 20 points/season versus raw long/slow power.

The contest objective is the season Margin score / probability of finishing first, not future-line MAE. Therefore the raw long/slow forecast is the better V1 decision input even though it is the less accurate intermediate closing-line predictor.

## Live source precedence after promotion

1. `CURRENT_MARKET` — current-week posted market.
2. `POSTED_LOOKAHEAD` — genuinely posted future market.
3. `MARKET_POWER_FORECAST` — raw long/slow market-power forecast for unpriced future games beginning Week 4.
4. `MARKET_RATING_INFERRED` — preseason/Weeks 1–3 fallback before the Week-4 power layer is active.

Team-style inputs are research/watchlist data only in V1 and do not numerically alter the allocator.

## Monitoring rule

Do not retune the model from a handful of 2026 outcomes. Persist every live decision and compare:
- anchor vs final pick;
- forecasted future values vs later posted markets;
- realized selected-team margins;
- inventory opportunity cost;
- championship recommendation when real pool state becomes available.

Revisit the future model only after enough new out-of-sample evidence accumulates or a clear data-quality failure appears.
