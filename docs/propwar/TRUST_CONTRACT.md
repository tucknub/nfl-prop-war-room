# PropWar Trust Contract

## Purpose

PropWar is a decision-support system, not a substitute for the authoritative source that owns a fact or an executable sportsbook price. User-facing wording must preserve that distinction.

This contract applies to the owner and public experiences.

## Source classes

### Factual and displayable as facts

- Historical NFL play-by-play, schedules, player statistics, rosters, and validated role/opportunity counts sourced through nflverse/nflreadpy.
- Sleeper league settings, rosters, ownership, transactions, matchup scores, trending counts, and FAAB fields returned directly by Sleeper.
- Private Margin pool state explicitly recorded by the owner.
- Official results after they are recorded from an authoritative source.

Derived arithmetic from factual inputs may be displayed as factual calculations when the formula is transparent, such as player targets divided by matching team targets.

### Model or heuristic outputs

These must be labeled as estimates, baselines, signals, or model outputs and must never be phrased as factual probabilities:

- Margin model mean margin and historical spread-conditioned rates.
- Future Margin market-power values.
- Market-implied fantasy baselines translated from player prop markets.
- Role-change classifications and sample-strength grades.
- Cross-book price-anomaly and line-shopping heuristics.
- Provider-derived fair probability or EV.

### Unavailable until a trusted source is implemented

Do not fabricate, infer, or present as production facts:

- true route share
- first-read share
- verified current practice progression
- verified weather
- shadow coverage
- man/zone assignment
- forward-looking red-zone targets or goal-line carries without a sourced current feed
- any other metric lacking a documented source and timestamp

## Market freshness rules

### Full player-prop feed

- Provider: ParlayAPI.
- A quote must have a parseable provider age.
- Maximum admitted provider quote age: 120 seconds.
- PropWar snapshot cache: maximum 120 seconds.
- Undated quotes are rejected.
- If no qualifying fresh quotes remain, the deep market workflow fails closed.
- The exact market, line, price, period, and settlement rules must still be verified inside the sportsbook before use.

### No-key market preview

The preview does not expose a reliable per-book provider quote age. It is research/verification context only.

- Cache maximum: 120 seconds.
- It may not be promoted into PropWar Today.
- It may not be described as an execution source.
- Preview anomalies, arbs, middles, and EV rows require an in-book verification.

## Betting language

Automated market discrepancies may use VERIFY, WATCH, PASS, candidate, anomaly, or research language.

They must not be promoted as an automatic BET solely because a provider or peer-consensus threshold fired.

Provider-derived fair value must identify that it is provider-derived, not a proprietary PropWar probability model.

## Fantasy rules

### Market-implied baseline

Sportsbook prop lines translated through league scoring are a current-week market baseline, not a precise fantasy projection or rest-of-season value.

### Start/Sit and waivers

A numeric delta based on the market baseline must be called a baseline or decision-support delta, not a guaranteed projected-points advantage.

### FAAB

PropWar may show factual:

- starting FAAB
- live remaining FAAB when Sleeper exposes it
- completed winning bid history
- median and percentile summaries of completed bids

PropWar must not present its internal heuristic as a recommended, target, aggressive, or maximum FAAB bid until forward validation demonstrates that the bid model is useful.

### Trades

A current-week market baseline is insufficient to issue a season-long ACCEPT or DECLINE recommendation.

- Trade analysis may show current-week baseline deltas and roster-structure context.
- It must explicitly state what it does not value, including rest-of-season role, schedule, injury recovery, age, keeper/dynasty value, and draft picks.
- Automatic trade recommendations must not be promoted into the all-leagues action feed from this baseline alone.

## Role Intelligence

Historical role/opportunity calculations remain valid descriptive research when they reconcile to the canonical play-level data.

The role-change HIGH/MEDIUM/LOW field is a sample-size grade. User-facing labels must call it sample strength, not predictive confidence.

Current-season role data must remain fail-closed until its publication gates pass.

## Margin

Current-week spread values are sourced from the nflverse/nfldata games snapshot used by the engine.

- The spread must be labeled with its source.
- Model mean margin is a model output.
- Loss and 20-plus values are historical spread-conditioned estimates based on 2006-2025 regular-season outcomes, not sportsbook probabilities.
- Future unpriced spreads are model values and must be labeled as such.

## Knockout

The current structural-only design is intentional.

Do not add a survival probability, player-quality ranking, or optimal FAAB bid until projection and opponent-field evidence are validated.

## Fail-closed principle

When a required source, timestamp, identity match, coverage threshold, or validation gate is missing, PropWar should omit the claim or stop that workflow rather than substitute a guessed value.

## Change control

Any future feature that introduces a new numeric claim should document:

1. source/provider
2. observation timestamp or publication boundary
3. formula/transformation
4. validation method
5. whether it is factual, derived, model-based, or heuristic
6. failure behavior when the source is stale or unavailable

A feature that cannot satisfy those requirements should not be promoted into the owner decision workflow.
