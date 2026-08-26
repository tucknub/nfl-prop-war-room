# Fantasy League HQ — Platform Integration Plan

**Status:** Pre-implementation integration contract

## Goal

Connect two Sleeper leagues and one Yahoo league to a shared normalized league-state layer without allowing platform-specific response shapes to leak into Fantasy HQ recommendation logic.

## Adapter interface

Each platform adapter should implement the conceptual operations below:

```text
identify_current_user()
list_or_resolve_leagues(season)
fetch_league(league_id)
fetch_managers(league_id)
fetch_rosters(league_id)
fetch_matchups(league_id, week)
fetch_transactions(league_id, week_or_window)
fetch_players_if_needed()
normalize_to_fantasy_league_state()
health()
```

Not every provider needs the same HTTP calls; the normalized result is the contract.

## Sleeper adapter

### Authentication

None for the official read-only API.

Persist the stable Sleeper `user_id`; do not rely on username as a permanent key because usernames can change.

### Primary calls

Use official endpoints for:

- user identity
- user NFL leagues for the season
- specific league
- league users
- league rosters
- weekly matchups
- weekly transactions
- drafts/picks when needed
- current NFL state
- player map / filtered player map
- trending adds/drops when useful

### Player-map policy

Sleeper's full NFL player map is large and is documented as a call to use sparingly. Cache/persist it and refresh at most on a low-frequency schedule unless a targeted filtered request is sufficient.

Candidate external IDs present in Sleeper player records (when populated) should be used to bootstrap identity resolution before fuzzy matching.

### Transaction policy

Persist completed free-agent, waiver and trade transactions. Preserve provider transaction ID, status, adds, drops and FAAB bid/budget details when present.

These records can later support league-specific FAAB behavior analysis; they should not create a recommended bid model before sufficient history exists.

### Seasonal league-family history

Sleeper creates a new league ID when many recurring leagues renew for a new season. Treat those provider IDs as season instances inside one stable PropWar `league_family`.

Use the current league's `previous_league_id` to walk backward through available historical seasons when the owner has approved that logical league family.

For each historical season instance, persist separately:

- provider league ID;
- season;
- full provider settings/scoring/roster positions;
- manager/user identities;
- season roster/team IDs;
- drafts/picks;
- weekly matchup results;
- completed weekly transactions and FAAB movement;
- final standings/results when derivable authoritatively.

**Never inherit historical settings into the current season.** Historical rules are for replay/context only.

Stable platform user identity may be linked across season instances so long-term manager behavior can survive annual league-ID changes. Season-specific roster/team IDs must not be treated as stable manager IDs.

Potential later manager-history features include:

- FAAB aggressiveness and typical winning-bid ranges;
- positional waiver preferences;
- add/drop frequency;
- draft tendencies;
- trade activity;
- historical matchup/standings context.

These are evidence features, not reasons to assume a manager will repeat prior behavior with certainty.

### Historical backfill policy

Historical backfill is a separate job from live current-season sync.

Recommended flow:

1. Start from the approved current Sleeper league ID.
2. Fetch and accept the current league object.
3. Record its `previous_league_id`.
4. Walk backward one season at a time until null, an already-ingested provider ID, or the configured history cutoff.
5. For each completed historical season, fetch league/users/rosters/drafts and week-scoped matchup/transaction history.
6. Preserve each season's exact rules fingerprint.
7. Map stable manager identities across seasons.
8. Build derived manager/league history only after raw backfill passes completeness checks.

Historical backfill failures must not block current-season roster sync. They should mark historical intelligence incomplete.

For Franchise Football League, the currently known chain is:

- 2026: `1383849993151987712` (live rules verified on 2026-08-26 through temporary read-only source audit)
- 2025: `1242463021108838400`
- 2024: `1112703068749058048`

The temporary audit workflow/PR used to verify the public 2026 provider payload is evidence gathering only and should not become part of the production integration. The real adapter remains the intended implementation.

## Yahoo adapter

### Authentication

Yahoo private fantasy data requires OAuth.

Initial scope should be **read-only**.

Separate concepts:

- PropWar Owner authentication answers: who may access owner tools?
- Yahoo OAuth answers: has that owner authorized Yahoo fantasy access?

