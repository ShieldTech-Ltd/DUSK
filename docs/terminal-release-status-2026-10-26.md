# Terminal and MCP implementation status

Verdict: 0.3.0rc1 install candidate verified on Windows, prepared for public
GitHub installation. Stable production release and PyPI publication remain open.

Implemented in `feat/terminal-mcp-release`, based on `origin/dev` at
`f2f5a7e644c01ba9683f55f82a849d6f7a509119`. Primary checkout preserved.

## Delivered

- `dusk doctor`, `dusk run`, `dusk mcp` and `python -m dusk`.
- Operator-configured fixed operations with executable digest verification.
- Existing signed permit verifier before command effects.
- SQLite request claims prevent duplicate execution across restarts and concurrent requests.
- Metadata receipts, blocked unknown/disabled operations, nonzero/timeout handling.
- MCP discovery and real subprocess tool invocation through the official SDK.
- Operator instructions in [terminal-install.md](terminal-install.md).
- `dusk` opens a DUSK branded screen with the version and setup commands.
- Harness imports migrated to `dusk_harness`, with Docker and CI references updated.
- Synchronized 0.3.0rc1 metadata and an opt-in PyPI Trusted Publishing job.
- A three-platform installed-wheel CI workflow.

## Verification

- Main Python suite excluding platform-specific CI tests: 561 passed, 2 skipped.
- Harness suite: 373 passed, 9 skipped.
- CI tests excluding Unix deployment-shell tests: 147 passed.
- The broader Windows run cannot execute the Unix deployment-shell tests because
  bash receives a Windows path. Those tests are not reported as passing here.
- Ruff check on all new Python files: passed.
- Mypy on the four new implementation modules and 25 harness modules: passed.
- Isolated core wheel/sdist and harness wheel builds: successful, version 0.3.0rc1.
- Fresh virtual environment installed that wheel outside the checkout.
- Copied CLI/runtime tests executed against the installed package: 16 passed.
  The MCP child process also used the installed package, with no source tree available.
- Fresh environment `pip check`: no broken requirements.

Artifacts: `C:/DUSK/terminal-release-artifacts/rc1/`.
Both wheels install together successfully with distinct import packages.

## Required next gates

1. Complete full CI, dependency security review, Linux/macOS installation checks
   and Docker startup validation.
2. Test actual Codex and Claude onboarding in isolated client configurations.
3. Configure the PyPI account's pending trusted publisher and protected `pypi`
   GitHub environment. See [publishing instructions](pypi-publishing.md).
4. Build authenticated hosted control-plane onboarding and dashboard ingestion
   before claiming the terminal runtime is connected to the hosted SaaS.

## Independent boundary review

The allowlist mediator trusts its operator's configuration and commands. A hashed
interpreter may still load unpinned scripts or modules. Same-user agents can
modify writable configuration or bypass DUSK with direct tool access. Executable
hash verification has a filesystem race before process creation. SQLite is not
a tamper-proof remote ledger. Timeout handling does not guarantee descendant
termination. No enterprise policy evaluation, remote signing authority or
machine-wide interception was introduced. These boundaries prevent a truthful
claim of universal agent protection from this candidate.

No PyPI publication, user MCP configuration mutation, production deployment or
merge was performed. Public candidate branch publication is tracked separately.
