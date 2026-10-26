# PR checks and release automation

PR check suites contain validation jobs. Publishing and deployment run from
separate event-specific workflows, so they do not appear as skipped PR checks.

| Workflow | Trigger | Purpose |
| --- | --- | --- |
| `dusk.yml` | PRs and trusted branch pushes | Full CI and security gate, including Worker/Container packaging |
| `terminal-install.yml` | PRs and the terminal candidate branch | Installed-wheel checks on Windows, Linux and macOS |
| `control-plane-image-validation.yml` | Relevant PR changes | Multi-architecture image build, no publishing |
| `console-image-validation.yml` | Relevant PR changes | Multi-architecture image build, no publishing |
| `control-plane-image.yml` | Existing trusted dev/tag push events | Original signed image publishing and attestation |
| `console-image.yml` | Existing trusted dev/tag push events | Original signed image publishing and attestation |
| `deploy-validated-main.yml` | Main pushes | Wait for successful CI on the exact main SHA, then invoke the protected deployment |
| `public-demo.yml` | Reusable workflow call | Deploy the exact validated main SHA after environment approval |

The release workflow filenames used in image signatures and OIDC trust remain
unchanged. Main deployment waits for the exact main push's CI result and passes that SHA into
the existing reusable workflow. It checks out that SHA, checks main ancestry,
and retains `public-demo-production` environment approval. The caller runs only
on main pushes and uses read-only Actions access to verify the source run.

Workflow separation does not turn a failing or unexecuted validation into a
passing result. Failed checks must be fixed and rerun on the current PR head.
Tests requiring external services or protected credentials are not represented
as live-provider certification by these CI checks.
