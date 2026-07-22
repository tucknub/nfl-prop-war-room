# PropWar Three-Report Launch MVP

## Product contract

The launch product contains exactly three reports released together:

1. Backfield Control
2. Target Hierarchy
3. Role Movement

Raw all-play player counts and matching same-team denominators are the methodology authority. Normal-game values are supporting context only.

## Included public surfaces

- Home
- Reports
- Teams
- Players
- Games
- Advanced Research
- Methodology

## Explicitly excluded

- Sportsbook odds
- Betting picks or recommendations
- Fantasy lineup advice
- Proprietary projections
- League sync
- Injury claims without a validated source
- Route, first-read, coverage, or tracking fields absent from trusted committed data
- Any fourth report

## Report boundaries

### Backfield Control

Closed views:

- Carries
- Total RB opportunities

### Target Hierarchy

Closed groups:

- WR targets
- TE targets

### Role Movement

Closed role families:

- RB carry share
- RB opportunity share
- WR target share
- TE target share

Role Movement is descriptive. It does not claim that a role change will persist.

## Acceptance requirements

- The Reports page exposes exactly the three locked reports.
- Every displayed share preserves its raw player count and matching team denominator.
- All-play values remain primary.
- Normal-game values are labeled supporting context.
- Missing values remain unavailable rather than silently becoming zero or an estimate.
- Existing locked role definitions, detector rules, historical validation fingerprints, and canonical data contracts remain unchanged.
- Team, Player, Game, Reports, and Advanced Research outputs reconcile to the same underlying data.
- The public navigation contains a dedicated Methodology page.

## Commercial validation boundary

This build prepares a testable product experience. It does not add billing or claim market validation. Payment work begins only after the three-report workflow passes functional and data-quality review.
