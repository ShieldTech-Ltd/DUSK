# DUSK terminal and MCP candidate

This branch adds real fixed-command execution through `dusk run` and an MCP
stdio server through `dusk mcp`. Version 0.3.0rc1 is a prerelease candidate,
not a production release. Do not install the unrelated PyPI package named `dusk`.

## Install from GitHub

Use Python 3.11 or newer, pip and Git, preferably in a dedicated virtual environment:

```bash
python -m pip install "dusk-security @ git+https://github.com/ShieldTech-Ltd/DUSK.git@feat/terminal-mcp-release"
dusk
```

`dusk` displays the DUSK title, version and setup commands. Use an exact commit
SHA in place of the branch name for a reproducible installation. This command
downloads from the public repository and does not require any files from the
developer's computer. It becomes available when this branch is pushed.

The short registry command `pip install dusk-security` requires a separate PyPI
publication. It is not available until that publication is verified. On PyPI,
prerelease installation will use `pip install --pre dusk-security`.

## Build an installer

Build with `python -m build --wheel`, then install the resulting wheel into a
dedicated virtual environment with `python -m pip install PATH_TO_WHEEL`.
The distribution is `dusk-security`; its terminal command is `dusk`.

The candidate uses version 0.3.0rc1. Do not replace published 0.2.0 release assets.
The harness now imports as `dusk_harness`, allowing both distributions to be
installed without overwriting each other's `dusk` modules. Harness launchers
must use `python -m dusk_harness.api` or `dusk_harness.api:app`.

## Configure

Create an operator-owned JSON file with this structure. Replace every path and
the digest with real values. Hash the selected executable with SHA-256.

```json
{
  "version": 1,
  "tenant_id": "my-team",
  "agent_id": "local-agent",
  "audit_path": "C:/DUSK/local-audit.sqlite3",
  "operations": {
    "approved-task": {
      "executable": "C:/trusted/bin/task.exe",
      "sha256": "REPLACE_WITH_64_LOWERCASE_HEX_CHARACTERS",
      "args": [],
      "cwd": "C:/trusted/work",
      "timeout_seconds": 30,
      "enabled": true
    }
  }
}
```

The audit file's parent directory must already exist. Linux and macOS use
absolute native paths. Protect the configuration, executable, arguments' target
files, working directory and audit database from modification by the agent.
Approving an interpreter, script or extensible tool also trusts the code and
configuration it loads. Hashing its executable alone does not pin that code.

```powershell
dusk doctor --config C:/trusted/dusk.json
dusk run approved-task --config C:/trusted/dusk.json --request-id UUID
dusk mcp --config C:/trusted/dusk.json
```

Replace UUID with a newly generated UUID for each intended operation. Reuse it
when retrying the same request. Duplicate IDs are refused across runtime
restarts. An uncertain or failed execution still consumes its ID. Inspect the
effect before deciding whether a new operation is appropriate.

## MCP client configuration

Configure a client's stdio MCP server with the absolute virtual environment
`dusk` executable and arguments `["mcp", "--config", "ABSOLUTE_CONFIG_PATH"]`.
On Windows the executable is in `Scripts/dusk.exe`; on Unix it is in `bin/dusk`.
No user client configuration is changed automatically.

Tools: `dusk_operations` lists names and enabled states. `dusk_execute` accepts
only an operation name and request UUID. The runtime uses fixed operator-owned
argv, no shell, suppressed command output and a minimal child environment.
The SQLite receipt contains metadata, not command arguments or output.

## Protection boundaries and release gates

This is an allowlist mediator, not an OS sandbox or a separate security identity.
It does not intercept unrelated tool calls. An agent with direct shell access
can bypass the mediator. A timeout does not promise to terminate descendants.
SQLite receipts are local and are not tamper-proof against the same OS user.
The signed permit is generated and checked within the same trusted process.
This path does not evaluate the enterprise policy pack or send dashboard data.

Before stable release: verify Linux and macOS, run full CI and dependency
checks, configure protected PyPI publishing and exercise actual Codex and Claude
client onboarding. A successful SDK protocol test is not proof of those clients'
complete user experience. Customer SaaS onboarding and hosted control-plane
integration remain separate work.
