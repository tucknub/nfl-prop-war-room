# Weekly Role Report Screening Rules

These are configurable presentation screens, not detector rules and not claims about future role persistence.

## Shared baseline

- Selected row: public-primary canonical row for the selected season and week.
- Baseline: up to 4 earlier qualifying games for the same player, team, family, and season.
- Baseline minimum: 2 prior games after Week 2.
- Week 2 exception: 1 prior game because only Week 1 can exist; the sample is always shown.
- Share calculation: summed player opportunities divided by summed matching team opportunities. Weekly percentages are never averaged.
- Confirmed partial games: excluded by the existing public-primary definition.
- Suspected partial games: included and labeled.

## Thresholds

- Minimum absolute change for gained/lost: 15%.
- Minimum current team denominator: 10.
- Minimum current raw opportunities for gained, context-overstated, and strong-opportunity screens: {'rb_carry_share': 6, 'rb_opportunity_share': 8, 'wr_target_share': 5, 'te_target_share': 4}.
- Lost-role minimum prior share/raw: 25% / 5.
- Context-overstated minimum all-play minus normal-game share gap: 10%.
- Context-overstated minimum opportunities outside normal-game context: 2.
- Strong-opportunity minimum share/useful contexts: 25% / 2.
- Weak-production maximum yards per documented opportunity: 3.0.

## Deterministic ordering

Within each category: larger absolute share change, larger selected-week raw opportunity count, larger selected-week team denominator, then alphabetical player name. No weighted score is calculated.
