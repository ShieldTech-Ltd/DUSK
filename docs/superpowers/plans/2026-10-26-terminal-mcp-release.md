# Terminal MCP Implementation Plan

> Execute inline with test-driven-development and verification-before-completion. Worktree C:/DUSK/DUSK-terminal-release preserves unrelated work.

Goal: implement the first real installable protected-command CLI/MCP slice. Spec: ../specs/2026-10-26-terminal-mcp-release.md.

- [x] Add failing tests for trusted fixed-command configuration and persistent request claims in tests/test_terminal_runtime.py.
- [x] Implement src/dusk/terminal.py with strict JSON configuration, SHA-256 executable pinning, existing permit/proxy use, SQLite audit and bounded subprocess execution.
- [x] Add failing CLI and MCP tests. Implement src/dusk/terminal_cli.py and src/dusk/mcp_server.py; register commands from cli.py.
- [x] Update distribution/build metadata and version, add the official SDK dependency, then test stdio protocol with the real SDK client.
- [x] Address legacy harness namespace ownership in a focused testable migration.
- [x] Build/install the exact wheel in an isolated environment; run installed commands outside the checkout and existing permit/core regression tests.
- [x] Document real installation and client registration, trust boundary and remaining publication/customer gates.

No public package upload, push, merge or live client configuration change is necessary for local implementation and validation.

User extension: make the candidate installable beyond the local computer and
display DUSK when launched. Add public branch installation, a versioned release
candidate, installation CI and opt-in PyPI publishing. Public branch push is
within this extended scope. PyPI publication requires the account's pending
publisher registration; stable release and merge gates remain unchanged.
