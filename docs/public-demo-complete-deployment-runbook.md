# DUSK public demo complete deployment runbook

This runbook covers the one-time cloud bootstrap, the settings that must be entered manually, the repository automation, and the remaining engineering needed to make the DUSK public demo suitable for prospective customers.

The intended topology is:

```text
Visitor
  |
  v
Cloudflare DNS, proxy, TLS, WAF, and rate limiting
  |
  v
OCI Ampere A1 VM
  |
  +-- Traefik
  +-- DUSK Console
  +-- DUSK Control Plane
  +-- Keycloak
  +-- PostgreSQL
```

Cloudflare does not create the VM in this design. Terraform creates the VM and its network in Oracle Cloud Infrastructure (OCI). Cloudflare protects and routes the public web traffic to the OCI public IP.

## Current readiness and launch blocker

The repository already contains:

- Terraform for an OCI `VM.Standard.A1.Flex` VM with 2 OCPUs, 12 GB RAM, and a 100 GB boot disk.
- A VCN, public subnet, internet gateway, and inbound rules for ports 80 and 443.
- Cloud-init that installs Docker, Docker Compose, Cosign, systemd timers, and the DUSK repository.
- A Docker Compose stack for Traefik, PostgreSQL, Keycloak, the control plane, and the console.
- A protected GitHub Actions deployment from `main` using OCI Run Command.
- Multi-architecture container builds, SBOMs, provenance, keyless Cosign signing, blue/green deployment, health checks, rollback, and nightly synthetic-data reset.
- Application and proxy restrictions that disable the evaluation API and reject API mutation methods.

The deployment implements anonymous one-click access only when both public-demo mode and its separate anonymous-access flag are enabled. The backend maps every anonymous request to the fixed synthetic tenant with the viewer role, rejects supplied bearer credentials, and blocks unsafe HTTP methods. Production and company-sandbox deployments keep OIDC as the default.

Before marketing the site publicly, choose one of these access models:

1. **Configured: anonymous read-only synthetic demo.** The console opens without login, and the backend creates a fixed demo-only viewer principal.
2. **Alternative: social login through Keycloak.** Visitors authenticate with a supported identity provider. It avoids issuing passwords but adds login and consent friction.

This runbook assumes option 1 will be implemented before public launch. Production and real company sandboxes must continue to require normal OIDC authentication.

## Responsibility split

### Manual actions for the owner

Only the account owner or cloud administrator can safely complete these actions:

- Create or verify the OCI account and select its home region.
- Add a payment method if Oracle requires account verification.
- Own or purchase the public domain.
- Add the domain to Cloudflare and change registrar nameservers.
- Create the OCI compartment and bootstrap identity permissions.
- Authenticate Terraform to OCI from an administrator workstation or approved infrastructure runner.
- Review and approve the Terraform plan before it creates resources.
- Create the OCI Identity Domain applications and Identity Propagation Trust.
- Copy generated OCIDs, client IDs, and secrets into the correct GitHub environment.
- Make the two GHCR packages public, or supply a read-only package credential.
- Approve the protected production deployment.
- Decide when the demo is ready to be announced publicly.

These steps cannot be safely automated by a repository agent because they involve account ownership, billing, domain control, production secrets, or an approval gate.

### Work that Codex can perform in this repository

Once the required values and cloud resources exist, Codex can:

- Implement an isolated anonymous, read-only public-demo mode without weakening production authentication.
- Add backend tenant, role, route, and mutation enforcement for the fixed synthetic tenant.
- Update the console to skip OIDC only when an explicit public-demo configuration is enabled.
- Add tests proving production still rejects anonymous requests and the public demo cannot select another tenant or mutate data.
- Update Terraform, Compose, Traefik, cloud-init, workflow, and documentation when required.
- Add safer Cloudflare-origin restrictions after the certificate strategy is agreed.
- Run local tests and static validation.
- Prepare the `dev` to `main` pull request and address code-review findings.
- Inspect the GitHub workflow run and diagnose deployment failures.
- Verify the public endpoints and deployment evidence after release.

