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
| 2026 | `1383849993151987712` | current | Supplied current league URL. Live provider object must be ingested before recommendations are enabled. |

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

### Confirmed 2026 change

The league is **no longer Superflex in 2026**.

Do not infer the rest of the 2026 roster/scoring settings from 2025. The current Sleeper league object is authoritative for:

- `roster_positions`
- `scoring_settings`
- `settings`
- team count
- waiver configuration
- keeper configuration
- playoff configuration
- trade configuration

### Rules fingerprint

Each accepted season state should persist a deterministic `rules_fingerprint` computed from normalized scoring, ordered roster positions, waiver/transaction rules, keeper rules, and playoff settings.

A changed fingerprint across seasons creates `LEAGUE_RULE_CHANGED` evidence but does not itself imply whether the change is strategically large or small. The decision layer evaluates the impact.

For FFL, removing `SUPER_FLEX` is strategically material because it changes quarterback replacement value, roster scarcity, waiver need, keeper value, and any future trade-value analysis.

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
5. roster ownership is fresh;
6. rules fingerprint is persisted;
7. no prior-season settings were used as a fallback.

Until then the season may be shown as connected/pending, but no league-specific player values, waiver actions, start/sit actions, keeper values, or roster-need scores should be published.