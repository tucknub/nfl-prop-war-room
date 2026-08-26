# Fantasy League HQ — League Registry Draft

**Status:** Documentation only; no runtime implementation yet.

## Principle

A recurring fantasy league is one logical `league_family`, but each season has a separate provider league ID and a separate authoritative ruleset.

Prior-season settings may be retained for historical analysis, manager behavior, draft/waiver tendencies, keeper history, and longitudinal reporting. They must never be inherited as current-season rules when the current provider league object is available.

If current-season settings cannot be verified, league-specific valuation and recommendation features fail closed rather than falling back to a prior season.

## Franchise Football League

Logical family: `franchise_football_league`

Platform: Sleeper

Known season chain:

| Season | Sleeper league ID | Status | Notes |
|---|---|---|---|
| 2024 | `1112703068749058048` | historical | Referenced by 2025 Sleeper `previous_league_id`. |
| 2025 | `1242463021108838400` | complete / historical | Confirmed cached league object in prior Commissioner Command Center. |
| 2026 | `1383849993151987712` | current / verified | Live Sleeper audit passed on 2026-08-26. |

### Confirmed 2025 historical rules

The 2025 cached provider object reported:

- 10 teams.
- Full PPR (`rec = 1`).
- Passing TD = 6.
- Starters: `QB, RB, RB, WR, WR, TE, FLEX, SUPER_FLEX, DEF`.
- 7 bench slots.
- 1 reserve/IR slot.
- $100 waiver budget.
- 1 keeper maximum.
- 6 playoff teams.
- Trade deadline Week 12.

These are **historical 2025 facts only**.

### Verified 2026 live rules

A temporary read-only GitHub Actions audit fetched the public Sleeper league/users/rosters/drafts resources for the current league ID and passed all accepted FFL checkpoints. The temporary audit workflow/PR is not part of the intended production architecture; its purpose was only to collect live source evidence before the real adapter exists.

Live league facts as of 2026-08-26:

- League name: Franchise Football League.
- Season: 2026.
- Status: `pre_draft`.
- 10 teams / 10 current managers.
- Full PPR (`rec = 1`).
- Passing TD = 6.
- Starter slots, in provider order: `QB, RB, RB, WR, WR, WR, TE, FLEX, DEF`.
- **No Superflex / OP slot.**
- 7 bench slots.
- 1 reserve/IR slot.
- No taxi slots.
- $100 waiver budget.
- 1 keeper maximum.
- 6 playoff teams.
- Playoffs start Week 15.
- Trade deadline Week 12.
- Previous Sleeper league ID is the confirmed 2025 FFL ID.

### Verified 2026 draft state

The live Sleeper draft resource reports:

- Status: `pre_draft`.
- Type: snake.
- 16 rounds.
- 10 teams.
- Draft roster slots: 1 QB, 2 RB, 3 WR, 1 TE, 1 FLEX, 1 DEF, 7 bench.
- Current scheduled start: 2026-09-05 12:00 PM America/Indiana/Indianapolis (16:00 UTC).
- Draft order is not yet assigned in the provider response.

Draft-specific configuration must come from the draft resource. The league object's `settings.draft_rounds` currently reports `3`, which does **not** represent the actual current 16-round draft.

### Current ownership state

All 10 current Sleeper rosters are presently empty and starter lists contain placeholder IDs because the league is pre-draft. Therefore:

- empty ownership must not be interpreted as every player being a free agent;
- Waiver Radar / drop / start-sit ownership features remain suppressed until authoritative roster ownership is initialized;
- draft/keeper preparation can still operate in pre-draft mode;
- keeper status should be re-read as managers make keeper selections.

### 2026 secondary artifact validation

A retained 2026 draft-board artifact is labeled `1QB • FULL PPR • 10 TEAM`. Its 10 manager display names match the live 2026 Sleeper manager set and the prior 2025 FFL manager set.

This artifact is useful as a cross-check, but the live Sleeper response is the authority. The artifact's displayed draft order must **not** be treated as the provider draft order because Sleeper currently reports `draft_order = null`.

### Cross-season rule comparison

Between the confirmed 2025 and live 2026 league objects:

- scoring settings are unchanged;
- overall roster size remains 16;
- `SUPER_FLEX` was removed;
- a third dedicated `WR` starter slot was added in its place;
- other apparent end-of-season/current-leg metadata differences are operational state, not necessarily league-rule changes.

The Superflex → WR change is strategically material because it lowers quarterback scarcity/value while increasing required weekly WR depth.

## Papa Johns

Logical family: `papa_johns`

Platform: Sleeper

Provider league name: `Papa Johns #2`

Known season chain:

| Season | Sleeper league ID | Status | Notes |
|---|---|---|---|
| 2024 | `1041254319653720064` | historical / not yet backfilled | Referenced by the 2025 league object's `previous_league_id`. |
| 2025 | `1237498478561603584` | complete / verified source comparison | Direct predecessor of current 2026 league. |
| 2026 | `1356381517693079553` | current / verified | Live Sleeper audit passed on 2026-08-26. |

### Verified 2026 live rules

Live league facts as of 2026-08-26:

