# Control-plane deployment and promotion

The production control-plane is packaged as one immutable OCI image and deployed
through the Helm chart in `deploy/helm/dusk-control-plane`. The image is built
once. Development, staging, and production must promote the exact same digest;
an environment must never rebuild source code or deploy a mutable tag.

## Current delivery boundary

This issue supplies cloud-neutral build, packaging, admission, migration,
promotion, and rollback controls. Backend and frontend localhost validation is
completed before any live-provider qualification. AWS, Azure, and managed
Kubernetes accounts are deliberately deferred to the final qualification gate
tracked by #251; no cloud account or credential is required to build and test
this change locally.

## Local verification

Build and test the service without publishing an image:

```sh
docker build -f services/control-plane/Dockerfile -t dusk-control-plane:local .
docker compose -f services/control-plane/compose.yml --profile control-plane config
helm lint deploy/helm/dusk-control-plane
helm template dusk-control-plane deploy/helm/dusk-control-plane \
  -f deploy/environments/localhost.yaml
pytest -q services/control-plane/tests tests/ci/test_control_plane_deployment.py
```

The localhost overlay contains documentation-only network ranges and an
unpublishable zero digest. Those placeholders are intentional. The deployment
validator rejects them when `--production` is supplied.

## Image integrity

`.github/workflows/control-plane-image.yml` builds the image with locked,
hash-verified Python dependencies. Pull requests build without publishing.
Trusted `dev` and release-tag runs publish to GHCR by digest, attach BuildKit
SBOM and SLSA provenance attestations, and add a repository-bound keyless Cosign
signature. The workflow records the resulting immutable image reference as the
only valid promotion input.

Clusters require Kyverno 1.18 or newer and apply
`deploy/policies/control-plane-image-policy.yaml`. Admission fails closed unless
the DUSK repository workflow signed the exact digest and signed provenance is
available. Registry or transparency-log outages therefore stop new pods; they
do not affect already-running pods.

## Runtime prerequisites

Before a non-local deployment, provide:

- Kubernetes, Helm 3, an ingress controller, metrics API, and Kyverno;
- an external OIDC issuer and JWKS endpoint;
- managed PostgreSQL with TLS and a least-privileged application role;
- a secret-store CSI or External Secrets operator integration;
- exact ingress-controller, PostgreSQL, OIDC, telemetry, and broker egress
  destinations; and
- a TLS certificate secret managed outside Git.

Never place credentials, tokens, database URLs, signing keys, or certificates in
values files. The chart references an existing Secret or an ExternalSecret. A
secret rotation updates that external object; restart the Deployment only when
the backing integration cannot project updates into existing pods.

Validate the final values before deployment:

```sh
python scripts/validate_control_plane_deployment.py values production-values.yaml --production
```

The validator rejects placeholder identities, documentation-only networks,
disabled NetworkPolicy, missing TLS, and non-digest images.

## Migration, promotion, and rollback

Helm runs a bounded pre-install/pre-upgrade migration Job using the same image
digest as the application. The runner holds a PostgreSQL advisory lock, applies
only the additive Alembic chain, and enforces connection, lock, statement, Job,
and Helm timeouts. A concurrent migration fails safely instead of racing.

Promote in this order: development, staging, production. At every boundary,
verify the keyless signature, SBOM attestation, SLSA provenance, exact digest,
tests, security approval, and immutable evidence URI. Validate the collected
record with:

```sh
python scripts/validate_control_plane_deployment.py promotion promotion.json
```

The manual `promote-control-plane.yml` workflow runs only on a protected,
pre-authenticated `dusk-deployer` runner. Each protected environment supplies a
non-secret values-file path and namespace. The runner obtains short-lived
workload identity outside the repository; do not store a kubeconfig or cloud
access key in GitHub. Account-backed runners and environments are created only
at the deferred qualification stage.

Use `helm upgrade --install --atomic --wait` so routing changes only after probes
succeed. Roll back application routing and the Helm release to the previously
approved digest with `helm rollback`; do not reverse an already-committed schema
migration. Migrations remain backward compatible for at least the rollback
window. Record the old and new digest, Helm revision, audit-chain continuity,
operator, approval, timestamps, and probe results during every rollback drill.

Production promotion remains unavailable until localhost backend/frontend tests
and the deferred live qualification in #251 pass. No generated or simulated
production evidence satisfies that gate.
