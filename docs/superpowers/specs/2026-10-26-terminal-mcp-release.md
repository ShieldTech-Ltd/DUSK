# Terminal and MCP release contract

The owner authorized continuing the real installable product after the terminal installation audit. This first implementation slice supplies an installable stdio server and a deterministic executor for operator-configured fixed commands. It does not publish to PyPI or claim arbitrary Codex/Claude activity is contained.

## CLI and execution contract

- Distribution remains dusk-security; executable remains dusk. The unrelated PyPI dusk package is not ours.
- `dusk doctor --config PATH` validates configuration, executable identities and local audit storage.
- `dusk run NAME --config PATH --request-id UUID` executes one fixed operation through the same code as MCP.
- `dusk mcp --config PATH` starts stdio MCP, with protocol output only on stdout.
- MCP exposes operation catalogue and execution by configured name and UUID. The agent cannot supply command arguments, environment, working directory, credentials or approval flags.
- Operator JSON config defines version 1, tenant/agent identity, absolute SQLite audit path and named operations. Every operation has an absolute executable, its SHA-256, fixed string argv, absolute cwd, bounded timeout and explicit enabled flag.
- Unknown/disabled operations fail closed before starting a process. Executable hash is revalidated before execution. Each authorized action is bound to an existing DUSK Ed25519 permit and verified by RestrictedExecutionProxy.
- Each request ID is claimed durably in SQLite before execution. Reuse fails across restarts, including after uncertain outcomes. Re-running intentionally requires a new ID.
- Audit records contain request ID, configured operation name, action digest, timestamps and outcome, not arguments, secrets, stdout or stderr. Storage failure prevents execution. Command output is suppressed by default for this first slice.
- Child runs with shell=False, stdin closed, bounded timeout and a small environment. No credentials are copied to the agent by DUSK. Configured executables may themselves have side effects and spawn children; this adapter is not an OS sandbox or a descendant process containment system.
- Config, executable and cwd must be controlled by a trusted operator and protected from the agent. Same-user malicious code can change files or bypass tools unless an external process/container/credential boundary restricts it. No hidden automatic interception is claimed.

## Packaging

The new runtime lives only in the canonical root dusk package; it does not import or require the separately packaged legacy harness. Prevent the legacy harness distribution from overwriting dusk modules by giving it a distinct import namespace, with all its owned startup/test references migrated together and focused tests. If that migration cannot be completed safely in the same slice, document it as a release blocker and do not claim co-installation safety.

Use compatible build metadata and version 0.3.0 for a future release. Public publishing remains gated on clean wheel installation, client verification, CI, security review, cross-platform evidence and an owned PyPI trusted publisher.

## Verification

Test fail-closed invalid config, default-deny unknown/disabled operation, argument injection refusal through MCP schema, executable replacement, audit storage failure, request replay after restart, timeout/nonzero exit, permit binding and an observable harmless command effect. Test MCP initialize/list_tools/call_tool using an actual subprocess. Build a wheel and exercise installed commands outside the repository. Do not modify the user's live Codex/Claude configurations; provide registration commands and use isolated config for checks where possible.
