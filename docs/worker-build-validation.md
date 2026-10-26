# Worker build validation

The Cloudflare `dusk` build was failing after its Worker tests and typecheck:
`wrangler deploy --dry-run` tried to build the configured Container, but that
build host could not launch Docker. This is a validation failure, not evidence
that a deployment succeeded.

## Required GitHub check

The main CI workflow now runs `worker-packaging` on an Ubuntu runner with Docker:

```sh
docker info
npm run test:worker
npm run typecheck:worker
npm audit --audit-level=moderate
npm run deploy:worker:dry-run
```

The `security-gate` job requires this job. Container packaging failures cannot
be ignored or replaced by the bundle-only check. This job uses no deployment
secrets and does not publish the image or Worker.

## Cloudflare Workers Builds command

The existing validation-only command on the Dockerless build host is:

```sh
npm run test:worker && npm run typecheck:worker && npx wrangler deploy --dry-run --containers-rollout=none
```

`--dry-run` keeps this check local. `--containers-rollout=none` allows this host
to validate the Worker bundle without attempting an unavailable local Docker
build. Full Worker/Container packaging remains mandatory in GitHub Actions.
The production branch command remains unchanged. Only the non-production
Version command uses this bundle validation path.
Use this only for the existing dry-run validation command, not as a production
Container deployment command.

Real deployment, bindings, runtime behavior, provider certification, review and
release approval remain separate requirements. Neither dry-run proves those.

References: [Cloudflare deploy guidance](https://developers.cloudflare.com/containers/guides/deploy/),
[rollout modes](https://developers.cloudflare.com/containers/configuration/rollouts/).
