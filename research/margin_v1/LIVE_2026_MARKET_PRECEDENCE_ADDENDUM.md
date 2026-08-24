# Live 2026 Market Precedence Addendum

This addendum is part of the frozen `LIVE_2026_DECISION_SPEC.md` contract.

## Rule

At a live decision snapshot, use the best information that is **genuinely available at that snapshot**.

For every team-game valuation, source precedence is:

1. **Current-week posted/consensus market** — authoritative for the current game.
2. **Genuinely posted look-ahead market** — authoritative for a future game if that line is already available at the current snapshot.
3. **Validated future-line model** — long/slow market power plus the validated current-season style correction for future games that are still unpriced once enough 2026 in-season style history exists.
4. **Market-implied preseason/early-season fallback** — used only when a future game is unpriced and the validated in-season style layer is not yet available.

A real future line available today must not be thrown away merely because the historical backtest had to forecast that horizon. Historical tests prohibit using a line that did not exist at the historical decision point; live operation may and should use information that truly exists now.

## Audit requirement

Every live valuation row must carry:
- `value_source`
- snapshot timestamp
- raw spread/forecast used
- whether the value was posted or inferred

The weekly audit should make it possible to reconstruct exactly what information was used when the decision was made.

## Confidence hierarchy

`CURRENT_MARKET` and `POSTED_LOOKAHEAD` are observed market inputs.

`STYLE_FORECAST` and `MARKET_RATING_INFERRED` are model outputs and should be labeled as such. The UI must never make inferred December spreads look like posted sportsbook lines.