- League name: Papa Johns #2.
- Season: 2026.
- Status: `pre_draft`.
- 12 teams / 12 current managers.
- Full PPR (`rec = 1`).
- Passing TD = 6.
- Passing interception = -1.
- Rushing/receiving yards = 0.1 per yard.
- Rushing/receiving TD = 6.
- Starter slots, in provider order: `QB, RB, RB, WR, WR, WR, TE, FLEX, FLEX`.
- No Superflex / OP slot.
- **No K or DEF starter slots**, even though the raw Sleeper scoring object retains kicking and D/ST scoring fields.
- 6 bench slots.
- Provider setting `reserve_slots = 1`; reserve eligibility flags should be preserved exactly rather than assuming generic IR behavior.
- No taxi slots.
- $150 waiver budget.
- Sleeper `waiver_type = 2`.
- 2-day waiver clear period.
- 1 keeper maximum.
- 6 playoff teams.
- Playoffs start Week 15.
- Trade deadline Week 12.
- QB roster limit = 3.
- Previous Sleeper league ID is the confirmed 2025 Papa Johns ID.

### Verified 2026 draft state

The live Sleeper draft resource reports:

- Status: `pre_draft`.
- Type: snake.
- 15 rounds.
- 12 teams.
- Draft roster slots: 1 QB, 2 RB, 3 WR, 1 TE, 2 FLEX, 6 bench.
- No K, DEF, or Superflex draft slot.
- Current scheduled start: 2026-09-06 12:00 PM America/Indiana/Indianapolis (16:00 UTC).
- Draft order is not yet assigned in the provider response.

As with FFL, the league object's `settings.draft_rounds` reports `3`; the actual current draft resource is authoritative and reports 15 rounds.

### Current ownership state

All 12 current Papa Johns rosters are empty because the league is pre-draft. Therefore ownership-dependent features remain blocked until authoritative roster ownership is initialized.

### 2025 → 2026 rule comparison

The fetched 2025 predecessor and 2026 current league have the same:

- scoring settings;
- ordered roster positions;
- waiver/keeper/playoff/trade configuration;
- team count.

Differences observed are season/status/current-leg reporting fields only. Therefore Papa Johns' current rules fingerprint should be treated as strategically unchanged from 2025 unless a later live provider sync changes the rule fields.

### Normalization lessons from Papa Johns

Papa Johns validates several platform rules the common Fantasy HQ model must handle:

1. A league can have scoring fields for K/DST even when K/DST are not roster positions. Active lineup positions come from `roster_positions`, not from the presence of scoring keys.
2. Reserve/IR configuration can be represented in provider `settings` separately from `roster_positions`; normalize reserve slots and eligibility flags explicitly.
3. Two leagues can both be Full PPR/1QB yet still require materially different player valuation because of team count, starting WR/FLEX depth, FAAB budget, defense usage, bench depth, and other rules.
4. Draft settings must come from the draft resource; both verified Sleeper leagues currently expose misleading `settings.draft_rounds = 3` values relative to their actual draft objects.

## Cross-league 2026 comparison

| Setting | Franchise Football League | Papa Johns #2 |
|---|---:|---:|
| Teams | 10 | 12 |
| PPR | Full | Full |
| Pass TD | 6 | 6 |
| Pass INT | -2 | -1 |
| QB | 1 | 1 |
| RB | 2 | 2 |
| WR | 3 | 3 |
| TE | 1 | 1 |
| FLEX | 1 | 2 |
| Superflex | 0 | 0 |
| DEF | 1 | 0 |
| K | 0 | 0 |
| Bench | 7 | 6 |
| Reserve slots | 1 | 1 provider setting |
| FAAB budget | $100 | $150 |
| Keepers | 1 | 1 |
| Playoff teams | 6 | 6 |
| Draft rounds | 16 | 15 |

This proves the normalized model must be league-specific even when the headline scoring format appears similar.

### Rules fingerprint

Each accepted season state should persist a deterministic `rules_fingerprint` computed from normalized scoring, ordered roster positions, waiver/transaction rules, keeper rules, and playoff settings.

A changed fingerprint across seasons creates `LEAGUE_RULE_CHANGED` evidence but does not itself imply whether the change is strategically large or small. The decision layer evaluates the impact.

## Future registry entries

Add one logical family per regular fantasy league rather than one entry per season:

- `franchise_football_league`
- `papa_johns`
- `mitey_mites`

Each family may contain multiple season/provider IDs and independent season rulesets.

## Import gate

A season becomes `RECOMMENDATION_READY` only when:

1. current provider league object is fetched successfully;
2. scoring rules are normalized with unmapped rules surfaced;
3. ordered roster positions are parsed successfully;
4. user/team identity is resolved;
5. roster ownership is fresh and meaningful for the current league phase;
6. rules fingerprint is persisted;
7. no prior-season settings were used as a fallback;
8. current provider facts agree with any accepted secondary checkpoints, or discrepancies have been explicitly reviewed.

A verified `pre_draft` league may be `RULES_READY` but not `OWNERSHIP_READY`. Ownership-dependent recommendations remain suppressed until roster ownership is initialized.