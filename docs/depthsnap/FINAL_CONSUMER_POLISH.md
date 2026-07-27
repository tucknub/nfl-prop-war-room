# DepthSnap Final Consumer Polish

## Scope

This pass is a presentation-only refinement of the validated DepthSnap V1
product. It does not change Python methodology, formulas, thresholds, report
membership, ordering authority, source records, publication gates, schemas,
registry hashes, or the exporter. DepthSnap presents role evidence, not
forecasts.

The work removes repetitive interface detail, improves scanability, and keeps
all exact evidence available through progressive disclosure.

## Home briefing and team snapshot

The Home briefing now uses a local, lightweight role diagram. It is deliberately
non-representational and has a generated accessible name such as “Green Bay
Packers backfield role illustration.” No player likeness or third-party image is
shown.

The populated completed-2025 registry is globally current through Week 18, while
the registry’s selected team snapshot has `teamSnapshot.week = 17`. The product
now displays that source fact as:

> Latest complete team snapshot · Week 17

When the snapshot week equals the registry week, it displays “Team snapshot ·
Week N.” The snapshot is never silently relabeled with the registry-wide week.

## Current report rows

Backfield Control and Target Hierarchy rows show the player/team/position,
current share with its exact numerator and denominator, and the evidence action.
The repeated Role and normal Context columns were removed.

An amber caution appears only when an existing row has a non-`complete`
participation quality or an `unavailable` supporting-context status. Complete
rows with available context have no caution label. Target Hierarchy keeps the
existing WR or TE position in the player identity line when All is selected.

## Result containment

Published report views initially render the first 25 filtered and sorted
players. The interface states “Showing 25 of N players” and reveals the next 25
only after “Show 25 more” is activated. The reveal count is transient UI state
and is never stored in the URL.

Changing the view, team, position, role, metric, direction, or sort resets the
visible count to 25. Reset also restores the report defaults. This containment
does not remove, reorder, or rewrite any supplied report row.

## Role Movement filters

Role Movement adds filters backed only by existing row fields:

- Position: All, RB, WR, TE.
- Role: All roles, RB opportunity, RB carry, WR target, TE target.

Only positions and roles present in the selected source view are offered. A
specific role selects its compatible position. Choosing an incompatible
position clears the role. Position and role are included in copied/deep-linked
URLs and survive reload.

## Normal-game explanation bands

The evidence drawer retains exact overall and normal-game percentages, counts,
labels, and raw technical codes. It adds one deterministic explanation based on
the existing shares:

| Difference: normal share minus overall share | Consumer explanation |
| --- | --- |
| Absolute difference below 2.0 percentage points | Nearly unchanged |
| At least 2.0 points lower | Lower when unusual game situations were excluded |
| At least 2.0 points higher | Higher when unusual game situations were excluded |
| Supporting evidence absent | Normal-game context is unavailable |

The bands are explanatory presentation rules only. They do not create a score,
classification in the registry, prediction, or recommendation.

## Weekly trend

Player dossiers now use an accessible SVG line trend on a fixed 0–100 percent
scale. The chart:

- displays one selected metric at a time;
- uses continuous line segments and never bridges missing weeks;
- labels every week and missing point;
- exposes each point as a focusable button with the exact percentage and count;
- updates a live exact-detail region on pointer or keyboard selection;
- provides a complete screen-reader text equivalent;
- keeps exact multi-metric weekly counts collapsed;
- uses “Normal,” “No evidence,” or an amber caution phrase in the consumer
  quality column while retaining raw quality codes in accessible metadata;
- remains a full-season chart in a contained horizontal scroll region on narrow
  screens.

## Search

Every search result is one full-row link with one trailing action: “View player
→” or “View team →.” The link’s accessible name includes the identity and
destination. Native link keyboard behavior and the combobox’s Arrow/Enter
navigation both remain supported. Matching covers partial names, surnames, team
abbreviations, and full team names using existing aliases.

## Verification boundary

Fixture, active-export, and historical-export browser suites remain separate.
The final historical review uses the temporary validated completed-2025 parity
registry only. It is review evidence, not a substitute for a current-season
publication and not production data.

The acceptance gate covers desktop widths 1440, 1280, and 1024 pixels and mobile
widths 390 and 430 pixels, direct links, keyboard interaction, accessible names,
horizontal overflow, page/console errors, exact evidence preservation, and the
publication-state and production-package suites.

