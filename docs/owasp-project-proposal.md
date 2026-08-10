# DUSK OWASP Incubator Proposal

## Project type and audience

- Type: Tool
- Audience: Defenders, builders, and security reviewers
- Proposed maturity: Incubator
- License: Apache-2.0 for code and CC BY-SA 4.0 for documentation

## Purpose

DUSK is a runtime behavioral detection and policy gate for autonomous agent
actions. It learns a known-good profile per agent and evaluates proposed
control-plane actions and observed network behavior for deviations before an
attack chain completes.

## Unique value

OWASP's Agentic Security Initiative defines risks and recommended mitigations.
DUSK operationalizes a subset of that guidance as a vendor-neutral control that
can run without an LLM or paid API. It evaluates behavior after an agent forms
an action but before an enforcing integration applies it. This position is
different from prompt scanners, model gateways, identity controls, and static
guidance.

DUSK should coordinate with the OWASP GenAI Security Project rather than
duplicate its taxonomy. The canonical risk definitions remain upstream. DUSK's
role is implementation, test fixtures, detection evidence, and operational
examples.

### Related OWASP work and differentiation

- [OWASP GenAI Security Project](https://genai.owasp.org/) publishes the
  agentic risk taxonomy and guidance that DUSK references. DUSK implements a
  limited set of runtime controls and does not replace that guidance.
- [OWASP Agent Security Regression Harness](https://github.com/OWASP/Agent-Security-Regression-Harness)
  executes security regression scenarios against agent systems. DUSK evaluates
  proposed actions and observed network behavior during operation. The projects
  are complementary, and DUSK scenarios could become harness fixtures.
- [OWASP Agent Memory Guard](https://owasp.org/www-project-agent-memory-guard/)
  protects agent memory operations. DUSK does not inspect or protect memory. It
  focuses on action behavior, policy verdicts, and network evidence after an
  agent proposes an operation.

No existing OWASP project named DUSK was found in the public project inventory
during the application review on 10 August 2026. Foundation approval remains
required before using OWASP branding.

## Scope

In scope:

- per-agent behavioral baselines
- deterministic action anomaly scoring
- allow, observe, or block verdicts
- network sweep and boundary-probe detection
- evidence, MITRE mappings, and predicted next-stage reporting
- optional inference enrichment with safe deterministic fallback

Out of scope:

- claiming complete coverage of ASI01 through ASI10
- prompt filtering or model alignment
- identity issuance and authentication
- vulnerability scanning of agent frameworks
- automatic trust of a learned baseline

## Project health

The repository includes automated tests, coverage enforcement, strict typing,
static security analysis, dependency auditing, secret scanning, contribution
guidance, confidential vulnerability reporting, a threat model, and branch
protection guidance. Release automation creates artifacts, an SBOM, checksums,
and provenance. A localhost-only Docker demo verifies both watch and enforce
behavior, including whether a proposed action reached the mock target.

## Leadership and support

Proposed leaders and maintainers are listed in [GOVERNANCE.md](../GOVERNANCE.md).
GitHub Issues handle defects, feature requests, support, and design questions.
If accepted, the project will request an official OWASP Slack channel and
publish its OWASP project page within the required timeframe.

The service desk submission must provide a current contact email and GitHub
username for each proposed leader. The submitter must enter and verify those
details directly in the private support request. The public conduct contacts in
this repository do not replace that application field.

## Submission summary

Use this copy-ready summary in the OWASP new project request:

> DUSK is a vendor-neutral open-source runtime behavioral detection and policy
> gate for autonomous agent actions. It learns reviewed known-good behavior per
> agent and evaluates proposed control-plane actions and observed network
> behavior for deviation. The deterministic core runs without an LLM or paid
> service. DUSK complements the OWASP GenAI Security Project by implementing and
> testing a documented subset of Agentic Security Initiative mitigations rather
> than redefining the taxonomy. We request Incubator status as a tool project.
> The repository uses Apache-2.0 for code, CC BY-SA 4.0 for
> documentation, DCO sign-off, two proposed leaders, public contribution and
> governance processes, confidential vulnerability reporting, automated
> security checks, and a documented annual release commitment.

Repository: `https://github.com/ShieldTech-Ltd/DUSK`

Requested type and level: Tool, Incubator

## Pre-submission checklist

- [x] Open-source code license
- [x] Open documentation license
- [x] Public purpose, scope, and roadmap
- [x] Tool selected as the single OWASP project type
- [x] At least two proposed project leaders
- [x] Contribution guidelines and DCO process
- [x] Code of Conduct
- [x] Security policy and private reporting path
- [x] Explicit relationship to existing OWASP work
- [x] Related OWASP projects reviewed and differentiation documented
- [x] Each proposed leader has confirmed active Individual or Complimentary
      Membership
- [ ] Current leader emails supplied privately in the service desk request
- [ ] Each proposed leader has confirmed willingness to follow OWASP policies
- [ ] Employer affiliations disclosed and leadership independence discussed
- [ ] Application demo and readiness evidence merged through `dev` into the
      default branch
- [ ] v0.2.0 release and demo recording published
- [ ] New Project Request submitted through the OWASP service desk

The unchecked pre-submission items require maintainer confirmation or repository
approval. They must not be marked complete based only on repository content.

## Post-approval checklist

- [ ] OWASP Foundation approval recorded
- [ ] Leader agreements signed within 30 days if OWASP provides them
- [ ] Repository transferred to or approved for the OWASP source platform
- [ ] OWASP project page created within 30 days of repository access
- [ ] OWASP project page lists leaders, contact emails, activity date, and version
- [ ] OWASP support channel created
