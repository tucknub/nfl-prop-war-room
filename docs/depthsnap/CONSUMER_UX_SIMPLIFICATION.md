# DepthSnap Consumer UX Simplification

## Purpose

This phase changes how the existing validated DepthSnap evidence is presented. It does not change Python methodology, exporter calculations, report membership, publication gates, source data, identity rules, hashes, or registry authority.

The interface now follows a three-level information hierarchy:

1. **Immediate football answer.** A deterministic sentence identifies the player, role, direction, current result, or team leader.
2. **Supporting evidence.** Percentages stay paired with their exact numerator and denominator, period, team, role, and context status.
3. **Optional audit detail.** Source versions, schemas, quality codes, exact weekly tables, and other operational fields remain available in collapsed sections or on Data Status and Methodology.

Every consumer sentence is a closed template populated only from existing registry fields. No score, grade, confidence measure, recommendation, projection, or new classification is calculated.

## Presentation authority

Python remains authoritative for formulas, thresholds, membership, original order, and publication state. The web application may:

- select an existing supplied metric;
- group duplicate records so one player appears once for the selected metric;
- filter by existing team, position, metric, direction, or period fields;
- sort current reports by the existing `current.share`;
- sort movement by the existing `movement.percentagePointChange`;
- restore the source order with the consumer-facing **Report order** option.

No registry, fixture, contract schema, manifest, source hash, source-version construction, evidence-team rule, or exporter record was changed for this phase.

## Exact sorting rules

| Surface | Default | Alternatives | Tie behavior |
| --- | --- | --- | --- |
| Backfield Control | Total opportunities; highest `current.share` | Carries; lowest share; Report order | Existing report position, then player/team/position fields |
| Target Hierarchy | Wide receivers; highest `current.share` | Tight ends; All; lowest share; Report order | Existing report position, then player/team/position fields |
| Role Movement — gains | Positive `percentagePointChange`, descending | Report order | Existing report position, then player/team/position fields |
| Role Movement — declines | Negative movement, most negative first | Report order | Existing report position, then player/team/position fields |
| Role Movement — all | Absolute movement, descending | Report order | Existing report position, then player/team/position fields |
| Quick leaders | Existing report order with the first record retained for each player | Report-family tabs | Source order is otherwise unchanged |

The report-order option is always available so a reviewer can compare the presentation directly with the Python-provided order.

## Consumer language

Normal application pages now lead with football language:

- `2025 · Through Week 18` and `Data verified`;
- `Current role`, `Recent change`, and `Team position`;
- `Team hierarchy`, `Compared periods`, and `Data status`;
- `Search DepthSnap` and `Search players and teams`;
- `No recent qualifying report`;
- `How this is calculated`;
- `View player dossier` and `View team dossier`.

Internal terms remain only where appropriate: Methodology, Data Status, developer documentation, tests, internal type/field names, or collapsed technical details.

## Semantic color

Color communicates meaning consistently and is always paired with text and/or an icon:

- green: documented role/share gain, paired with an up arrow, **Gain**, and exact positive pp;
- red/coral: documented decline, paired with a down arrow, **Decline**, and exact negative pp;
- amber: an existing participation or game-context caution, paired with **Caution** text;
- gray: stable or neutral, paired with a minus/stable mark and **Stable** or neutral text;
- teal: brand, navigation, selected controls, links, and current neutral shares.

A high share is not colored green merely because it is high, and a low share is not colored red merely because it is low.

## Surface decisions

### Weekly briefing

The lead finding states the exact before/after change, raw counts, pp movement, and comparison window. Unusual context is an amber supporting note. The first viewport also contains recent gains/declines/cautions, a deterministic team summary, and deduplicated quick leaders.

### Reports

Backfield Control uses a metric selector and shows one row per player for opportunities or carries. Target Hierarchy uses a WR/TE/All selector and shows one row per player. Role Movement defaults to the largest gains and can switch to declines, all movement, or report order. Desktop uses compact rows; mobile rows stack without becoming a compressed table.

### Player dossier and weekly trend

The dossier begins with three compact summaries: Current role, Recent change, and Team position. The weekly view shows one metric and one interactive record per week. Focus or selection announces the exact percentage, numerator/denominator, role, and context. Missing weeks say **No evidence**. A visually hidden textual equivalent mirrors the chart.

The grouped exact-count table is collapsed under **View exact weekly counts**. Technical fields are separately collapsed under **Technical details**.

### Team dossier, search, and evidence

The team page begins with a closed-template role summary and then separates gains, declines, and role hierarchies. Deeper evidence is collapsed. Search results show a player’s position and full team name or a team’s name and abbreviation with direct **View player**/**View team** actions.

The evidence drawer explains the selected result first, retains exact counts and context, links to both dossiers, traps focus, closes with Escape, restores focus to its opening button, and keeps operational fields collapsed.

## State and contract safety

The published, `no_published_week`, unavailable, loading, no-match, not-found, and contract-failure states remain distinct. The interface does not fall back to fixtures or historical data. The active 2026 export continues to truthfully show no published week, while the completed-2025 registry remains test-only historical parity evidence.

## Acceptance

The release acceptance matrix covers:

- deterministic fixture validation and process-cache/fail-closed contract behavior;
- all fixture browser routes and trust pages;
- exact consumer sorting and report-order fallback;
- semantic colors plus non-color labels;
- metric, position, direction, and weekly controls;
- raw numerator/denominator retention;
- one player per selected report metric and one record per weekly period;
- collapsed exact and technical evidence;
- direct dossier links and focus trapping/restoration;
- populated historical 2025 Week 18 evidence;
- active 2026 no-week, unavailable, and contract-failure states;
- 1440, 1280, 1024, 430, and 390 pixel review widths;
- production package creation, smoke tests, and artifact isolation;
- relevant Python exporter, parity, validation, and atomic-publication tests.

Final command results and committed screenshots are recorded in the accompanying review evidence and the pull-request checks.
