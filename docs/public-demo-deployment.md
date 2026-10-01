# DUSK public demo deployment

This deployment runs the console, control plane, PostgreSQL, Keycloak, and Traefik on one Oracle Cloud Infrastructure Ampere A1 virtual machine. It avoids application cold starts, but it does not provide a permanent availability guarantee. Oracle can reclaim an idle Always Free instance, A1 capacity can be unavailable, and every component still shares one failure domain.

The deployment is intentionally a public, synthetic, read-only showcase. It is not the customer deployment architecture and must never contain customer data, production credentials, or real enforcement integrations.

## Security boundary

- OCI permits inbound TCP 80 and 443 only. SSH is not exposed.
- GitHub Actions obtains an OIDC token, exchanges it for a short-lived OCI resource principal session token, and invokes OCI Run Command.
- The VM verifies each image's keyless Cosign signature before starting it.
- The API omits its evaluation endpoint, and Traefik also allows only GET and OPTIONS requests to the API host.
- PostgreSQL is attached only to an internal Docker network.
- The database reset command accepts only the fixed synthetic tenant, database, host, and public-demo mode.
- Runtime containers use read-only filesystems, dropped capabilities, bounded logs, health checks, and resource limits where their upstream image permits them.

## One-time OCI bootstrap

1. Create an OCI account and confirm Ampere A1 capacity in the intended availability domain.
2. Apply `deploy/public-demo/terraform` through an approved infrastructure workflow or from an administrator workstation. Keep Terraform state in an encrypted remote backend. The configuration creates the A1 VM, VCN, public subnet, internet gateway, 80/443 security rules, and enables Compute Instance Run Command.
3. Point the owned DNS records for `demo`, `api.demo`, and `auth.demo` at the Terraform `public_ip` output.
4. Create `/etc/dusk-demo/deployment.env` on the VM from `deployment.example.env`. Generate independent random values of at least 32 bytes for every password and signing key. Set mode `0600` and owner `root:root`.
5. Confirm cloud-init installed the pinned Docker Engine and checksum-verified Cosign package successfully.
6. Make the two GHCR packages publicly readable. Public images contain no secrets. If public packages are not acceptable, configure a read-only package token on the VM and accept the resulting long-lived secret.
7. Configure the GitHub environment `public-demo-production` with required reviewers. Every application deployment pauses for an environment approval after protected `main` passes CI. The approval is a deliberate production release gate, not an infrastructure-only control.

## Workload identity federation

In the OCI identity domain, create a confidential OAuth application without administrator roles for token exchange. Create an Identity Propagation Trust with:

- issuer `https://token.actions.githubusercontent.com`
- subject type `Resource`
- impersonating resource `githubactions`
- the token-exchange OAuth client ID in `oauthClients`
- exact claim validation for `job_workflow_ref` equal to `ShieldTech-Ltd/DUSK/.github/workflows/public-demo.yml@refs/heads/main`
- exact claim validation for the repository and branch claims available in the GitHub OIDC token

Grant the resulting resource principal only the OCI permission needed to create, inspect, and cancel Instance Agent commands for the one demo instance. Do not grant general compute administration.

Configure these GitHub environment values:

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `OCI_WIF_CLIENT_ID` | Token-exchange OAuth client ID |
| Secret | `OCI_WIF_CLIENT_SECRET` | Token-exchange OAuth client secret |
| Variable | `OCI_IDENTITY_DOMAIN_URL` | Identity domain HTTPS origin |
| Variable | `OCI_REGION` | OCI region identifier |
| Variable | `OCI_COMPARTMENT_ID` | Demo compartment OCID |
| Variable | `OCI_INSTANCE_ID` | Terraform instance OCID |

The OAuth client secret is a remaining bootstrap credential. It is not an OCI API key, but it is still long-lived and must be rotated. OCI currently requires one of its supported authentication methods for this exchange.

## Release and reset lifecycle

After a push to protected `main` passes the `CI` workflow, the `public-demo-production` environment requires a reviewer to approve the release job. Once approved, `public-demo.yml` builds multi-architecture images, publishes SBOM and provenance metadata, signs immutable digests, exchanges identity, and starts an OCI Run Command. The host deploys into the inactive blue or green slot, runs migrations, waits for container health, resets the synthetic corpus, switches the Traefik route, verifies all public endpoints, and then removes the previous slot. A failed public check restores the previous route.

The `dusk-demo-reset.timer` recreates the synthetic corpus nightly. The `dusk-demo-health.timer` checks the three public endpoints every five minutes. Connect OCI Monitoring notifications to systemd or external uptime alerts during bootstrap because the unit alone records failures but does not page anyone.

## Verification

Before the first public announcement:

1. Confirm HTTPS certificates and HSTS on all three hosts.
2. Sign in as `demo-viewer` and verify that real API data is displayed.
3. Confirm POST, PUT, PATCH, and DELETE requests to the API host are rejected by Traefik.
4. Run the nightly reset and confirm only the dedicated demo database changes.
5. Exercise a failed deployment and confirm the previous slot remains reachable.
6. Confirm OCI audit logs identify the federated workflow subject for every Run Command.
7. Reboot the VM and confirm Docker, timers, and the demo recover without manual intervention.

No free tier can honestly guarantee both zero cold starts and permanent public uptime. This design removes intentional application sleep while keeping that infrastructure limitation explicit.
