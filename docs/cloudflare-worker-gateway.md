# DUSK Cloudflare Worker gateway

## Purpose

The `dusk` Cloudflare Worker is a fail-closed request boundary for DUSK action evaluation. It accepts only authenticated JSON `POST` requests to `/v1/actions/evaluate`, then forwards validated bytes through `DuskRuntimeDO` to the Python policy Container.

The Worker does not evaluate DUSK policy, issue permits, or execute tools. The Python DUSK service remains the enforcement authority and the only component that can authorize a consequential action.

## Local verification

```powershell
npm ci
npm run test:worker
npm run typecheck:worker
npm run deploy:worker:dry-run
```

The dry run verifies that Wrangler can package the Worker. It does not deploy it or prove Container startup, bindings, or downstream enforcement.

## Configure secrets for the reviewed environment

Use a principal that is authorized only for this Worker. Do not put the secret values in `wrangler.jsonc`, `.dev.vars`, source control, CI logs, or terminal recordings.

```powershell
npx wrangler secret put DUSK_GATEWAY_TOKEN
npx wrangler secret put DUSK_SIGNING_KEY
npx wrangler deploy
```

Confirm the account, Worker, resource inventory, and reviewed candidate before running these remote commands. `DUSK_ORIGIN` is no longer used. `DUSK_GATEWAY_TOKEN` must be a newly generated high-entropy bearer secret. `DUSK_SIGNING_KEY` must be a separate base64-encoded 32-byte raw Ed25519 private key. The Durable Object passes only the signing key to the Container at startup with outbound Internet disabled. Missing signing-key configuration fails closed as `503 runtime_unavailable`; there is no ephemeral production fallback. See Cloudflare's [Container secrets documentation](https://developers.cloudflare.com/containers/examples/env-vars-and-secrets/).

The startup code does not change the environment of an already running Container. After rotating the signing key, stop existing runtime Container instances through the approved deployment procedure and verify that a fresh instance uses the new key before resuming traffic. Removing the Worker signing secret blocks new evaluations even if a Container remains running.

## Request contract

```powershell
curl.exe -X POST "https://dusk.<your-subdomain>.workers.dev/v1/actions/evaluate" `
  -H "Authorization: Bearer <client-gateway-token>" `
  -H "Content-Type: application/json" `
  --data '{"action_type":"route_change","target":"sandbox"}'
```

The Worker permits only a JSON object up to 65,536 bytes. It returns a generated `X-DUSK-Request-ID` response header. Keep that identifier with DUSK audit records when investigating a decision.

## Evidence boundary

Local tests and a successful packaging dry run verify Worker behavior in an isolated runtime. Live validation must also prove Container startup using the configured signing key, Replay Guard persistence, redacted R2 receipts, Analytics events, and the exact active source and image digest. This evaluation endpoint does not execute tools or establish tenant identity from the shared bearer token. Scoped execution, fake downstream containment proof, and reviewed live evidence remain tracked in #271, #272, #284, and #285 before production promotion.
