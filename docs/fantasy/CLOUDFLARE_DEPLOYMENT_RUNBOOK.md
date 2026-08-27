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

A code rollback does not reverse a D1 migration. Database migrations therefore remain explicit, versioned, and separately audited.

## Source references verified 2026-08-26

- Cloudflare Wrangler configuration: https://developers.cloudflare.com/workers/wrangler/configuration/
- Cloudflare D1 migrations: https://developers.cloudflare.com/d1/reference/migrations/
- Cloudflare D1 Wrangler commands: https://developers.cloudflare.com/d1/wrangler-commands/
- Cloudflare Workers secrets: https://developers.cloudflare.com/workers/configuration/secrets/
- Cloudflare Cron Triggers: https://developers.cloudflare.com/workers/configuration/cron-triggers/
- Cloudflare scheduled handler: https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/
- Cloudflare D1 prepared statements: https://developers.cloudflare.com/d1/worker-api/prepared-statements/
