# Fantasy League HQ — NFL Asset Reuse Audit

**Status:** Architecture / reuse audit only  
**Production behavior changed:** No  
**Purpose:** Define what Fantasy League HQ must reuse, adapt, extend, or avoid before implementation begins.

## Executive decision

Fantasy League HQ must not create a second football-intelligence stack.

The existing PropWar Python pipeline remains the authoritative NFL calculation and evidence layer. Sleeper and Yahoo provide league state (settings, rosters, ownership, matchups, transactions). A persistent platform layer may normalize and retain fantasy state, but fantasy actions must consume the existing PropWar player/role/market evidence wherever that evidence is already authoritative.

Recommended architecture:

1. **Python / PropWar** — sole NFL role, historical-feature, validation, and model authority.
2. **Cloudflare Worker + D1** — league integrations, Yahoo OAuth, scheduled fantasy syncs, normalized league state, change events, and recommendation history.
3. **Streamlit owner UI initially** — add Fantasy League HQ without rewriting current Owner tools.
4. **DepthSnap / Next.js branch** — preserve as a reusable future frontend/contract asset; do not merge wholesale because it has diverged from current production and predates the current Owner-tool stack.
5. **`propwar-private-state`** — keep for manually confirmed Margin/Knockout state; do not use it as a high-frequency fantasy synchronization database.

## Live FFL source-audit checkpoint

A temporary read-only GitHub Actions audit was used only to retrieve and validate the public Sleeper resources for the current 2026 Franchise Football League before the real adapter exists. The source audit succeeded and confirmed:

- 2026 league ID `1383849993151987712` is Franchise Football League;
- it links directly to the known 2025 FFL ID;
- 10 teams / 10 expected managers;
- Full PPR and 6-point passing TDs;
- 2026 starters are `QB, RB, RB, WR, WR, WR, TE, FLEX, DEF`;
- Superflex is absent;
- $100 waiver budget, one keeper maximum, six playoff teams, Week 12 trade deadline;
- league/draft are currently `pre_draft` and all current rosters are empty;
- the actual draft resource reports a 16-round snake draft and must be used instead of the conflicting `league.settings.draft_rounds = 3` convenience field.

The temporary workflow/PR is not part of the target production architecture. These findings are now acceptance fixtures for the real adapter.

## Reuse matrix

| Existing asset | Location | Coverage / grain | Current quality | Fantasy HQ use | Decision |
|---|---|---|---|---|---|
| Canonical role history | `outputs/role_research/`, `src/role_validation/` | 2018–2025; season × week × player × team × role family | Validated; canonical audit passes | Historical role priors, role-change replay, player evidence | **REUSE AS AUTHORITY** |
| Current role operations | `src/operations/current_role_pipeline.py` | Completed current-season regular-season weeks | Completion/identity/partial-game gates | Current NFL role truth | **REUSE AS AUTHORITY** |
| NFL source ingestion | `src/operations/nflverse_current.py` | PBP, weekly stats/rosters, schedules, snaps | Timestamped/cache-aware | Current NFL factual inputs | **REUSE** |
| Normal-game context | `src/role_validation/normal_game.py` + current-role pipeline | Play/context flags | Validated methodology | Avoid garbage-time/late-context fantasy overreaction | **REUSE** |
| Partial-game handling | `src/role_validation/partial_game.py` | Player-game participation context | Explicit confirmed/suspected policy | Suppress misleading role alerts | **REUSE** |
| Player identity crosswalk | `src/load/build_identity_crosswalk.py`, `outputs/identity/` | Existing NFL identities | Duplicate-name safeguards; team-qualified matching | Base authority for external ID expansion | **EXTEND** |
| Opportunity feature history | `src/features/player_opportunity_shares.py`, feature tables | Historical player-week | Shifted rolling features; early-season sample states | Early-season evidence and research | **ADAPT / VALIDATE** |
| Historical feature windows | `src/features/history_window.py` | Point-in-time target week | Explicit leakage checks | Fantasy historical replay | **REUSE** |
| Prop feature tables | `outputs/*_feature_table.csv` | Carries, rushing, receptions, receiving, passing families | Large historical feature warehouse | Candidate components; not fantasy projections by default | **REUSE SELECTIVELY** |
| Prop backtests/calibration | `src/backtest/`, `outputs/*backtest*` | Walk-forward historical | Week N uses data through N-1 | Reuse test patterns / candidate components | **REUSE METHODOLOGY** |
| Signal context | `SIGNAL_DATA_SOURCES.md`, signal-board outputs | Recent form, game environment, opponent fit | Leak-safe context, visible missingness | Candidate contextual evidence | **REUSE SELECTIVELY** |
| Historical signal audit | `outputs/signal_boards/` | Passing/receiving/rushing | Component usefulness already audited | Prioritize useful components; distrust noisy ones | **REUSE EVIDENCE** |
| Weekly Role Report | `outputs/weekly_role_report/` + associated code | Weekly discovery cards | Deterministic caps/dedup; historical replay | Model Fantasy HQ `Today` information density | **REUSE PRESENTATION LOGIC** |
| Live-intake gate contracts | `LIVE_DATA_INTAKE.md`, validators | Roster/role/injury/market contracts | Contracts exist; current gate rows remain NEEDS DATA | Schema/validation reference only | **REUSE CONTRACTS, NOT CURRENT DATA** |
| Deep Prop market feed | `dashboard/glitch_radar_props_feed.py` | Current sportsbook player props | Useful live rows; player matching is text-label based | Market confirmation after canonical join | **EXTEND IDENTITY** |
| Deep Prop stale/coverage logic | `dashboard/glitch_radar_stale.py` | Current cross-book comparisons | Good coverage/freshness safeguards | Evidence freshness / market confirmation | **REUSE** |
| Margin private state | `propwar-private-state/margin/` | Manual authoritative pool state | Purpose-built | None for normal fantasy sync | **KEEP SEPARATE** |
| Knockout private state | `propwar-private-state/knockout/` | Manual authoritative special fantasy state | Purpose-built | Can later consume shared NFL evidence only | **KEEP SEPARATE** |
| DepthSnap Next.js frontend | `propwar-nextjs-public-v1` / PR #9 | Public frontend/contracts from July 2026 | Release-hardened at branch point; now diverged | Future typed frontend and data-contract patterns | **PRESERVE / PORT SELECTIVELY** |
| Archived Propedge | `tucknub/Propedge` | MLB prototype | Unrelated modeling domain | Possible UI inspiration only | **DO NOT REUSE MODEL LOGIC** |

## Confirmed historical foundation

The role-research dataset currently validates:

- 57,928 canonical rows.
- Seasons 2018–2025.
- Zero duplicate canonical keys.
- Zero required missing cells.
- 100% canonical identity coverage.
- 2025 full regular season: 272 games, Weeks 1–18.
- Richer situational/event outputs available for 2023–2025.

The canonical role grain is already compatible with a shared player-evidence layer:

`season × week × player_id × team × role_family`

Primary validated role families are:

- RB carry share.
- RB opportunity share.
- WR target share.
- TE target share.

Fantasy HQ must consume these definitions instead of implementing fantasy-specific duplicates.

## Existing early-season logic: reuse the concept, not blindly the current weights

`player_opportunity_shares.py` already assigns sample states conceptually equivalent to early-season evidence eras:

- `PRIOR_HEAVY`
- `CURRENT_BLEND`
- `CURRENT_STRONG`

Rolling features are shifted before use. This is valuable.

Do **not** assume the current early-season weights or fallbacks are production-ready fantasy priors. Existing research code should be replayed and validated before promotion.