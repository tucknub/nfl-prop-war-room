# DepthSnap Opportunity Context source map

Date: 2026-07-25

This document inventories source availability for possible future Opportunity
Context research. It does not add a fourth report, change V1 schemas, infer
causation, create a projection, or introduce a universal opportunity score.

## Guardrails

- Carries, targets, receptions, offensive snaps, and total opportunities remain
  distinct measures.
- Receptions are completed touches, not opportunities.
- Player snap totals must not be summed to invent a team snap denominator.
- Roster presence changes do not establish transaction timing or causation.
- A bye, coach change, coordinator change, play-caller change, or quarterback
  change must not be described as causing a role change without supplied
  evidence.
- Vacated work must not be assumed to transfer one-for-one.
- Dimensions that are absent or definitionally ambiguous remain out of V1.

## Availability map

| Dimension | Availability now | Source and definition | Known gap / preservation action |
|---|---|---|---|
| Rushing attempts | Available | Opportunity events with `opportunity_type = carry`; valid rushing attempts exclude kneels, deleted/aborted plays, and two-point attempts | Preserve exact event identity and exclusion definition |
| Receiving targets | Available | Assigned receiver target events from valid pass attempts | Preserve as targets; do not mix with receptions |
| Receptions | Available | Sum of `complete_pass` in game-player production output | Preserve separately as completed touches |
| Total RB opportunities | Available | RB carries plus RB targets within the documented opportunity universe | Keep distinct from carry share |
| Player offensive snaps | Available in the underlying snap source | `snap_counts.offense_snaps` is loaded by the current pipeline | It is discarded from current published outputs; preserve it in a future normalized source layer |
| Player snap share | Available | Canonical `snap_share` from the supplied snap source | Keep the source denominator semantics; do not reverse-engineer a team count |
| Team snap denominator | Unavailable / ambiguous | No exact team offensive-snap denominator is published | Do not sum player snaps; require an authoritative team denominator field |
| Yards to goal / field position | Exactly derivable from play-by-play | `yardline_100` on each source play | Currently reduced to zone booleans; preserve the raw value before aggregation |
| Inside-20 usage | Available | Current `red_zone` flag where yards to goal is 20 or less | Preserve current definition |
| Inside-15 usage | Exactly derivable from play-by-play | `yardline_100 <= 15` | Not currently retained; add only to a future normalized layer |
| Inside-10 usage | Available | Current `inside_10` flag | Preserve current definition |
| Inside-5 usage | Available | Current `inside_5` flag | Preserve current definition |
| Goal-to-go | Unavailable / definitionally ambiguous | No explicit normalized goal-to-go field is retained | Do not infer until the source column and definition are frozen |
| Down | Available in underlying play-by-play | Raw `down` | Currently reduced to context flags; preserve exact down in a future normalized layer |
| Distance to first down | Available in underlying play-by-play | Raw `ydstogo` | Currently reduced to context flags; preserve exact distance |
| Third/fourth-and-short | Available | Current `short_yardage`: down 3 or 4 with 2 or fewer yards to go | Preserve as a supplied context, not a causal label |
| Two-minute context | Available | Final 120 seconds of either half in regulation | Preserve the exact clock definition |
| Early down | Available | Down 1 or 2 | Existing normalized context |
| Passing down | Available | Down 3 or 4 | Existing normalized context; it is not a pass prediction |
| Score state | Available | Leading, trailing, and within-seven flags from score differential | Preserve descriptive state only |
| Quarter | Available | Regulation quarter flags 1 through 4 | Preserve; do not interpolate overtime context |
| End-zone target | Available | Target air yards at least the remaining yards to goal | Preserve the exact documented definition |
| Roster arrivals/departures | Partially derivable | Weekly roster presence and supplied team assignment | Exact transaction timestamps and transaction reasons are not preserved |
| Team changes/trades | Available at weekly identity grain | GSIS player ID plus supplied weekly team | Use stable player ID; never infer by name |
| Bye-week marker | Exactly derivable with a complete schedule | No scheduled regular-season game for a team in that week | No explicit normalized marker is currently written |
| Head-coach change | Unavailable | No authoritative coaching source is present | Keep out of V1 |
| Offensive-coordinator change | Unavailable | No authoritative coaching source is present | Keep out of V1 |
| Play-caller change | Unavailable | No authoritative play-caller source is present | Keep out of V1 |
| Quarterback regime change | Unavailable as supplied metadata | QB participation could be observed, but no authoritative regime field exists | Do not infer a regime from snaps, names, or box-score usage |

## Current normalized layers

The current Python pipeline already preserves these reusable descriptive layers:

- canonical player-week-role evidence;
- situational player-game evidence;
- game-player usage with carries, targets, and receptions kept separate;
- opportunity events with role-relevant context booleans;
- partial-game status and reasons;
- identity, join, and source coverage;
- source and output hashes;
- completed-week checks.

The current opportunity event output retains:

- all-play and normal-game context;
- early down;
- passing down;
- third/fourth-and-short;
- two minute;
- inside 20;
- inside 10;
- inside 5;
- end-zone target;
- leading;
- trailing;
- close score;
- regulation quarter.

## Fields to preserve before a future Opportunity Context phase

A future-compatible exporter-side normalized source layer should preserve, when
the validated inputs supply them:

- stable season, week, game, play, team, and player identities;
- opportunity type;
- carry/target/reception distinction;
- raw offensive snaps and supplied player snap share;
- raw yards to goal;
- raw down and distance;
- explicit schedule participation/bye marker;
- weekly roster team presence;
- source version, generated timestamp, run identifier, and file hashes.

That normalized layer should not be added to frozen V1 public JSON and should
not be interpreted as a prediction surface.

## Known source gaps

The following require new authoritative metadata or a frozen definition before
public use:

- exact team offensive-snap denominators;
- explicit goal-to-go;
- transaction timing and transaction reason;
- head-coach chronology;
- offensive-coordinator chronology;
- play-caller chronology;
- quarterback-regime chronology.

Raw play-by-play, roster, schedule, and snap snapshots referenced by the
completed-2025 source manifest are not committed as a public bridge input in
this worktree. Ordinary CI must continue to use committed validated outputs and
must not make live network calls.
