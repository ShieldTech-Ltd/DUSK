# Security Policy

## Reporting a Vulnerability

Do not open a public GitHub issue for security vulnerabilities.

Report using GitHub Security Advisories (Security tab > Report a vulnerability).
You will receive acknowledgement within 72 hours.
We target a patch within 30 days for critical issues, 90 days for others.
We follow coordinated disclosure, we will notify you before public disclosure.

## Scope

In scope: bypass of detection logic, privilege escalation via the CLI,
dependency vulnerabilities, unsafe handling of pcap input.

Out of scope: theoretical attacks with no practical path, issues in lab/
scenarios (test code only).

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.2.x   | Yes |
| 0.1.x   | No |

Security fixes are applied to the latest released minor version.

## Deployment Boundary

The HTTP service under `examples/agent-action-monitor` is a local integration
example. Its default Compose configuration binds published ports to localhost.
It is not an internet-ready deployment and must not be exposed directly.

Production deployments must provide authentication, TLS, request rate limits,
network allowlists, restricted CORS, centralized audit logging, and a managed
WSGI server or equivalent ingress. Set `DUSK_GATE_API_KEY` to require bearer
authentication at the example gate. Store that value in a secret manager, not
in source control, image layers, Compose files, or shell history.

See [docs/production-hardening.md](docs/production-hardening.md) for the full
deployment checklist.
