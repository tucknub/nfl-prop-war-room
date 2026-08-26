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

However, the current receptions feature build uses research-era fixed current weights (25% / 50% / 70%) and a fallback prior driven largely by positional median. That is not sufficient as a personalized 2026 fantasy prior. Fantasy HQ should validate a player/team-specific offseason prior and its decay through historical point-in-time replay rather than simply copying these weights.

The route-participation proxy is explicitly marked `ROUTE_PROXY_UNVALIDATED`; it must not be presented as true route participation.

## Existing negative evidence we should respect

Historical signal auditing already shows that not every available signal deserves weight.

Strong / useful historical families include, depending on market family:

- projection score
- usage foundation
- recent form
- opponent fit (particularly rushing / receiving)

Historically weak or noisy families include:

- game script in the older signal formulation
- the old role-availability placeholder
- several volatility / quality components as direct production predictors

Fantasy HQ should test end-action utility rather than inherit every old score or weight.

## Weekly discovery design to reuse

The Weekly Role Report already solved a problem Fantasy HQ will face: dozens of technical matches are too noisy for a default screen.

Existing design principles worth retaining:

- One player appears once in the default report.
- Deterministic category priority.
- Section caps.
- Small default total (roughly 10–12 situations in historical replay).
- Full technical evidence remains available beneath the default presentation.
- No weighted opaque score is required to order the default cards.

Fantasy HQ `Today` should use the same philosophy: `Needs Action` → `Monitor` → `No Action / FYI`, with strong de-duplication.

## Current 2026 handoff

Current role status is intentionally `PRESEASON` until the first completely validated regular-season week is available.

Fantasy HQ should therefore distinguish:

1. **Offseason / preseason prior** — 2025 role history + 2026 roster/depth/injury/market evidence that is actually sourced.
2. **Early current season** — blend the prior with validated 2026 observations.
3. **Established season** — current-season role becomes dominant as evidence matures.
4. **Disrupted state** — injury, trade, QB/coaching or depth-chart change can invalidate the normal baseline.

Exact blending/decay weights must be historically replayed and validated; do not hard-code assumptions merely for convenience.

## New shared component required: canonical external-provider identity

This is the clearest missing shared infrastructure.

Current NFL role data has real NFL IDs; current Deep Prop market rows generally normalize player labels textually for cross-book comparison. Fantasy platforms introduce Sleeper and Yahoo identifiers.

Extend the existing identity authority so one canonical PropWar player can map to:

- GSIS / current PropWar player ID
- PFR ID
- Sleeper player ID
- Yahoo player key
- Sportradar / FantasyData IDs when available
- sportsbook/provider player identifiers or reviewed aliases

Duplicate-name and unresolved-team cases must fail closed. Do not use name-only matching when an identity is ambiguous.

## New shared component required: Player Evidence contract

Fantasy HQ, Role Shock, and Deep Prop should all consume the same evidence object rather than joining raw files independently.

Recommended domains:

### Identity
- canonical player ID
- provider IDs
- current NFL team
- position

### Historical role
- prior baseline
- recent baseline
- role family
- persistence / reversion history where valid

### Current role
- all-game and normal-game share
- raw player opportunities
- team denominator
- snap share when authoritative
- situational context when authoritative

### Change
- role delta
- persistence classification where available
- partial-game flags
- data quality / identity status

### Current context
- roster / depth-chart role where sourced
- injury / availability where sourced
- teammate availability where sourced
- opponent

### Market
- relevant current prop lines
- price/line movement where available
- source/book
- market timestamp / freshness

### Quality
- source timestamps
- stale/missing evidence
- unresolved mappings
- publication version

## Fantasy league state: new, platform-derived layer

Sleeper/Yahoo should own league facts, not NFL truth.

Normalize each league into a common model including:

- platform and platform league/team IDs
- scoring settings
- roster positions / starter slots
- bench / IR
- waiver / FAAB settings
- managers and all rosters
- current starters
- matchups / standings
- transactions / adds / drops / bids where available
- sync timestamp / source health

Do not create one universal fantasy player rank. Player action must be evaluated inside the active league rules, user roster, free-agent pool, opponent context, and current NFL evidence.

## Storage boundaries

### Keep in existing Python/data pipeline
- Raw / large NFL historical datasets.
- Historical player-week features.
- Role history and validation artifacts.
- Model/backtest outputs.
- Raw/derived football research artifacts.

### Candidate for Cloudflare D1
- Normalized fantasy leagues/settings.
- Current fantasy rosters/starters/matchups/standings.
- Fantasy transactions and change events.
- League snapshots / sync runs.
- External provider identity extensions (or a synchronized compact mirror of canonical identity).
- Recommendation history and outcomes.
- Encrypted rotating Yahoo OAuth refresh-token material.

### Keep in `propwar-private-state`
- Manually confirmed Margin state.
- Manually confirmed Knockout state.

## DepthSnap / Next.js decision

PR #9 / branch `propwar-nextjs-public-v1` is a valuable asset, especially its typed data contracts, registry/cache, identity types, evidence bundle concepts, deterministic exporter, and release QA.

It is not production-equivalent today. It diverged from the current production branch after its July branch point; current production later added Owner auth, Margin, Knockout, Glitch Radar, Deep Prop, and related tests/infrastructure.

Therefore:

- Do not merge PR #9 wholesale.
- Do not throw it away.
- Treat it as a validated design/contract/front-end source.
- Port or rebase only after the current backend/data contracts are settled.
- Keep Streamlit for the first Fantasy HQ owner surface unless a currentized Next.js migration clearly buys enough UX value to justify the work.

## Fantasy HQ V1 after reuse audit

V1 should focus on decisions rather than administration:

1. Three normalized league profiles from platform APIs.
2. Current rosters, starters, ownership, matchup state.
3. `Today / What Changed?` across all leagues.
4. Cross-league Role Alerts.
5. Personalized Waiver Radar.
6. Drop candidates.
7. Start/Sit Decision Board.
8. Cross-league player ownership / exposure.
9. Bye-week / roster bottleneck detection.
10. Recommendation/evidence history.

Explicitly excluded from V1:

- dues/payment tracking
- generic fantasy news feed
- opaque universal fantasy score
- new full proprietary fantasy projection system before validation
- automatic waiver/lineup writes
- duplicating existing PropWar NFL role or market engines

## Validation requirement: historical fantasy decision replay

Before strong automated recommendation claims, construct point-in-time replay tests.

At each historical decision point, permit only data known before that timestamp/week. Compare, where evidence permits:

- projection-only baseline
- projection + role
- projection + role + market
- projection + role + market + context

Evaluate end-action usefulness (waiver/start-sit outcome), not merely whether an intermediate model fits historical production.

Preserve 2026 prospective recommendations with:

- generated-at timestamp
- source timestamps
- player/league state version
- evidence fields used
- recommendation / reason codes
- model/rules version

Never rewrite prior recommendations after outcomes are known.

## Implementation prerequisite checklist

Before new Fantasy HQ application code:

- [ ] Approve this reuse boundary.
- [ ] Define canonical external-provider ID extension.
- [ ] Define Player Evidence schema/contract.
- [ ] Define normalized fantasy league schema.
- [ ] Define D1 storage/event schema.
- [ ] Verify the two Sleeper leagues against the normalized schema.
- [ ] Define Yahoo OAuth/read-only connection contract.
- [ ] Define point-in-time Fantasy HQ validation protocol.

Only then should implementation begin.