Codex will not invent cloud identifiers, request billing approval, expose secrets in chat or source control, bypass branch protection, or claim that a successful CI run proves the live deployment works.

## Values to collect

Create a secure password-manager entry for this deployment. Record the following values, but do not put secrets in this Markdown file or commit them to Git.

| Value | Example or format | Secret? | Used in |
| --- | --- | --- | --- |
| OCI home region | `uk-london-1` | No | Terraform and GitHub variable |
| OCI compartment OCID | `ocid1.compartment...` | No | Terraform and GitHub variable |
| Availability domain | Full OCI AD name | No | Terraform |
| OCI instance OCID | `ocid1.instance...` | No | GitHub variable |
| OCI VM public IP | IPv4 address | No | Cloudflare DNS |
| OCI identity-domain URL | `https://idcs-...identity.oraclecloud.com` | No | GitHub variable |
| WIF OAuth client ID | OCI-generated ID | Treat as sensitive | GitHub secret |
| WIF OAuth client secret | OCI-generated secret | Yes | GitHub secret |
| Demo root domain | Domain you own | No | Cloudflare |
| Console hostname | `demo.example.com` | No | DNS and VM environment |
| API hostname | `api.demo.example.com` | No | DNS and VM environment |
| Authentication hostname | `auth.demo.example.com` | No | DNS and VM environment |
| ACME email | Operations/security email | No | VM environment |
| PostgreSQL password | At least 32 random bytes | Yes | VM environment |
| Keycloak database password | At least 32 random bytes | Yes | VM environment |
| Keycloak admin username | Non-default unique name | Yes | VM environment |
| Keycloak admin password | At least 32 random bytes | Yes | VM environment |
| Cursor signing key | At least 32 random bytes | Yes | VM environment |

## Phase 1: create and prepare the OCI account

### 1.1 Create or sign in to OCI

- Create an account: <https://signup.cloud.oracle.com/>
- Sign in to the OCI Console: <https://cloud.oracle.com/>
- OCI Always Free resource reference: <https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm>
- OCI first Linux VM tutorial: <https://docs.oracle.com/en-us/iaas/Content/Compute/tutorials/first-linux-instance/overview.htm>

Choose the home region carefully. Always Free compute must be created in the tenancy's home region, and the home region cannot be changed later. Prefer a region close to the expected audience, but first confirm that Ampere A1 capacity is realistically available.

OCI can return `Out of host capacity` even when the account is eligible. Try another availability domain if the region has more than one. If capacity remains unavailable, wait and retry or use a paid shape. Do not silently substitute an undersized micro VM; the complete DUSK stack is not designed for 1 GB RAM.

### 1.2 Create a dedicated compartment

In the OCI Console:

1. Open **Identity & Security**.
2. Open **Compartments**.
3. Select the root compartment.
4. Click **Create Compartment**.
5. Name it `dusk-public-demo`.
6. Add a description such as `Isolated resources for the public synthetic DUSK demo`.
7. Record the new compartment OCID from its details page.

OCI compartment documentation: <https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingcompartments.htm>

Do not deploy the demo into a compartment that contains customer or production resources.

### 1.3 Authenticate Terraform

Install Terraform 1.8 or newer:

- Terraform installation: <https://developer.hashicorp.com/terraform/install>
- OCI Terraform provider authentication: <https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/terraformproviderconfiguration.htm>

For a local administrative bootstrap, configure the OCI CLI/API-key profile according to Oracle's instructions. Keep `~/.oci/config` and private keys outside this repository. An approved CI infrastructure workflow with workload identity is preferable for repeatable long-term changes, but it is not currently included in this repository.

OCI CLI setup reference: <https://docs.oracle.com/en-us/iaas/Content/API/SDKDocs/cliinstall.htm>

Verify authentication without printing credentials:

```bash
oci iam region list --output table
```

## Phase 2: create the VM and network with Terraform

Do not manually create the Compute instance through the OCI web form. The linked OCI VM tutorial is useful for account orientation, but manual VM creation would duplicate and drift from the repository's Terraform resources.

Terraform will create:

