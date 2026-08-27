# Fantasy HQ Cloudflare deployment runbook

Status: shadow-deployment contract. Following the remote steps creates Cloudflare resources; repository CI does not. The tracked Wrangler config keeps automatic Cron Triggers explicitly disabled.

## Fixed v1 invariants

- Worker: `propwar-fantasy-hq`
- Worker entrypoint: `workers/fantasy-hq/index.mjs`
- Public origin: Cloudflare `workers.dev` for the first controlled deployment; no custom route is required in v1
- D1 binding: `FANTASY_DB`
- D1 database name: `propwar-fantasy-hq`
- D1 migrations: repository `migrations/` directory
- Required Worker secret: `FANTASY_PERSISTENCE_TOKEN`
- Non-secret schedule mode: `FANTASY_SCHEDULE_MODE=SHADOW`
- Automatic Cron Triggers: explicitly disabled with `crons=[]`
- The Worker exports a Cloudflare `scheduled()` handler, but in this slice it performs only a fixed read-only D1 schema probe and structured readiness log
- The shadow scheduled handler never calls D1 `batch()`, never writes a sync run/snapshot/event, and never invokes the Python #76 scheduled-sync contract
- The secret value must never be committed, placed in Wrangler `vars`, written into the generated config, pasted into documentation, or placed on a shell command line
- The real D1 UUID is resource identity, not a secret, but the generated config is ignored so provisioning remains an explicit operator step

## Manual GitHub shadow deployment gate

The repository also contains `.github/workflows/fantasy-hq-shadow-deploy.yml` for the first remote deployment. It is **manual only**: the workflow has `workflow_dispatch` and no push, pull-request, schedule, or Cron trigger.

Repository or environment secrets required by that workflow:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `FANTASY_PERSISTENCE_TOKEN`

The Cloudflare token must be scoped narrowly enough to perform the intended D1 operations and Worker deployment and to read Worker Cron schedules. The workflow never writes these values into source or artifacts.

To authorize a run, the operator must enter the exact confirmation:

`DEPLOY_FANTASY_HQ_SHADOW`

The optional `database_id` input pins the run to a known D1 UUID. If supplied and that UUID is missing or belongs to another database name, the workflow stops. It will never create a replacement for an explicitly requested UUID.

`create_database_if_missing` defaults to **false**. Only a manually dispatched run that explicitly sets it to true may create `propwar-fantasy-hq`, and only when there is no exact-name database already present.

Before deployment, the workflow requires the migrated D1 target to contain the complete tracked Fantasy HQ schema and **zero** existing rows in the persistence tables used by the first canary. It then:

1. renders the validated SHADOW Wrangler config;
2. lists/applies/lists only tracked remote D1 migrations;
3. performs a read-only schema/data probe;
4. runs a Wrangler dry-run;
5. deploys the Worker with the persistence secret from an ephemeral runner-temp file;
6. parses structured Wrangler deployment output and requires the expected `workers.dev` origin;
7. calls the Cloudflare Cron schedules API and requires zero schedules;
8. verifies public health and both unauthorized persistence boundaries;
9. runs the authenticated #78 read-only runtime handshake;
10. uploads only a sanitized deployment-evidence JSON artifact.

A successful shadow-deployment workflow still reports `real_fantasy_write_performed=false`. It does **not** invoke #80's single-league canary, enable recurring scheduling, or authorize multi-league persistence. The first real league write remains a separate deliberate action after reviewing the shadow evidence.

The workflow pins Wrangler `4.126.0` for reproducible first-deployment behavior. Upgrade that pin only in a reviewed change after checking current Cloudflare documentation and rerunning repository tests.

The local Wrangler procedure below remains the operator fallback when GitHub-hosted deployment credentials are intentionally not used.

### Two-pass one-league canary workflow

After this change is merged, the first real Fantasy HQ write uses the separate manual workflow:

`.github/workflows/fantasy-hq-single-league-canary.yml`

The repository is public. **Never place a real Sleeper league ID, Sleeper user ID, league display name, or internal league identity into workflow-dispatch inputs, logs, summaries, or public artifacts.** Stable real-league configuration lives only in GitHub Actions secrets:

