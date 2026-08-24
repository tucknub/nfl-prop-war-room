# Live 2026 Future Model — Superseding Addendum

Date: 2026-08-23

This addendum supersedes the future-model portion of `LIVE_2026_MARKET_PRECEDENCE_ADDENDUM.md` and the style-specific wording in `LIVE_2026_DECISION_SPEC.md`.

## Why this changed

The earlier future-line research showed that current-season team style improved prediction of eventual future closing spreads. That was a valid intermediate forecasting result.

A later end-to-end one-use allocation gate showed that directly feeding the style correction into Margin Pool decisions reduced realized season scores versus the raw long/slow market-power future forecast. Because the contest objective is Margin Pool decision quality, the end-to-end result controls production.

## Updated source precedence

At each live decision snapshot:

1. **`CURRENT_MARKET`** — current-week posted/consensus spread. Authoritative for the current game.
2. **`POSTED_LOOKAHEAD`** — genuinely posted future market. Authoritative when it exists at the snapshot.
3. **`MARKET_POWER_FORECAST`** — raw long/slow market-power forecast for future games that remain unpriced, beginning Week 4.
4. **`MARKET_RATING_INFERRED`** — preseason / Weeks 1–3 early fallback for unpriced future games.

## Raw long/slow production configuration

- market window: 32 market periods
- half-life: 8 periods
- ridge: 3.0
- current-week posted market included in the power fit
- future schedule/location known at the snapshot
- no style/EPA/YPP/explosive/turnover numeric correction

## Expected-points policy remains unchanged

Weeks 1–3:
- Biggest Favorite default.

Weeks 4–18:
- Biggest Favorite is the anchor.
- Alternate must improve optimal remaining-season calibrated EV by at least +0.5.
- Alternate may sacrifice at most 3 current spread points in expected-points mode.
- Championship simulation may override only when real pool standings/inventory data makes that layer production-ready.

## Style status

Style is **not** deleted as research evidence. It may remain useful for diagnostics, football context, or a future model family.

For V1 allocation, however:
- it does not change current-week market expectation;
- it does not change future unpriced spreads numerically;
- it does not change the assignment objective.

Any future attempt to restore style to production must pass a new out-of-sample end-to-end allocation gate, not merely improve forecast MAE.

## Evidence references

See:
- `STYLE_ALLOCATION_GATE_RESULTS.md`
- `RAW_POWER_CAP3_PROMOTION_GATE_RESULTS.md`

The production rollout must preserve Week-1 parity and explicitly test Week-4 activation before merge.