- `dusk-public-demo` VCN and subnet.
- Internet gateway and default route.
- Security list allowing inbound TCP 80 and 443.
- Oracle Linux 9 ARM64 VM.
- `VM.Standard.A1.Flex`, 2 OCPUs, and 12 GB RAM.
- 100 GB boot volume.
- Public IPv4 address.
- OCI Compute Instance Run Command plugin.
- Cloud-init bootstrap without SSH keys.

### 2.1 Provide Terraform inputs

From the repository root:

```bash
export TF_VAR_region='<OCI_REGION>'
export TF_VAR_compartment_id='<OCI_COMPARTMENT_OCID>'
export TF_VAR_availability_domain='<FULL_AVAILABILITY_DOMAIN_NAME>'
```

Find availability domains with:

```bash
oci iam availability-domain list \
  --compartment-id '<TENANCY_OCID>' \
  --query 'data[].name' \
  --raw-output
```

Do not set `TF_VAR_ssh_authorized_keys`. The Terraform module deliberately rejects SSH keys for this public host.

### 2.2 Configure Terraform state before applying

The Terraform module requires the native OCI Object Storage backend. This provides state locking, and bucket versioning provides recovery from accidental overwrites or deletion. Backend account values are supplied during `terraform init`; credentials and account identifiers are not committed to the repository.

Create a private, versioned state bucket before initializing Terraform:

```bash
export OCI_NAMESPACE="$(oci os ns get --query data --raw-output)"

oci os bucket create \
  --namespace-name "$OCI_NAMESPACE" \
  --compartment-id "$TF_VAR_compartment_id" \
  --name dusk-public-demo-terraform-state \
  --public-access-type NoPublicAccess \
  --storage-tier Standard \
  --versioning Enabled
```

Initialize the partial backend using only non-secret settings. The OCI backend reads API-key authentication from the local `DEFAULT` profile:

```bash
terraform init \
  -backend-config="bucket=dusk-public-demo-terraform-state" \
  -backend-config="namespace=$OCI_NAMESPACE" \
  -backend-config="region=$TF_VAR_region" \
  -backend-config="key=public-demo/terraform.tfstate" \
  -backend-config="config_file_profile=DEFAULT"
```

Terraform state contains infrastructure identifiers and can contain sensitive material. Confirm `.tfstate` files are ignored before proceeding:

```bash
git check-ignore deploy/public-demo/terraform/terraform.tfstate
```

If the command produces no matching ignore rule, stop and add a repository ignore rule before running `apply`.

### 2.3 Plan and apply

```bash
cd deploy/public-demo/terraform
terraform fmt -check
terraform validate
terraform plan -out=tfplan
```

Export the tenancy OCID before planning so Terraform can create the
instance-specific Run Command dynamic group:

```bash
export TF_VAR_tenancy_id="$OCI_TENANCY_OCID"
```

Review the plan. It should create one A1 instance plus the documented network resources. It should not create SSH access, unrelated resources, or paid shapes.

After manual approval:

```bash
terraform apply tfplan
terraform output
```

Record:

- `instance_id`
- `public_ip`
- `compartment_id`

If OCI reports an A1 capacity error, do not edit the code to use a paid shape without reviewing cost implications.

### 2.4 Verify cloud-init and the host

Use OCI Run Command instead of SSH:

1. Open <https://cloud.oracle.com/compute/instances>.
2. Select `dusk-public-demo`.
3. Open **Resources > Run command**.
4. Create a command using the shell script option.
5. Run the following non-secret checks:

```bash
sudo cloud-init status --wait
sudo systemctl status docker --no-pager
docker version
docker compose version
cosign version
sudo test -d /opt/dusk/repository
sudo systemctl list-timers 'dusk-demo-*' --all
```

Cloud-init is complete only when its status is `done` and every check succeeds.
The Terraform stack also creates the instance-specific dynamic group and policy
required for the agent to poll commands. Cloud-init grants the `ocarun` agent
administrator execution because the reviewed deployment command must manage
root-owned configuration and Docker. Treat permission to create Run Commands
for this instance as root access and keep it instance-scoped.

## Phase 3: add the domain to Cloudflare

### 3.1 Create or sign in to Cloudflare

