# Fantasy HQ Cloudflare deployment runbook

Status: deployment-readiness contract only. Following this runbook creates remote Cloudflare resources; repository CI does not.

## Fixed v1 invariants

- Worker: `propwar-fantasy-hq`
- Worker entrypoint: `workers/fantasy-hq/index.mjs`
- Public origin: Cloudflare `workers.dev` for the first controlled deployment; no custom route is required in v1
- D1 binding: `FANTASY_DB`
- D1 database name: `propwar-fantasy-hq`
- D1 migrations: repository `migrations/` directory
- Required Worker secret: `FANTASY_PERSISTENCE_TOKEN`
- The secret value must never be committed, placed in Wrangler `vars`, written into the generated config, or pasted into documentation
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

## 4. Configure the Worker secret

Generate a high-entropy token outside the repository/password history and store it in the password manager used for this project. Then set it directly in Cloudflare:

```powershell
npx wrangler secret put FANTASY_PERSISTENCE_TOKEN --config workers/fantasy-hq/wrangler.generated.jsonc
```

Wrangler should prompt for the value. Do not pass the token on the command line, commit it, or save it to `.env` unless doing an intentionally local-only test in an ignored file.

## 5. Apply the D1 migration before serving writes

List first, then apply only the tracked migration set to the named remote database:

```powershell
npx wrangler d1 migrations list propwar-fantasy-hq --remote --config workers/fantasy-hq/wrangler.generated.jsonc
npx wrangler d1 migrations apply propwar-fantasy-hq --remote --config workers/fantasy-hq/wrangler.generated.jsonc
```

Re-run `migrations list` and confirm there are no unapplied migrations. Do not execute ad-hoc schema SQL against production when a tracked migration can represent the change.

## 6. Build-only preflight

```powershell
npx wrangler deploy --dry-run --config workers/fantasy-hq/wrangler.generated.jsonc
```

A dry run must succeed before a remote deployment is attempted.

## 7. Deploy the Worker

```powershell
npx wrangler deploy --config workers/fantasy-hq/wrangler.generated.jsonc
```

Record the exact deployed URL and deployment/version identifier. Do not add a custom domain until the workers.dev deployment has passed the smoke tests below.

## 8. Smoke test without writing fantasy data

1. `GET /health` must return HTTP 200, `ok=true`, `status="ok"`, and protocol version 1.
2. A POST to `/v1/fantasy/persistence` with no bearer token must return HTTP 401.
3. A POST with an incorrect bearer token must return HTTP 401.
4. Logs must not expose bearer tokens, command bodies, SQL parameters, or league/player payloads.

Do not perform an authenticated write merely to prove connectivity. The first authenticated write should be the intentional registration of a verified real league season after the Python runtime is wired to the endpoint.

## 9. Python/runtime wiring is a separate gate

The deployed Worker URL becomes `FANTASY_PERSISTENCE_URL`; the same secret value becomes `FANTASY_PERSISTENCE_TOKEN` for the trusted Python runtime. Those values must live in runtime secret storage, not GitHub source. The Python client performs a public health check and strict response validation before any higher-level sync workflow is enabled.

## Rollback / stop conditions

Stop instead of deploying if any of these occur:

- D1 name/UUID does not match the generated config
- migration list is unexpected
- required Worker secret is missing
- Wrangler dry-run fails
- `/health` protocol version differs from Python
- unauthenticated persistence POST is accepted
- logs contain secret or request-body material

A code rollback does not reverse a D1 migration. Database migrations therefore remain explicit, versioned, and separately audited.

## Source references verified 2026-08-26

- Cloudflare Wrangler configuration: https://developers.cloudflare.com/workers/wrangler/configuration/
- Cloudflare D1 migrations: https://developers.cloudflare.com/d1/reference/migrations/
- Cloudflare D1 Wrangler commands: https://developers.cloudflare.com/d1/wrangler-commands/
- Cloudflare Workers secrets: https://developers.cloudflare.com/workers/configuration/secrets/
