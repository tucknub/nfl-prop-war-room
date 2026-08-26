# Fantasy League HQ — Sleeper Historical Backfill Audit

**Audit date:** 2026-08-26  
**Status:** Source audit / implementation evidence; no Fantasy HQ runtime behavior changed.

## Scope

A temporary read-only audit walked the approved `previous_league_id` chains for the two current Sleeper leagues and fetched, for each available 2024–2026 season instance:

- league object;
- users/managers;
- rosters;
- draft resource and picks;
- Week 1–18 matchups;
- Week 1–18 completed transactions.

The temporary workflow is evidence gathering only and is not part of the production design.

## Historical completeness result

The historical Sleeper data is sufficiently complete to support backfill work.

### Franchise Football League

| Season | Teams | Manager continuity | Draft | Matchup weeks returned | Completed transactions |
|---|---:|---:|---|---:|---:|
| 2024 | 10 | 9/10 into 2025 | complete, 16 rounds | 18 | 244 |
| 2025 | 10 | 10/10 into 2026 | complete, 16 rounds | 18 | 248 |
| 2026 | 10 | current | pre-draft, 16 rounds | 0 pre-season | 0 pre-season |

### Papa Johns #2

| Season | Teams | Manager continuity | Draft | Matchup weeks returned | Completed transactions |
|---|---:|---:|---|---:|---:|
| 2024 | 12 | 11/12 into 2025 | complete, 15 rounds | 18 | 246 |
| 2025 | 12 | 12/12 into 2026 | complete, 15 rounds | 18 | 260 |
| 2026 | 12 | current | pre-draft, 15 rounds | 0 pre-season | 0 pre-season |

This manager continuity is high enough to make prior-season manager behavior potentially useful context, while still requiring uncertainty/recency treatment rather than assuming manager behavior is permanent.

## Transaction composition

### Franchise Football League

2024 completed transactions:

- 168 waivers;
- 73 free-agent transactions;
- 2 trades;
- 1 commissioner transaction.

2025 completed transactions:

- 188 waivers;
- 53 free-agent transactions;
- 4 trades;
- 3 commissioner transactions.

### Papa Johns #2

2024 completed transactions:

- 89 waivers;
- 156 free-agent transactions;
- 1 trade.

2025 completed transactions:

- 91 waivers;
- 168 free-agent transactions;
- 1 trade.

This supports historical waiver/FAAB and transaction-behavior features. Trade history exists but is too sparse in these two seasons to justify making trade-tendency modeling a V1 priority.

## FAAB environment

Raw waiver-bid medians are misleading because completed $0 waivers are common. For FAAB intelligence, separate $0 claims from positive winning bids.

### Positive completed waiver bids

| League | Season | Budget | Positive bids | Median positive bid | Median % budget | Mean positive bid | 75th percentile | Maximum |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FFL | 2024 | $100 | 73 | $5 | 5% | $9.56 | $11 | $71 |
| FFL | 2025 | $100 | 80 | $7 | 7% | $10.10 | $12.25 | $50 |
| Papa Johns | 2024 | $150 | 55 | $15 | 10% | $19.76 | $25.50 | $134 |
| Papa Johns | 2025 | $150 | 54 | $15 | 10% | $20.11 | $25 | $100 |

The leagues have meaningfully different historical clearing environments even after normalizing for FAAB budget. A generic cross-league raw-dollar bid recommendation would therefore be wrong.

### Recommendation design implication

Future FAAB evidence should begin with:

1. league-specific positive winning-bid distribution;
2. normalized percentage of initial/current FAAB budget;
3. player/position/role-shock class when enough samples exist;
4. manager-specific history with recency and uncertainty;
5. current roster need / competing-manager need;
6. current remaining budgets.

Do not use historical manager behavior as a deterministic label. Individual spending can change sharply from one season to another.

## Owner continuity / identity result

The same stable Sleeper user identity resolves the owner in both current leagues, while roster/team IDs remain league-season facts. The current pre-draft instances already resolve the correct owner roster even though player lists are empty.

Implementation rule remains:

- stable provider `user_id` identifies the manager;
- provider roster/team ID identifies that manager's team for a specific league season;
- display/team names are presentation metadata, never identity authority.

The fact that a roster number may happen to repeat across seasons does not make it a stable identity key.

## Provider inconsistency discovered: `total_moves`

Historical roster settings report `total_moves = 0` for the owner in seasons where the transaction endpoint proves dozens of completed owner-involved transactions.

Therefore:

- do not use roster `settings.total_moves` as authoritative historical activity;
- derive add/drop/waiver/trade activity from completed transaction records;
- retain the raw provider field for auditability only.

By contrast, historical `waiver_budget_used` matched the sum of positive completed winning waiver bids in the audited owner seasons and may be used as a cross-check, but transaction records remain the detailed authority.

## Draft history availability

Complete owner draft pick histories were returned:

- FFL 2024: 16 picks; draft slot 9.
- FFL 2025: 16 picks; draft slot 2.
- Papa Johns 2024: 15 picks; draft slot 12.
- Papa Johns 2025: 15 picks; draft slot 7.

The historical draft pool is sufficient to support future features such as league-specific ADP/reach/value review and manager drafting tendencies, provided those features are validated and do not overfit two seasons.

## What this validates for Fantasy HQ

The real backend can safely plan for historical backfill of:

- season-specific league rules;
- manager continuity;
- draft picks;
- weekly matchup history;
- completed waiver/free-agent/trade history;
- positive and $0 FAAB behavior;
- owner/team histories.

The following should **not** be assumed yet:

- historical manager tendencies are predictive enough for production bid recommendations;
- two seasons are enough for precise player-class FAAB models;
- sparse trade history justifies a trade-behavior engine;
- `total_moves` is a trustworthy provider aggregate.

## Next validation gate

Use the real historical/current Sleeper player IDs found in these leagues and drafts to test cross-provider player identity coverage against PropWar's canonical NFL identity authority. The identity gate should report direct-ID, bridged-ID, fallback, ambiguous, and unresolved rates before Fantasy HQ joins league ownership to PropWar role/market evidence.