- Cloudflare dashboard: <https://dash.cloudflare.com/>
- Add a domain: <https://developers.cloudflare.com/fundamentals/setup/manage-domains/add-site/>
- Change nameservers: <https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/>

In Cloudflare:

1. Click **Add a domain**.
2. Enter the root domain you own.
3. Select the Free plan unless a paid feature is deliberately required.
4. Review imported DNS records.
5. Copy the two Cloudflare nameservers.
6. At the domain registrar, replace the existing authoritative nameservers with the Cloudflare nameservers.
7. Wait until Cloudflare reports the zone as active.

Nameserver propagation can take time. Do not continue to certificate validation until the zone is active.

### 3.2 Create DNS records

Cloudflare DNS instructions: <https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/>

Open **Cloudflare Dashboard > your domain > DNS > Records** and create:

| Type | Name | Content | Proxy status | TTL |
| --- | --- | --- | --- | --- |
| `A` | `demo` | Terraform `public_ip` | DNS only initially | Auto |
| `A` | `api.demo` | Terraform `public_ip` | DNS only initially | Auto |
| `A` | `auth.demo` | Terraform `public_ip` | DNS only initially | Auto |

The current Traefik configuration uses Let's Encrypt HTTP-01 on port 80. Start with DNS-only records so initial origin certificate issuance and troubleshooting are direct. After the stack is healthy and all certificates have been issued, enable the Cloudflare proxy for all three records.

### 3.3 Configure TLS

- Cloudflare SSL/TLS modes: <https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/>
- Full (strict) mode: <https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/>

After Traefik has valid certificates:

1. Open **SSL/TLS > Overview**.
2. Select **Full (strict)**.
3. Do not select `Flexible`; it would leave Cloudflare-to-origin traffic without proper HTTPS validation.
4. Enable proxying for the three DNS records.
5. Confirm each hostname still works over HTTPS.

Enable HSTS only after all hosts and certificate renewal have been verified. A bad HSTS configuration can make recovery harder.

### 3.4 Configure edge protections

At minimum:

- Enable available managed WAF protections.
- Rate-limit repeated requests to the API and authentication host.
- Do not cache `auth.demo.example.com/realms/*`.
- Do not cache authenticated or dynamic API responses.
- Cache only versioned static assets from the console.
- Add uptime monitoring from outside OCI.

Cloudflare proxy reference: <https://developers.cloudflare.com/dns/proxy-status/>

The current OCI security list accepts 80 and 443 from the whole internet. Cloudflare proxying does not by itself prevent direct access through a discovered origin IP. Restricting ingress to Cloudflare IP ranges is a recommended later hardening task, but it should be implemented together with a reviewed certificate-renewal and health-check design.

## Phase 4: create the protected VM environment file

The deployed scripts read:

```text
/etc/dusk-demo/deployment.env
```

Generate independent random values in a password manager. Each password or signing key should contain at least 32 random bytes. Do not reuse production, personal, OCI, GitHub, or domain credentials.

Use OCI Run Command to create the file from this repository template:

```text
deploy/public-demo/deployment.example.env
```

The finished file must contain:

```dotenv
CONSOLE_URL=https://demo.example.com
API_URL=https://api.demo.example.com
AUTH_URL=https://auth.demo.example.com
ACME_EMAIL=security@example.com
POSTGRES_PASSWORD=<GENERATED_SECRET>
KEYCLOAK_DATABASE_PASSWORD=<GENERATED_SECRET>
KEYCLOAK_ADMIN_USERNAME=<GENERATED_NON_DEFAULT_NAME>
KEYCLOAK_ADMIN_PASSWORD=<GENERATED_SECRET>
DECISION_CURSOR_SIGNING_KEY=<GENERATED_SECRET>
```

Replace `example.com` with the owned domain. When entering the command in OCI, ensure command output does not echo the secret values. Then enforce ownership and permissions:

```bash
sudo chown root:root /etc/dusk-demo/deployment.env
sudo chmod 0600 /etc/dusk-demo/deployment.env
sudo stat -c '%U:%G %a %n' /etc/dusk-demo/deployment.env
```

The expected result is:

