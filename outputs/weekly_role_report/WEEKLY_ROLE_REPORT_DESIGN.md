# Weekly Role Report Design

## Purpose

Home is a five-minute weekly discovery surface for factual NFL role research. It shows a maximum of 12 default situations across four named categories, then links to the Player, Team, and Game evidence pages.

## Information order

1. `This Week in NFL Roles`
2. Compact season and week controls
3. Selected-state and result-count summary
4. Four category sections with compact evidence cards
5. Collapsed advanced filters
6. Collapsed technical matches
7. Collapsed calculation notes

Every card uses the same shared payload at mobile and desktop widths. Mobile uses one category column; desktop uses two. Categories use both a text label and a symbol/border treatment. No category depends on color alone.

## Card evidence

Each card includes player/team/position/family identity, factual headline, selected-week numerator and denominator, count-weighted prior baseline, percentage-point change, all-play comparison, baseline sample, a short explanation, participation note, and Player/Team/Game links that preserve season and week.

## Default de-duplication

A player may match several technical categories or both RB families. The default report assigns one row per player using this category priority: Box Score Overstated the Role → Opportunity Lost → Opportunity Gained → Strong Opportunity, Weak Production. Each section is capped at 3 cards and the whole report at 12. Technical matches remain available in the collapsed full-results view.