- `FANTASY_CANARY_LEAGUE_SEASON_ID`
- `FANTASY_CANARY_PLATFORM_LEAGUE_ID`
- `FANTASY_CANARY_SEASON`
- `FANTASY_CANARY_LEAGUE_FAMILY_ID`
- `FANTASY_CANARY_FAMILY_DISPLAY_NAME`
- `FANTASY_CANARY_SEASON_DISPLAY_NAME`
- `FANTASY_CANARY_REGISTRATION_CREATED_AT_MS`
- `FANTASY_CANARY_CURRENT_USER_ID`

The canary workflow also requires the existing deployment secrets:

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `FANTASY_PERSISTENCE_TOKEN`

The only operator inputs are the mode, successful shadow workflow run ID, explicit canary timestamp, and—during execution—the reviewed deterministic sync-run ID plus the exact write confirmation.

The workflow is intentionally **two-pass**.

**Pass 1 — PREVIEW_ONLY**

1. Run **Fantasy HQ Shadow Deploy** from the current `streamlit-cloud-deploy` commit and require it to finish successfully.
2. Copy that successful shadow workflow run ID.
3. Run **Fantasy HQ Single-League Canary** with mode `PREVIEW_ONLY`, the shadow run ID, and an explicit `canary_at_ms`.
4. The workflow downloads the exact immutable shadow evidence artifact using `actions:read`.
5. It requires the artifact's source run ID and source commit SHA to match the requested shadow run and the current canary workflow commit.
6. It re-verifies remote D1 is still pristine, remote Cron Triggers are still empty, and the authenticated runtime handshake is still READY/read-only.
7. It validates the private league configuration and builds the deterministic canary plan with no provider or persistence write.
8. Public preview evidence contains only the season, a one-way league-identity fingerprint, canary timestamp, batch ID, sync-run ID, and snapshot ID. It does not contain the real league/user identifiers.
9. No fantasy write occurs.

Review the preview's `sync_run_id` before moving on.

**Pass 2 — EXECUTE_ONE_WRITE**

Run the workflow again with:

- the **same** successful shadow run ID;
- the **same** `canary_at_ms`;
- mode `EXECUTE_ONE_WRITE`;
- `expected_sync_run_id` copied exactly from Pass 1;
- confirmation exactly `RUN_ONE_REAL_FANTASY_WRITE`.

Before the write, the workflow repeats the shadow evidence validation, D1 pristine-state probe, Cron check, runtime handshake, and deterministic preview. Execution is blocked unless the newly generated sync-run ID exactly matches the operator-reviewed value.

The write then invokes only `scripts/run_fantasy_hq_single_league_canary.py`, which performs the #80 one-league canary and immediate authenticated read-back verification. For the first pristine database, the result must be `ACCEPTED`; `NO_CHANGE` or an existing-final slot is not accepted as proof of a new real canary.

A successful public canary artifact contains only sanitized evidence: the one-way league identity fingerprint, season, logical canary timestamp, deterministic IDs, accepted snapshot ID, content fingerprint, read-back status, shadow run/version identity, zero-cron proof, and `recurring_schedule_enabled=false`.

If execution fails, the workflow uploads only the sanitized canary error JSON and fails the job. **Do not retry automatically.** If the failure indicates that a write may have committed, use authenticated recovery reads before doing anything else.

After a successful first canary, the D1 database is no longer pristine. This workflow's pre-write D1 guard will therefore block a second "first canary" run. Expansion beyond the first league must be a separate reviewed milestone.

Any repository change after the successful shadow deployment changes `GITHUB_SHA`; the canary workflow will reject an older shadow artifact. Re-run the shadow deployment from the new exact commit before attempting another preview.

## 1. Authenticate and record the tool version

Run Wrangler from a trusted local shell and record the exact version used in the deployment log.

```powershell
npx wrangler --version
npx wrangler whoami
```

Do not use a repository-stored Cloudflare API token for an interactive one-owner deployment. Prefer Wrangler's authenticated local profile/keychain flow.