```text
root:root 600 /etc/dusk-demo/deployment.env
```

The deployment script will refuse to run if this condition is not met.

## Phase 5: make GHCR images readable by the VM

The workflow publishes:

- `ghcr.io/shieldtech-ltd/dusk-control-plane`
- `ghcr.io/shieldtech-ltd/dusk-console`

GitHub package visibility documentation: <https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility>

Recommended for a public demo:

1. Open the ShieldTech-Ltd organisation on GitHub.
2. Open **Packages**.
3. Open each DUSK package.
4. Open **Package settings**.
5. Change visibility to **Public**.
6. Confirm an unauthenticated `docker pull` can read a published digest.

Images must not contain secrets. Secrets are injected on the VM at runtime. If package visibility must remain private, create a read-only package token and securely configure `docker login ghcr.io` on the VM. That introduces another long-lived secret and rotation obligation.

## Phase 6: configure GitHub-to-OCI workload identity

This is the most specialised manual step. It should be completed by an OCI identity administrator and reviewed against Oracle's current documentation.

- OCI identity domains overview: <https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm>
- Add a confidential application: <https://docs.oracle.com/en-us/iaas/Content/Identity/applications/add-confidential-application.htm>
- JWT token exchange and Identity Propagation Trust: <https://docs.oracle.com/en-us/iaas/Content/Identity/api-getstarted/json_web_token_exchange.htm>
- GitHub OIDC reference: <https://docs.github.com/en/actions/concepts/security/openid-connect>

### 6.1 Create the token-exchange application

In OCI:

1. Open **Identity & Security > Domains**.
2. Select the identity domain used for the demo automation.
3. Open **Integrated applications**.
4. Add a **Confidential application**.
5. Name it `github-dusk-public-demo-token-exchange`.
6. Enable only the OAuth/token-exchange capabilities required by Oracle's current JWT exchange procedure.
7. Do not grant Identity Domain Administrator or general OCI administrator roles to this runtime application.
8. Activate the application.
9. Record the client ID and client secret securely.
10. Record the identity-domain HTTPS origin.

Oracle's procedure may require a temporary administrative application or administrator token to create the trust. Remove or disable temporary elevated bootstrap credentials after the trust is created.

### 6.2 Create the Identity Propagation Trust

Configure a trust with these restrictions:

```text
Issuer: https://token.actions.githubusercontent.com
Subject type: Resource
Impersonating resource: githubactions
Audience used by workflow: oci-public-demo
Repository: ShieldTech-Ltd/DUSK
Branch: refs/heads/main
job_workflow_ref: ShieldTech-Ltd/DUSK/.github/workflows/public-demo.yml@refs/heads/main
OAuth client: the token-exchange application's client ID
```

Use exact claim matching. Do not allow every repository in the GitHub organisation or every branch to exchange a token.

### 6.3 Grant least-privilege OCI policy

The federated resource principal needs only enough permission to create, inspect, and cancel Compute Instance Agent commands for the DUSK demo instance. It does not need permission to create instances, alter networks, read unrelated compartments, or administer the tenancy.

OCI policy syntax and available resource conditions can change. Generate the exact statement from the principal/trust OCI creates, scope it to the `dusk-public-demo` compartment, add instance-specific conditions where OCI supports them, and have an OCI administrator review it before saving.

OCI policy documentation: <https://docs.oracle.com/en-us/iaas/Content/Identity/policieshow/Policy_Basics.htm>

## Phase 7: enter GitHub environment values

The environment is named exactly:

```text
public-demo-production
```

Open:

<https://github.com/ShieldTech-Ltd/DUSK/settings/environments>

GitHub environment documentation: <https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments>

### 7.1 Add environment secrets

Open `public-demo-production`, then under **Environment secrets** add:

| Name | Value |
| --- | --- |
| `OCI_WIF_CLIENT_ID` | Token-exchange confidential application client ID |
| `OCI_WIF_CLIENT_SECRET` | Token-exchange confidential application client secret |

Enter these as environment secrets, not repository variables and not `.env` files.

### 7.2 Add environment variables

Under **Environment variables** add:

