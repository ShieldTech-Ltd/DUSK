# Cloudflare candidate build evidence

The native policy image is built from `workers/dusk-runtime/Dockerfile`, using the pinned Python base, fixed Debian snapshot and hash-verified Linux Python dependency closure. The CI build labels the candidate source commit and captures the immutable image ID. Its isolated boot check must pass before scans continue.

## Scanner inventory

Verified against official release repositories and published registry manifests on2026-11-16:

| Tool | Release | Immutable image index |
| --- | --- | --- |
| Hadolint | 2.15.1 | `hadolint/hadolint@sha256:a1d49ae1a4e83c1dbad26b8c1ad7588c8bd1e04f4866b34ad3cac50335198552` |
| Trivy | 0.76.2 | `aquasec/trivy@sha256:8f6bb947dbc528902e11f2f5be52f7b519f6a39d5d148f41166f2040499768fb` |
| Syft | existing pinned build | `anchore/syft@sha256:b8c170b8e51bfc4779ec3ef4399942c57290f5ce76a9c3af564c9d00d4946a6b` |
| Grype | 0.121.3 | `anchore/grype@sha256:13113eeceab017260370cf540e1d25442c59665fd07d1b09b66d63bb0c282887` |

Primary release sources: [Hadolint](https://github.com/hadolint/hadolint/releases/tag/v2.15.1), [Trivy](https://github.com/aquasecurity/trivy/releases/tag/v0.76.2), [Grype](https://github.com/anchore/grype/releases/tag/v0.121.3). Runtime version output is retained with the evidence. Updates require a reviewed reference change, version check, build and scan; tags alone cannot retarget the pinned execution.

## Execution and artifacts

`scripts/ci/container_controls.sh` captures each local image ID, exports that exact image to a temporary Docker archive, and mounts the archive read-only for Trivy and Syft. Neither scanner receives the Docker socket. Grype reads the generated SBOM through a read-only mount. Temporary archives are removed, including on scanner failure.

The `container-evidence` artifact contains image IDs, scanner references and version outputs, the native smoke report, CycloneDX SBOMs, Trivy reports and Grype reports. A required command, version check, boot test or high/critical vulnerability result fails the job. Existing reviewed vulnerability exceptions remain in `ci/grype.yml`; this change adds none. Scanner database freshness and execution output must be inspected on the candidate run.

The image ID links CI's boot test and scans to its artifact. It does not prove that the same image is active on Cloudflare. Before deployment, record the source commit, published immutable image digest, signed provenance/SBOM verification, protected reviewer approval, resource inventory and rollback input. Registry publication, signature verification and live Cloudflare startup are outstanding until independently observed. This document does not close issue284.
