# DUSK Security Operations Console

Read-only React client for the authenticated control-plane read APIs. The UI never supplies a tenant identifier and never recalculates risk, aggregates, or dependency health. Access tokens use an in-memory `oidc-client-ts` store; only transient PKCE state uses session storage.

## Local development

```bash
cd apps/console
npm ci --ignore-scripts
npm run generate:api
npm run dev
```

Runtime configuration is read from `/config.json` with `Cache-Control: no-store`. Production deployments must replace that file with environment-specific public values. It must never contain secrets.

## Company sandbox and production configuration

Generate the public configuration and its matching Nginx CSP together. Use a deployment input file with these five public fields, replacing the example domains with actual endpoints:

```json
{
  "consoleUrl": "https://console.example.com",
  "apiBaseUrl": "https://api.example.com",
  "oidcAuthority": "https://identity.example.com/realms/company",
  "oidcClientId": "dusk-console",
  "environmentLabel": "Company sandbox"
}
```

```bash
npm run configure -- deployment.json /tmp/dusk-company-config
```

The output directory must not already contain either output file. Mount the generated `config.json` read-only at `/usr/share/nginx/html/config.json` and `nginx.conf` read-only at `/etc/nginx/conf.d/default.conf`. Both files are required. Terminate TLS at the deployment ingress and serve the console at the origin root. Keep the container read-only, non-root, and without capabilities, as in the local Compose service.

The generator limits CSP connections to the API and identity origins and rejects insecure remote endpoints, embedded credentials, and unknown configuration keys. The browser also rejects localhost endpoints on a remote console. Localhost HTTP is permitted only for local development. Do not deploy the local Compose realm, scenario loader, health monitor, sample credentials, or database to a company environment.

Release images are published as `ghcr.io/shieldtech-ltd/dusk-console` by immutable digest. The release workflow produces build provenance and an SPDX SBOM and signs the digest with keyless Cosign. Production admission policy should verify those attestations before allowing the image to run. Mirror the verified digest into the company's private registry for disconnected or restricted sandboxes.

Register an OIDC public client with Authorization Code and PKCE, exact redirect URI `https://console.example.com/auth/callback`, post-logout URI `https://console.example.com/login`, and the console origin as its allowed web origin. The provider must expose discovery and browser token endpoints on the configured identity origin. Configure the control plane's allowed CORS origin and OIDC issuer/audience for that deployment, with validated `dusk_roles` and `dusk_tenant_id` claims. API authorization remains enforced by the backend. No tenant or secret is supplied through this public configuration.

Verify sign-in, sign-out, tenant isolation, role restrictions, API requests, CSP headers, and actual data freshness in each target environment before release. Local test success does not establish that a remote identity provider or ingress is configured correctly.

For the real PostgreSQL, Keycloak, FastAPI, and production-image stack, run `./scripts/console-local.sh up` from the repository root. See `docs/security-console-local-acceptance.md` for temporary accounts and the acceptance checklist.

## Verification

```bash
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
npm run check:api
npm audit --audit-level=moderate
npm run test:e2e
```

The generated `src/api/schema.d.ts` is checked in. `check:api` fails when it differs from `services/control-plane/contracts/openapi.json`.
