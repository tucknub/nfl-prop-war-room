# NFL Margin Pool V1 — Live 2026 Decision Contract

Status: research architecture frozen for live implementation.

This document is the operating contract for the 2026 Margin Pool. Historical research files remain useful evidence, but this file governs the live decision process unless new out-of-sample 2026 evidence justifies a change.

## Contest objective

One NFL team is selected each regular-season week. A team can be used only once. Weekly score is the selected team's actual point differential. The final objective is to finish with the highest cumulative Margin Pool score.

The live system therefore has two related objectives:

1. **Expected-points objective:** maximize the quality of our remaining one-use inventory and expected cumulative margin.
2. **Championship objective:** once standings and opponent inventories matter, maximize probability of finishing first rather than blindly maximizing expected points.

## Non-negotiable operating principle

Only the current week's selection is a commitment.

Every future assignment is provisional and is deleted/rebuilt after each completed week.

The system must never present a preseason or early-season 18-week route as a locked pick sheet.

---

# 1. Required live inputs

## Our pool state

Required every week:
- current cumulative Margin Pool score
- all teams already used
- current week number
- pool pick deadline
- whether picks are visible before kickoff

## Opponent/pool state

When available:
- entrant name/ID
- current cumulative score
- teams already used by entrant
- historical weekly selections
- current pick if visible
- eliminated/inactive status if applicable

Derived opponent features:
- remaining inventory strength
- overlap with our remaining inventory
- frequency of choosing Biggest Favorite
- tendency to save elite teams
- favorite-spread distribution of past picks
- likely current-week ownership by team

If actual opponent data is unavailable, use the synthetic field only as a sensitivity range and clearly label the championship estimates as lower-confidence.

## NFL market state

For every current-week game:
- consensus spread
- book/source count if available
- opening spread when available
- current spread
- timestamp
- home/away/neutral
- game time

The current sportsbook spread is the primary V1 current-game expectation.

Do not add EPA, yards/play, explosive rate, turnovers, or total to the current-game expectation unless future out-of-sample evidence proves incremental value.

## Future NFL state

For all remaining scheduled games:
- season
- week
- team/opponent
- home/away/neutral
- game date/time

Future value model inputs:
- long/slow market-derived team power
- entering team-style features validated for future-line prediction
- recent EPA/play differential
- passing EPA differential
- rushing EPA differential
- yards/play differential
- explosive-play differential

The style layer is permitted only for forecasting future weeks whose sportsbook lines do not yet exist.

## Context/watchlist data

Track separately from the core statistical model:
- starting QB status
- major QB injury/news
- starter-rest/motivation concerns late in season
- severe weather only when genuinely material
- schedule changes

These should initially trigger warnings/manual review rather than silently rewrite the model with unvalidated numeric weights.

---

# 2. Current-week expected-margin layer

For each unused team playing in the current week:

`current_market_margin = team-perspective consensus spread`

Apply the residual-centered empirical calibration to obtain:
- calibrated expected margin
- P(loss)
- P(win by 10+)
- P(win by 20+)
- P(win by 30+)
- full simulated integer margin distribution

Do not use game total in V1 distribution calibration.

---

# 3. Future-week valuation layer

For every unused team × remaining future week:

1. Create a market-derived long/slow team-strength forecast.
2. Add only the validated core team-style correction.
3. Convert projected spread to calibrated expected margin using the same empirical residual framework.
4. Increase forecast uncertainty with horizon; do not treat a Week-15 projection in Week 4 as equally certain as next week's projection.

Future sportsbook lines, once they actually become available, replace the old forecast for that current decision week.

Historical backtests must never use eventual future closing lines as information available earlier.

---

# 4. Expected-points allocator

## Weeks 1-3

Default to the largest available sportsbook favorite.

Reason: insufficient current-season team-style history exists for the validated future-style layer.

A manual exception may be considered only for extraordinary QB/injury/news information that the market clearly has not incorporated, and must be explicitly documented.

## Weeks 4-18

### Anchor

Biggest available current-week favorite.

### Alternative evaluation

For every reasonable unused current-week candidate:

`candidate total value = calibrated current-week EV + optimal calibrated EV across remaining weeks after burning candidate now`

Solve the remaining weeks as an exact one-team-per-week, one-use-per-team assignment.

### Default deviation requirement

An alternate must improve total remaining-season calibrated EV by at least:

**+0.5 expected Margin Pool points**

versus taking the Biggest Favorite now.

### Default risk cap

Under expected-points mode, the alternate may not sacrifice more than:

**3 current spread points**

versus the Biggest Favorite.

This cap is a default risk policy, not a fundamental law. It may be overridden only by the Championship Override layer described below.

---

# 5. Championship Override layer

This layer becomes increasingly important once actual pool standings and opponent inventories are informative.

It should be available all season but should not manufacture a contrarian pick when opponent data is weak.

## Candidate simulation

For each serious current-week candidate:

1. Start from our actual current score and used-team inventory.
2. Force that candidate as this week's pick.
3. Re-optimize our remaining inventory from the next week forward.
4. Simulate remaining NFL game margins using the snapshot-available empirical margin distributions.
5. Simulate each opponent from their actual score and used-team inventory.
6. Use opponent-specific pick tendencies where enough history exists; otherwise shrink toward a generic field model.
7. Preserve shared-game correlation: if multiple entrants select the same NFL game/team, they receive the same simulated outcome in that trial.
8. Calculate our expected first-place share, outright-first probability, tie-for-first probability, and score distribution.

## Override objective

Choose the candidate that maximizes **expected first-place share**, subject to data-quality safeguards.