## 2. Create the D1 database exactly once

```powershell
npx wrangler d1 create propwar-fantasy-hq
```

Do not use automatic/draft resource provisioning for this database. Copy the returned D1 UUID. If the database may already exist, stop and verify with `npx wrangler d1 list` instead of creating another one.

## 3. Render the deployable Wrangler config

```powershell
python scripts/render_fantasy_hq_wrangler.py --database-id <D1_UUID>
```

This creates the ignored file:

`workers/fantasy-hq/wrangler.generated.jsonc`

The renderer refuses invalid/nil UUIDs and validates every v1 binding invariant before writing the file. It does not read or write the persistence token.

Inspect the generated file. It should contain the D1 UUID but no secret value and no league/player data.

## 4. Apply the D1 migration before serving writes

List first, then apply only the tracked migration set to the named remote database:

```powershell
npx wrangler d1 migrations list propwar-fantasy-hq --remote --config workers/fantasy-hq/wrangler.generated.jsonc
npx wrangler d1 migrations apply propwar-fantasy-hq --remote --config workers/fantasy-hq/wrangler.generated.jsonc
npx wrangler d1 migrations list propwar-fantasy-hq --remote --config workers/fantasy-hq/wrangler.generated.jsonc
```

Confirm there are no unexpected or unapplied migrations. Do not execute ad-hoc schema SQL against production when a tracked migration can represent the change.

## 5. Build-only preflight

```powershell
npx wrangler deploy --dry-run --config workers/fantasy-hq/wrangler.generated.jsonc
```

A dry run must succeed before a remote deployment is attempted. This step does not authorize a remote deploy.

Confirm the rendered config still contains both of these exact shadow safeguards:

```json
"vars": {
  "FANTASY_SCHEDULE_MODE": "SHADOW"
},
"triggers": {
  "crons": []
}
```

An empty `crons` list is intentional. Do not replace it with a schedule during the first Worker/D1 shadow deployment.

The repository Worker tests exercise the `scheduled()` boundary directly. If a local Wrangler scheduled-event test is desired, use Wrangler's `--test-scheduled` mode only after applying the migration to the local D1 state. Current Wrangler exposes the local scheduled-handler test route at `/cdn-cgi/handler/scheduled`, with optional `cron` and `time` query parameters. Do not add a real remote Cron Trigger merely to test the handler.

## 6. Prepare the first-deploy secret outside the repository

Generate a high-entropy token outside Git history and store the durable copy in the password manager used for this project.

For the first deployment, create a temporary `.env`-format secrets file in the operating system's temporary directory, not inside the repository. Its only line is:

```text
FANTASY_PERSISTENCE_TOKEN=<value from password manager>
```

Do not type the token as part of a PowerShell command because shell history may retain it. Open the temporary file in a trusted editor, paste the value, save, and close the editor. Keep the path available as `<TEMP_SECRETS_FILE>` for the next command.

This temporary file is a bootstrap mechanism only. It is not a source-of-truth secret store.

## 7. Perform the intentional first deploy with the secret attached

```powershell
npx wrangler deploy --secrets-file <TEMP_SECRETS_FILE> --config workers/fantasy-hq/wrangler.generated.jsonc
```

Using `--secrets-file` uploads the required secret alongside the code in the same deliberate deployment instead of calling `wrangler secret put` first. Current Wrangler behavior for `secret put` creates and deploys a new Worker version immediately, so it is not used as a harmless pre-deploy configuration step.

After the deployment succeeds or fails, delete `<TEMP_SECRETS_FILE>` immediately. Do not move it into the repository, OneDrive, a synced folder, or an artifacts/log directory.

Record the exact deployed URL and deployment/version identifier. Do not add a custom domain until the workers.dev deployment has passed the smoke tests below.

## 8. Smoke test without writing fantasy data