| Name | Value |
| --- | --- |
| `OCI_IDENTITY_DOMAIN_URL` | Identity-domain HTTPS origin, without an OAuth path |
| `OCI_REGION` | Region identifier such as `uk-london-1` |
| `OCI_COMPARTMENT_ID` | Terraform `compartment_id` output |
| `OCI_INSTANCE_ID` | Terraform `instance_id` output |

### 7.3 Verify environment protection

Confirm:

- Required reviewer is configured.
- Prevent self-review is enabled when another authorised reviewer exists.
- Only protected branches can deploy.
- Administrator bypass is disabled if that matches the organisation's emergency process.

The deployment job cannot access the environment secrets until its protection rules pass.

## Phase 8: verify anonymous read-only demo access

The repository implements this boundary. Keep the following controls and tests green before the public launch and after every authentication or routing change.

### Backend controls

- Add an explicit anonymous-demo configuration that defaults to `false`.
- Permit it only when public-demo mode is also enabled.
- Create the principal server-side with a fixed tenant ID and fixed viewer roles.
- Ignore and reject caller-supplied tenant overrides.
- Permit only an allowlist of dashboard read endpoints.
- Reject all mutations at the application layer even if the proxy is bypassed.
- Keep the evaluation API, API documentation, background enforcement, and outbox worker disabled.
- Prevent anonymous access to Keycloak and administrative APIs.

### Console controls

- Load the public-demo flag from runtime configuration.
- Skip OIDC redirect only when the explicit anonymous-demo flag is true.
- Display a permanent synthetic-data/read-only banner.
- Hide all controls that cannot succeed in read-only mode.
- Provide a clear request-a-sandbox or contact-sales action.
- Preserve the current OIDC/PKCE path as the default for every non-demo deployment.

### Security tests

- Production mode rejects an anonymous request.
- Public-demo mode permits the fixed read routes.
- Public-demo mode rejects a different tenant ID.
- Public-demo mode rejects `POST`, `PUT`, `PATCH`, and `DELETE` at Traefik and the application.
- Public-demo mode cannot create tokens, API keys, policies, users, integrations, or evaluations.
- Public-demo mode cannot read data outside the synthetic tenant.
- Turning off the anonymous flag restores OIDC without rebuilding the application.

No frontend-only login bypass will be accepted. The backend is the security boundary.

## Phase 9: release from `dev` to `main`

The deployment workflow does not deploy from `dev`. It runs only after the protected `main` branch passes the complete security gate.

Release sequence:

1. Merge and verify the anonymous-demo implementation on `dev`.
2. Open a pull request from `dev` to `main`.
3. Wait for all required CI and security checks.
4. Resolve every review discussion.
5. Obtain the required approval.
6. Merge the pull request.
7. Open the GitHub Actions run for the merged `main` commit.
8. Review the exact commit and approve the `public-demo-production` deployment.
9. Monitor the build, signing, token exchange, OCI Run Command, and public health checks.

GitHub Actions page:

<https://github.com/ShieldTech-Ltd/DUSK/actions>

GitHub deployment approval reference: <https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments>

The automated deployment will:

1. Check out the immutable `main` commit.
2. Build ARM64 and AMD64 control-plane and console images.
3. Publish the images, SBOM, and provenance.
4. Sign the immutable image digests with Cosign.
5. Exchange the GitHub OIDC token through the OCI Identity Domain.
6. Invoke the VM using OCI Run Command.
7. Verify image signatures on the VM.
8. Update the host repository to the candidate commit.
9. Start the shared core services.
10. Deploy into the inactive blue or green slot.
11. Run database migrations.
12. Reset the synthetic demo corpus.
13. Wait for container health.
14. Switch Traefik to the candidate slot.
15. Verify console, API, and authentication endpoints.
16. Remove the old slot only after successful verification.
17. Restore the previous route if the candidate deployment fails.

## Phase 10: production acceptance checks

Do not publish the demo URL until all items pass.

### Infrastructure

- [ ] OCI shows the instance as running.
- [ ] Cloud-init status is `done`.
- [ ] Docker and Cosign checks succeed.
- [ ] Only ports 80 and 443 are reachable publicly.
- [ ] OCI Run Command works without SSH.
- [ ] Terraform state is encrypted, backed up, and absent from Git.