Do not merge these identities into one authentication mechanism.

### OAuth callback

Recommended backend routes:

- `/v1/auth/yahoo/start`
- `/v1/auth/yahoo/callback`
- `/v1/auth/yahoo/status`
- `/v1/auth/yahoo/disconnect`

OAuth state must be validated and short-lived. Client secret and token-encryption key belong in backend secrets, never GitHub or browser code.

Refresh-token material must be persisted in a writable secure form because OAuth token lifecycle may require refresh/rotation. A revoked/invalid connection transitions to `RECONNECT_REQUIRED`; the system does not silently continue with indefinitely stale Yahoo league state.

### Fantasy resources

Normalize Yahoo game/league/team/player resources into the same contract used by Sleeper, including league scoring and roster rules. Retain Yahoo resource keys exactly.

When a Sleeper player record includes a Yahoo identifier, treat it as candidate crosswalk evidence and validate it against Yahoo player/team context rather than using display names as the primary bridge.

## Sync policy

### Baseline schedule

Use scheduled backend synchronization rather than requiring an active Streamlit session.

Suggested adaptive cadence, subject to provider limits and actual use:

- offseason / quiet periods: low frequency
- waiver-processing windows: increased frequency
- Thursday through Sunday: regular refreshes
- manual `Refresh now` path for the owner when a current decision is needed

Do not exceed provider guidance simply because scheduled infrastructure makes polling easy.

### Sync sequence

For each league:

1. Fetch league/settings.
2. Fetch managers/teams.
3. Fetch rosters/starters.
4. Fetch relevant matchup state.
5. Fetch new/recent transactions.
6. Normalize deterministically.
7. Resolve external player IDs to canonical PropWar players.
8. Compute state fingerprint.
9. If unchanged: update sync health only.
10. If changed: update current state and emit deterministic change events.

## Failure policy

### Provider failure

Retain last successful state but mark it stale.

UI must display:

- failed provider
- last successful sync time
- whether ownership-sensitive recommendations are suppressed

### Partial roster/ownership response

Do not infer free-agent availability from incomplete ownership data.

Suppress or downgrade:

- waiver recommendations
- drop/replacement recommendations
- ownership-driven cross-league alerts

### Identity failure

Keep provider player row in league state with `UNRESOLVED` identity. Do not drop it.

Any recommendation that requires linking the player to NFL evidence is blocked until identity is resolved.

## API boundary for Streamlit / future frontend

Fantasy HQ should consume normalized backend responses rather than call Sleeper/Yahoo directly.

Initial conceptual endpoints:

- `GET /v1/fantasy/leagues`
- `GET /v1/fantasy/leagues/{id}`
- `GET /v1/fantasy/leagues/{id}/roster`
- `GET /v1/fantasy/leagues/{id}/matchup`
- `GET /v1/fantasy/leagues/{id}/transactions`
- `GET /v1/fantasy/changes`
- `GET /v1/fantasy/ownership/{propwar_player_id}`
- `GET /v1/fantasy/sync-status`
- `POST /v1/fantasy/leagues/{id}/refresh` (owner-authenticated)

Recommendation endpoints should be added only after the state/identity layer is validated.

## First proof milestone

Before building the full Fantasy HQ UI:

1. Resolve one real Sleeper league.
2. Normalize its scoring and roster settings.
3. Match the user's team through Sleeper user/roster ownership.
4. Reproduce every current roster and starter exactly.
5. Reproduce the current matchup exactly.
6. Import recent transactions exactly.
7. Resolve platform player IDs to PropWar IDs with an explicit match report.
8. Refresh again and prove unchanged state does not create duplicate events.
9. Change fixture/source state and prove the correct deterministic event is emitted.
10. Follow the league's `previous_league_id` one generation and prove historical settings are stored separately rather than inherited.
11. Prove stable manager identities link across seasons while season roster IDs remain separate.
12. Prove a `pre_draft` empty-roster league does not create false free-agent availability.
13. Prove draft-specific settings come from the provider draft resource rather than conflicting league convenience fields.

Only after this passes should the second Sleeper league be added, followed by Yahoo OAuth.
