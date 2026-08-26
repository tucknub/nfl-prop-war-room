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

Only after this passes should the second Sleeper league be added, followed by Yahoo OAuth.