1. `GET /health` must return HTTP 200, `ok=true`, `status="ok"`, and protocol version 1.
2. A POST to `/v1/fantasy/persistence` with no bearer token must return HTTP 401.
3. A POST with an incorrect bearer token must return HTTP 401.
4. Remote D1 migration listing must show the tracked migration applied.
5. The deployed Worker configuration must still show no Cron Triggers.
6. Logs must not expose bearer tokens, command bodies, SQL parameters, league/player payloads, or secret values.

Do not perform an authenticated write merely to prove connectivity. The first authenticated write should be the intentional registration of a verified real league season after the Python runtime is wired to the endpoint.

## 9. Scheduled shadow boundary

The Worker now exports `scheduled(controller, env)`, but automatic dispatch remains disabled by `crons=[]`.

When explicitly exercised in a controlled test, the handler:

1. requires `FANTASY_SCHEDULE_MODE=SHADOW`;
2. validates the scheduled timestamp and cron identity;
3. executes only the fixed read-only query `SELECT COUNT(*) AS row_count FROM fantasy_league_seasons`;
4. logs a compact readiness record with `write_enabled=false`;
5. does not read the persistence token;
6. does not call the Python scheduler or write fantasy state.

Activating a remote recurring Cron Trigger is a separate reviewed change. Do not add a cron expression to the deployment config as part of this shadow deployment.

## 10. Python/runtime deployment handshake

The deployed Worker URL becomes `FANTASY_PERSISTENCE_URL`; the same secret value becomes `FANTASY_PERSISTENCE_TOKEN` for the trusted Python runtime. Those values must live in runtime secret storage, not GitHub source, shell history, command arguments, or checked-in dotenv files.

After both values are present in the trusted runtime environment, run:

```powershell
python scripts/check_fantasy_hq_runtime_handshake.py
```

The command is deliberately read-only. It performs exactly this logical sequence:

1. public `GET /health` with no bearer token;
2. validates `ok=true`, `status="ok"`, and persistence protocol version 1;
3. authenticated `GET /v1/fantasy/read/sync-runs/propwar-runtime-handshake-v1-read-only-probe`;
4. validates the read response and requires that reserved probe ID to be absent;
5. returns a sanitized summary with `write_enabled=false`.

A successful result has this shape:

```json
{"authenticated_read_ready":true,"handshake_version":1,"health_ready":true,"probe_absent":true,"protocol_version":1,"ready":true,"write_enabled":false}
```

The command never calls the persistence POST endpoint and never creates a league, sync run, snapshot, event, or identity row. On failure it emits only `ready=false` plus the Python exception class; Worker messages, secrets, endpoint values, and D1 records are not printed.

The reserved probe sync-run ID is a deployment invariant. If it is ever present in D1, stop and investigate instead of deleting or reusing it merely to make the handshake pass.

**Production persistence gate:** do not enable an authenticated fantasy write path, scheduled Python runner, or recurring Cloudflare trigger unless this handshake returns `ready=true` in the same target environment that will perform the writes.

### Handshake-gated scheduled runtime

The library entrypoint `run_handshake_gated_scheduled_sleeper_sync(...)` is the only approved composition path for scheduled Sleeper persistence after the deployment handshake exists.

Its order is fixed:

1. validate and freeze the deterministic #76 scheduled plan before network I/O;
2. execute the #78 read-only Worker/D1 handshake;
3. require `ready=true`;
4. execute the frozen scheduled plan;
5. allow the existing multi-league and single-league persistence lifecycle to proceed.

If plan validation or the handshake fails, Sleeper must not be fetched and the persistence lifecycle must not begin. Tests enforce zero provider reads, zero registration/snapshot reads, and zero writes on those failure paths.

This entrypoint is a runtime library boundary only. It does **not** create a daemon, host a scheduler, configure a Cloudflare Cron Trigger, discover league configuration from secrets, or deploy anything remotely.

### First single-league persistence canary

The first intentional real write must use exactly one verified Sleeper league and the guarded operator command:

```powershell
python scripts/run_fantasy_hq_single_league_canary.py
```

The runtime environment must already contain the Worker settings from the handshake section plus all of these explicit canary values:

