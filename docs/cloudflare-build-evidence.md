# Cloudflare candidate build evidence

The native policy image is built from `workers/dusk-runtime/Dockerfile`, using a digest-pinned Python 3.13.18 Alpine 3.24 base and hash-verified Python dependency closure. The control plane and harness also use this base. Compatible musl wheels for both locked dependency closures were downloaded and hash-checked before proposing the platform change. The CI build labels the candidate source commit and captures the immutable image ID. Its isolated boot check must pass before scans continue.

The Alpine candidate replaces Debian libraries with unresolved stable-release findings. Python remains on the same minor version, but libc changes, so Docker boot, PostgreSQL migrations, watch/enforce scenarios and both scanner gates must pass on the rebuilt images before approval. Native and control-plane third-party Python dependencies remain hash-locked. Preserve and promote the exact scanned artifact, its package SBOM and digest rather than rebuilding during deployment.

## Library patch candidate requiring explicit review

The shared `dusk-agent-harness/mock-prod/alpine-runtime-patches.sh` installs SQLite 3.54.1-r0, zlib 1.4-r0, and OpenSSL libraries libcrypto3 and libssl3 at 3.5.9-r1 from downloaded APK files. Each package has a fixed SHA-256 per architecture. APK validates package signatures and installs with `--no-network`. Each image build verifies both installed OpenSSL package revisions, the SQLite and zlib versions loaded by Python, and an in-memory SQL integrity check. The package URLs and hashes are retained inside every patched image and in scan evidence.

SQLite is the upstream stable 3.54.1 release, but its APK comes from Alpine's **pre-release 3.25 branch**; zlib comes from stable 3.24. This mixed-branch library candidate requires Ritik's explicit review. It retains the same `libsqlite3.so.0` SONAME and declares only the existing musl dependency. That metadata is feasibility evidence, not a substitute for runtime tests. Both amd64 and arm64 package hashes are pinned; actual validation must state which architecture ran. Do not describe this as a fully stable-branch backport or an Alpine distribution upgrade.

The previous expired Debian exceptions are removed. The only proposed exception is CVE-2026-119586 attributed to APK `sqlite-libs=3.54.1-r0`. [SQLite's primary explanation](https://sqlite.org/cves.html) identifies this as a C CLI `.recover` workflow issue, not a core-library bug. The CLI package/executable is absent, asserted during builds and before scans, and DUSK has no recovery-shell workflow. This narrowly scoped component-attribution exception expires 2026-11-30 and requires maintainer review. It does not exempt any SQLite library memory-corruption finding. The suppression-expiry policy runs before scanning, so an expired disposition blocks publication.

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

The `container-evidence` artifact contains image IDs, scanner references and version outputs, the native smoke report, CycloneDX SBOMs, Trivy reports and Grype reports. A required command, version check, boot test or high/critical vulnerability result fails the job. The sole proposed component-attribution exception in `ci/grype.yml` is scoped and governed as described above; prior expired Debian exceptions are removed. Scanner database freshness and execution output must be inspected on the candidate run.

The image ID links CI's boot test and scans to its artifact. It does not prove that the same image is active on Cloudflare. Before deployment, record the source commit, published immutable image digest, signed provenance/SBOM verification, protected reviewer approval, resource inventory and rollback input. Registry publication, signature verification and live Cloudflare startup are outstanding until independently observed. This document does not close issue284.
