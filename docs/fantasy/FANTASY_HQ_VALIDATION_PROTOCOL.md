# Fantasy League HQ — Validation Protocol

**Status:** Pre-implementation validation contract

## Goal

Fantasy League HQ must be validated as a point-in-time decision system rather than judged from hindsight. It may reuse existing PropWar historical NFL features, role research, and backtest patterns, but it must not silently import future information or provider state that did not yet exist at the decision timestamp.

## Validation principles

1. **Point-in-time only.** Every replay decision sees only evidence available before the replay timestamp.
2. **Current league rules only.** Historical seasons use that season's actual scoring/roster rules; current seasons never inherit old rules.
3. **Ownership is timestamped evidence.** A waiver recommendation is invalid if roster ownership is not known as of that point.
4. **Provider phase matters.** Pre-draft empty rosters are not a free-agent pool.
5. **Draft resource is authoritative for draft configuration.** Do not validate draft behavior from conflicting league convenience fields.
6. **No retrospective recommendation editing.** Persist the original recommendation/evidence version.
7. **Fail closed.** Missing identity, ownership, rules, or required evidence suppresses the affected recommendation rather than being silently filled.

## Existing PropWar foundations to reuse

- `before_target_mask` / historical feature-window leakage checks.
- rolling features shifted before the target week.
- normal-game context and partial-game handling.
- canonical 2018–2025 role research.
- historical role-report replay patterns.
- historical signal component audits.

Do not assume an older model/weight is correct for fantasy simply because its infrastructure is reusable.

## Stage 1 — Platform-state correctness

For each connected league, verify exact parity with provider facts before testing recommendations.

### Rules parity

- team count
- ordered roster positions
- scoring settings
- waiver/FAAB rules
- keeper rules
- playoff/trade rules
- unmapped custom settings surfaced

### Draft parity

- provider draft ID
- status/type
- rounds
- team count
- slot counts
- start time
- draft order when assigned

A provider draft object wins over conflicting draft convenience fields in the league settings. Verified acceptance fixture: 2026 FFL has `league.settings.draft_rounds = 3` but an actual 16-round Sleeper draft resource.

### Manager/team parity

- stable provider manager identities
- seasonal roster/team IDs
- user's team resolved through provider ownership

### Roster parity

When ownership is initialized:

- every platform player retained
- starter/bench/IR/taxi state exact
- unresolved identities retained and reported

### Pre-draft guard

For a `pre_draft` league with empty/uninitialized rosters:

- rules may be marked ready;
- draft preparation may be enabled;
- ownership must remain not-ready;
- waiver/drop/start-sit recommendations must be suppressed;
- all NFL players must not be labeled free agents;
- the first valid ownership population creates one initialization transition rather than thousands of fake transaction events.

## Stage 2 — Identity correctness

Measure:

- direct authoritative ID resolution rate
- externally bridged ID resolution rate
- reviewed fallback rate
- unresolved rate
- ambiguous/conflicting rate

Any duplicate-name case must demonstrate that team/provider ID context prevents cross-player contamination.

## Stage 3 — Change-event correctness

Replay controlled snapshots and verify exact deterministic events:

- roster add/drop
- player becomes available
- starter/IR changes
- FAAB changes
- league-rule changes
- draft-state changes
- ownership initialization

Unchanged repeated syncs create no duplicate event history.

## Stage 4 — Historical fantasy decision replay

Reconstruct historical decision timestamps using only information that existed then.

Candidate replay families:

- waiver add ranking
- drop/replacement comparison
- start/sit decisions
- early-season role alerts

Compare staged evidence sets rather than immediately testing one opaque score:

1. projection/baseline only
2. + PropWar usage/role evidence
3. + market evidence when historically available
4. + matchup/opponent context
5. + league-specific roster need

Evaluate whether each added layer improves the relevant decision metric. Do not assign production weights merely because a component sounds useful.

## Stage 5 — Early-season prior research

Test the existing `PRIOR_HEAVY / CURRENT_BLEND / CURRENT_STRONG` concept against historical early-season replays.

Candidate questions:

- how quickly should prior-season player role decay?
- does team/roster change require faster prior decay?
- does validated current role improve waiver/start decisions after Week 1?
- when does current-season role become more informative than positional/prior fallback?

Existing fixed blend weights are challengers, not production truth.

## Stage 6 — Prospective 2026 audit

Persist every actionable recommendation with:

- generation timestamp
- league/rules fingerprint
- Player Evidence version
- source freshness
- exact action and reason codes
- unavailable/blocked evidence

Do not overwrite recommendations when evidence changes later. Append a new record.

At season end, audit:

- recommendation usefulness by family
- false positives caused by transient roles
- suppressed recommendations that would have been unsafe due to stale/missing ownership
- value of market confirmation
- value of role evidence vs baseline/projection-only alternatives
- early-season prior behavior

## Promotion rule

A recommendation family is production-ready only after:

1. state/identity correctness passes;
2. point-in-time replay shows useful incremental performance or decision quality;
3. known failure modes have suppression rules;
4. prospective logging is enabled;
5. no opaque component is promoted solely by subjective weighting.
