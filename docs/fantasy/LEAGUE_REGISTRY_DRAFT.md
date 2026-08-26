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

A read-only GitHub Actions audit fetched the public Sleeper league/users/rosters/drafts resources for the current league ID and passed all accepted FFL checkpoints.

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