The model must report the cost of the override versus cap 3:
- current spread sacrifice
- calibrated current EV sacrifice
- remaining-plan EV sacrifice
- change in simulated first-place share
- projected ownership/differentiation

## Important research conclusion

Do **not** implement:

`trailing -> increase variance multiplier`

Historical snapshot research did not show that championship-optimal alternatives were consistently higher variance.

The advantage frequently came from:
- avoiding duplicated opponent paths
- differentiated team inventory
- ownership/correlation
- preserving a unique future route
- consuming a team competitors had already burned

Therefore championship risk must be evaluated through first-place simulation directly.

## Historical guidance — not a hard live rule

Modern 2021-2025 snapshots suggested:

| Position vs leader | Historical override frequency | Avg current-spread sacrifice when optimizing first place | Avg remaining-plan EV sacrifice | Mean first-share lift |
| --- | ---: | ---: | ---: | ---: |
| 30 behind | 86.7% | 2.78 | 3.59 | +5.05 pp |
| 15 behind | 48.3% | 1.40 | 1.08 | +3.75 pp |
| Tied | 30.0% | 0.78 | 0.21 | +3.08 pp |
| 15 ahead | 16.7% | 0.44 | 0.03 | +0.54 pp |

These figures explain expected behavior; they must **not** be hard-coded as switching thresholds.

Actual 2026 standings and inventories control the live decision.

---

# 6. Weekly recommendation board

The user-facing decision board must be simple even though the engine underneath is complex.

Minimum columns:

| Rank | Team | Current Spread | Calibrated Margin | P(Loss) | P(20+) | Future Cost | Total Season EV Delta vs Anchor | First-Place Share | First-Share Delta | Ownership | Status |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |

Status values:
- **PICK** — final recommended selection
- **ANCHOR** — Biggest Favorite benchmark
- **SAVE** — valuable now but future opportunity cost is too high
- **PIVOT** — best practical alternative if news/market changes
- **CHAMP OVERRIDE** — selected primarily because it raises first-place probability
- **AVOID** — poor expected current/future value or unacceptable downside
- **USED** — unavailable permanently

## Required explanation for final PICK

Always state:
- why this team beats the anchor or why the anchor remains best
- current market edge/value
- future opportunity cost
- whether the 3-point cap binds
- first-place simulation result if standings mode is active
- what specific news/line movement would change the pick

---

# 7. Weekly operating cadence

## Monday/Tuesday — Roadmap

After the prior week finishes:
- lock actual prior-week margin
- mark selected team used
- update standings
- ingest all opponent selections when available
- refresh remaining schedule
- rebuild team strength/style state
- rerun full remaining assignment
- produce preliminary current-week top candidates and SAVE list

Do not make a final selection yet unless the contest deadline requires it.

## Wednesday/Thursday — Serious board

- refresh market
- update QB/injury watchlist
- calculate cap-3 expected-points board
- calculate preliminary championship field simulation if standings data is available

## Friday/Saturday — Finalists

- narrow to PICK / ANCHOR / PIVOT
- review meaningful line movement
- update likely opponent ownership
- rerun first-place simulations

## Final pre-deadline run

As close to the pool deadline as practical:
- final market refresh
- official inactives if available before deadline
- weather only if materially relevant
- final opponent/pick information allowed by pool rules
- rerun expected-points allocator
- rerun championship override
- output one final PICK

---

# 8. Data-quality gates

No final recommendation may be labeled production-ready unless:

- schedule coverage is complete for all remaining weeks
- current-week spreads have valid timestamps
- used-team list is valid and contains no duplicates
- candidate is unused
- exactly one future team can be assigned per remaining week
- no team is assigned more than once
- future forecasts do not contain eventual future market leakage
- current pool score and standings timestamp are known for championship mode

If opponent data is incomplete, downgrade championship estimates and show cap-3 expected-points recommendation as the authoritative fallback.

---

# 9. State that must be persisted after each week

Our state:
- season
- completed week
- selected team
- closing/decision-time spread
- actual margin
- cumulative score
- used teams

Decision audit:
- Biggest Favorite anchor
- cap-3 recommendation
- championship recommendation
- actual final pick
- total-season EV delta at decision time
- estimated first-place-share delta
- reason for any manual override
- model/data version
- market timestamp

Opponent state:
- weekly pick
- actual margin
- cumulative score
- used teams

This creates a fully auditable 2026 record and lets us evaluate the live model without hindsight rewriting.

---

# 10. What V1 intentionally does not do

Do not add these merely because they sound sophisticated:
- current-game EPA override of sportsbook spread
- game-total-based blowout adjustment
- turnover-form adjustment
- arbitrary 'variance when behind' multiplier
- subjective preseason power rankings mixed into current market without validation
- locked preseason 18-week pick path
- automated UI complexity before live decision correctness is proven

---

# 11. Preseason 2026 mode

Before Week 1:

Use the system to create a **roadmap only**:
- identify premium future spots
- estimate team scarcity
- identify teams likely to be valuable one-use assets
- flag schedule clusters
- show several near-optimal provisional routes

Do not label Weeks 2-18 as committed selections.

For Week 1 itself, current market Biggest Favorite is the V1 default under the frozen research rules.

---

# 12. Frozen V1 hierarchy

When the 2026 season starts, decision priority is:

1. **Validity / no leakage / unused-team constraint**
2. **Current sportsbook market**
3. **Cap-3 remaining-season expected-points allocator**
4. **Actual pool standings + opponent inventories**
5. **Championship first-place simulation override**
6. **Manual football-news review for exceptional information**

The model exists to improve the contest decision, not to maximize modeling complexity.
