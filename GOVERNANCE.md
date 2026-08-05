# DUSK Governance

## Mission

DUSK provides vendor-neutral, open-source runtime behavioral detection and
policy gating for autonomous agent actions. It helps defenders observe and
constrain the consequences of agent goal hijack, tool misuse, privilege abuse,
and rogue behavior.

DUSK does not claim compliance with the OWASP Top 10 for Agentic Applications.
It implements controls that detect or mitigate a documented subset of those
risks.

## Maintainers and proposed OWASP project leaders

The current maintainers are:

- Tanvir Farhad, `@TFT444`
- Ritik Sah, `@ritiksah141`

If OWASP accepts DUSK as an Incubator project, both maintainers are proposed as
project leaders, subject to Foundation approval and any leader agreement OWASP
provides. OWASP membership is recommended by the Foundation but is not required
for project leadership. Project leadership is personal and is not held on
behalf of an employer.

## Decision making

Routine changes use pull requests and require passing checks plus one approving
review. Security-sensitive, governance, release, and policy changes require a
Code Owner review. Maintainers seek consensus for changes to project scope,
licensing, or supported security guarantees.

If consensus cannot be reached, the maintainers document the alternatives in
the pull request. The project leaders then make a recorded decision based on
the project mission, user safety, and OWASP policy. Disputes that cannot be
resolved within the project may be escalated through OWASP's dispute process
after the project is accepted.

## Contributions

Participation is open to the public. Contributions follow
[CONTRIBUTING.md](CONTRIBUTING.md), the Developer Certificate of Origin, and
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Maintainers review issues and pull
requests in a timely and respectful manner.

## Releases and activity

The project aims to publish at least one release each year. Releases use
Semantic Versioning, have changelog entries, source and wheel artifacts, an
SBOM, checksums, and build provenance where the hosting platform supports it.

## Vendor neutrality

Core deterministic detection remains usable without a commercial service or
paid feature. Optional integrations must be replaceable, documented as
optional, and must not control project governance or access to core features.