- `FANTASY_CANARY_CONFIRM=RUN_ONE_REAL_FANTASY_WRITE`
- `FANTASY_CANARY_LEAGUE_SEASON_ID`
- `FANTASY_CANARY_PLATFORM_LEAGUE_ID`
- `FANTASY_CANARY_SEASON`
- `FANTASY_CANARY_LEAGUE_FAMILY_ID`
- `FANTASY_CANARY_FAMILY_DISPLAY_NAME`
- `FANTASY_CANARY_SEASON_DISPLAY_NAME`
- `FANTASY_CANARY_REGISTRATION_CREATED_AT_MS`
- `FANTASY_CANARY_AT_MS`
- `FANTASY_CANARY_CURRENT_USER_ID`

`FANTASY_CANARY_AT_MS` is an explicit logical slot; the command never substitutes the current clock. Reusing a slot that is already final is rejected. A new trial requires a newly reviewed timestamp.

The canary execution order is:

1. validate all canary and persistence configuration before provider network I/O;
2. run the #78 read-only Worker/D1 handshake;
3. require READY;
4. fetch exactly one Sleeper league through the #79 gated runtime;
5. perform the existing registration/sync persistence lifecycle;
6. read back the exact sync-run ID and require `COMPLETED`;
7. read back the latest accepted snapshot;
8. strictly rehydrate the persisted normalized state;
9. require league identity, accepted snapshot ID, and content fingerprint to match the live provider run;
10. stop.

A successful command returns sanitized JSON with `ready=true`, `readback_verified=true`, the canary mode, batch/sync/snapshot IDs, and the verified content fingerprint.

**Do not automatically retry a failed canary.** If failure output contains `"write_may_have_committed":true`, the persistence operation may already be durable. Inspect the sync run and latest snapshot through authenticated recovery reads before choosing a fresh canary slot. A code rollback cannot undo an accepted D1 snapshot.

Do not enable a recurring scheduler or expand to additional leagues merely because the write returned HTTP success. The canary is successful only after the immediate read-back verification passes.

## 11. Later secret rotation

`wrangler secret put FANTASY_PERSISTENCE_TOKEN` is appropriate only when an immediate secret-version deployment is intended and understood. It must not be treated as a passive settings update. Coordinate the Worker secret and the trusted Python runtime secret so one side is not left using a stale token.

## Rollback / stop conditions

Stop instead of deploying if any of these occur:

- D1 name/UUID does not match the generated config
- migration list is unexpected
- Wrangler dry-run fails
- the first-deploy secret file is inside the repository or a synced folder
- `/health` protocol version differs from Python
- unauthenticated persistence POST is accepted
- logs contain secret or request-body material
- `FANTASY_SCHEDULE_MODE` is not exactly `SHADOW`
- the generated deployment config contains any Cron Trigger
- the scheduled shadow test performs any D1 write
- the runtime deployment handshake does not return `ready=true`
- the reserved runtime handshake probe sync-run ID exists
- the handshake command output contains an endpoint, token, Worker message, or D1 record
- the canary confirmation value is missing or differs from `RUN_ONE_REAL_FANTASY_WRITE`
- canary identity values do not exactly match the intended real Sleeper league
- the canary returns `write_may_have_committed=true` and recovery reads have not been inspected
- canary sync or snapshot read-back does not exactly match the accepted content fingerprint

A code rollback does not reverse a D1 migration. Database migrations therefore remain explicit, versioned, and separately audited.

## Source references verified 2026-08-26

- Cloudflare Wrangler configuration: https://developers.cloudflare.com/workers/wrangler/configuration/
- Cloudflare D1 migrations: https://developers.cloudflare.com/d1/reference/migrations/
- Cloudflare D1 Wrangler commands: https://developers.cloudflare.com/d1/wrangler-commands/
- Cloudflare Workers secrets: https://developers.cloudflare.com/workers/configuration/secrets/
- Cloudflare Cron Triggers: https://developers.cloudflare.com/workers/configuration/cron-triggers/
- Cloudflare scheduled handler: https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/
- Cloudflare D1 prepared statements: https://developers.cloudflare.com/d1/worker-api/prepared-statements/