### DNS and TLS

- [ ] All three records resolve through Cloudflare after proxying is enabled.
- [ ] Cloudflare SSL mode is Full (strict).
- [ ] Valid certificates are served for console, API, and authentication hosts.
- [ ] HTTP redirects to HTTPS.
- [ ] HSTS is enabled only after validation.

### Application security

- [ ] The public console opens without credentials if anonymous mode was selected.
- [ ] The banner clearly says the data is synthetic and read-only.
- [ ] No customer, employee, or production data is present.
- [ ] Anonymous access cannot choose another tenant.
- [ ] `POST`, `PUT`, `PATCH`, and `DELETE` are rejected.
- [ ] Evaluation and administration endpoints are unavailable.
- [ ] Production and company-sandbox configurations still require OIDC.
- [ ] Keycloak administration is not publicly exposed through Traefik.

### Reliability and operations

- [ ] Nightly reset changes only the dedicated demo database.
- [ ] Five-minute health timer is running.
- [ ] External uptime alerting reaches an operator.
- [ ] VM reboot restores the stack without manual intervention.
- [ ] A deliberately failed candidate deployment leaves the previous slot reachable.
- [ ] OCI audit logs identify the GitHub federated workflow subject.
- [ ] A credential rotation and incident-response owner is documented.

### Customer conversion

- [ ] Console has a visible request-a-sandbox or contact-sales action.
- [ ] Privacy-conscious analytics measure demo visits and conversions.
- [ ] A real company sandbox is provisioned separately and never shares the public-demo tenant or database.

## Day-two operations

### Application releases

Normal releases are made through reviewed commits to `main`. Do not edit application files directly on the VM. The protected workflow supplies traceability, immutable images, signature verification, and rollback.

### Infrastructure changes

Modify `deploy/public-demo/terraform`, review a Terraform plan, and apply it through the approved infrastructure process. Do not manually edit OCI networking and then leave Terraform unaware of the change.

### Secret rotation

Rotate:

- OCI WIF client secret.
- PostgreSQL and Keycloak database passwords using a planned database procedure.
- Keycloak administrator credential.
- Cursor signing key with consideration for outstanding cursors.

Update the GitHub environment or protected VM environment as appropriate. Never paste secret values into an issue, pull request, workflow log, or support conversation.

### Backups and data policy

The public demo contains replaceable synthetic data. Define whether any backup is actually required. Avoid accumulating visitor identifiers or turning the demo database into an undeclared customer-data store.

### Availability limitation

This design avoids intentional application sleep and cold starts, but it is still one free-tier VM in one failure domain. OCI can have capacity shortages and can reclaim qualifying idle Always Free instances. It is appropriate for a public showcase, not an uptime-sensitive customer production service.

## Final handoff checklist

The owner supplies:

- [ ] Active OCI account and selected home region.
- [ ] Dedicated compartment OCID.
- [ ] Availability domain with A1 capacity.
- [ ] Approved Terraform plan and created instance.
- [ ] Terraform outputs: instance OCID and public IP.
- [ ] Active Cloudflare zone and three hostnames.
- [ ] Protected VM environment file.
- [ ] OCI Identity Propagation Trust and least-privilege policy.
- [ ] WIF client ID and secret entered directly into GitHub.
- [ ] Four OCI environment variables entered into GitHub.
- [ ] GHCR packages readable by the VM.
- [ ] Approval for the production deployment.

Codex completes and verifies:

- [x] Anonymous read-only public-demo implementation.
- [ ] Production-authentication regression protection.
- [ ] Security and tenancy tests.
- [ ] Required deployment configuration changes.
- [ ] Local verification and review-ready PR.
- [ ] Review feedback fixes.
- [ ] Workflow and deployment-log diagnosis.
- [ ] Public endpoint and rollback verification after approval.

The deployment is complete only when the live URLs, access boundary, synthetic dataset, automated reset, alerts, and rollback have all been demonstrated. A merged pull request or green CI run alone is not production evidence.
