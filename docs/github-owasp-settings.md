# GitHub Settings for OWASP Readiness

This runbook contains the repository settings that require an organization
owner or repository administrator. Apply them to
`https://github.com/ShieldTech-Ltd/DUSK` before submitting the OWASP New Project
Request.

## 1. Repository profile

Open **Settings**, then **General**.

Set the repository description to:

```text
Vendor-neutral runtime behavioral detection and policy gating for autonomous AI agent actions.
```

Leave the website field empty until an official OWASP project page or other
maintained public project site exists. Do not use an unrelated company page.

Add these repository topics:

```text
agent-security
ai-security
behavioral-analysis
runtime-security
application-security
python
open-source
```

Under **Features**:

- Keep Issues enabled.
- Enable Discussions so the support link in the issue chooser works.
- Keep Projects optional.
- Keep Wiki disabled unless the maintainers commit to keeping a second
  documentation surface current.

Keep `main` as the default branch. Preserve the existing pull request, review,
merge, and branch settings. The maintainers explicitly chose not to change that
workflow as part of the OWASP application preparation.

## 2. Pull request configuration

No change is required. Do not run `scripts/protect-main.sh` as part of this
application work and do not create a new branch ruleset. The current pull
request system remains the maintainer-approved workflow.

## 3. Release tags

No setting change is required for the application. Continue using verified
signed annotated release tags. The current `v0.2.0` tag is verified and points
to the reviewed `main` commit.

## 4. Actions permissions

Open **Settings**, then **Actions**, then **General**.

- Select **Allow enterprise, and select non-enterprise, actions and reusable
  workflows**.
- Enable **Allow actions created by GitHub**.
- Add `aquasecurity/trivy-action@*` to the allowed actions list. This is the
  only non-GitHub action currently used. It is pinned to an immutable commit in
  the workflow.
- Set default workflow permissions to **Read repository contents and packages**.
- Disable **Allow GitHub Actions to create and approve pull requests**.
- Require approval for workflows from first-time external contributors.
- Keep fork pull request workflows read-only and do not expose repository
  secrets to them.

Do not add broad repository-level write permissions. Each workflow job must
request only the permissions it needs.

## 5. Code security and analysis

Open **Settings**, then **Code security and analysis**. Enable every feature
available to the public repository:

- Dependency graph
- Dependabot alerts
- Dependabot security updates
- Grouped security updates, if available
- Keep CodeQL default setup disabled because the checked-in advanced CodeQL
  workflow already runs `security-extended` queries and uploads results
- Secret scanning
- Push protection
- Validity checks for detected secrets, if available
- Private vulnerability reporting

The repository already contains Dependabot configuration, a CodeQL workflow,
Semgrep, dependency auditing, secret scanning, and container scanning. GitHub
settings should complement those controls.

After enabling private vulnerability reporting, confirm that **Security**, then
**Advisories**, then **Report a vulnerability** opens a private report form.

## 6. Discussions and community support

After enabling Discussions:

1. Create a `Q&A` category for installation and usage questions.
2. Create an `Ideas` category for design proposals.
3. Pin a welcome post that links to the README, contribution guide, security
   policy, roadmap, and Code of Conduct.
4. Confirm that maintainers receive notifications for new discussions.

Do not accept vulnerability reports through Discussions or public Issues.

## 7. DCO and review enforcement

Install the official DCO GitHub App for this repository if the OWASP source
platform does not provide it automatically. Keep the repository's `dco` CI job
as defense in depth.

Confirm that:

- A pull request with an unsigned-off commit fails DCO validation.
- Code owners are automatically requested for sensitive files.
- At least one qualified reviewer other than the author approves each change.

## 8. Release and recording

The signed `v0.2.0` release already includes the wheel, source archive, SBOM,
checksums, and build provenance. The remaining release task is the public demo
recording.

Follow [OWASP Demo Recording Guide](owasp-demo-recording.md), then attach this
exact asset to the existing release:

```text
dusk-owasp-demo-v0.2.0.mp4
```

After upload:

1. Open the asset in a private browser window and confirm it is public.
2. Add the recording URL to the README and OWASP application package.
3. Confirm the recording shows tag `v0.2.0` and an unedited watch and enforce
   run.
4. Mark the recording rows complete in
   [OWASP Application Readiness Tracker](owasp-readiness-tracker.md).

## 9. Private leader confirmations

Do not commit private emails, membership evidence, or service desk contents to
the repository. Before submission, both proposed leaders must privately
confirm:

- Active OWASP Individual or Complimentary Membership
- Consent to serve as project leader
- Willingness to follow current OWASP policies
- Current email and GitHub username
- Employer affiliation
- Leadership independence plan if both leaders share an employer

Enter this information directly into the OWASP service desk request.

## 10. Final verification

The repository is ready to submit only when all of the following are true:

- Repository description and topics are visible publicly.
- Discussions support link works.
- The existing pull request system remains unchanged.
- Actions default to read-only permissions.
- Security analysis, secret scanning, push protection, Dependabot, and private
  vulnerability reporting are enabled.
- The demo recording is attached and linked.
- Both leader confirmations are complete privately.
- The readiness tracker contains no blocked or unconfirmed submission gate.
