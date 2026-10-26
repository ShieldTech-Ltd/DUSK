"""Terminal product commands, shared by direct use and stdio MCP clients."""

from __future__ import annotations

import json
from pathlib import Path

import click

from dusk.terminal import TerminalError, TerminalRuntime, load_terminal_config

_CONFIG = click.Path(exists=True, dir_okay=False, path_type=Path)


def _runtime(path: Path) -> TerminalRuntime:
    try:
        return TerminalRuntime(load_terminal_config(path))
    except TerminalError as exc:
        raise click.ClickException(str(exc)) from None


def register_terminal_commands(group: click.Group) -> None:
    """Register without changing existing packet/file-analysis commands."""
    group.add_command(doctor)
    group.add_command(run)
    group.add_command(mcp)


@click.command(help="Validate fixed-command configuration and local audit storage.")
@click.option("--config", "config_path", required=True, type=_CONFIG)
def doctor(config_path: Path) -> None:
    runtime = _runtime(config_path)
    click.echo(
        json.dumps(
            {
                "status": "CONFIGURED",
                "configured_operations": len(runtime.config.operations),
                "enabled_operations": sum(op.enabled for op in runtime.config.operations.values()),
                "coverage": "configured fixed commands only",
                "os_sandbox": False,
            }
        )
    )


@click.command(help="Execute one operator-configured command through DUSK's permit verifier.")
@click.argument("operation")
@click.option("--config", "config_path", required=True, type=_CONFIG)
@click.option(
    "--request-id", required=True, help="Unique UUID; retries with this ID never reexecute."
)
def run(operation: str, config_path: Path, request_id: str) -> None:
    try:
        result = _runtime(config_path).execute(operation, request_id)
    except TerminalError as exc:
        raise click.ClickException(str(exc)) from None
    click.echo(json.dumps(result))
    if result["status"] != "EXECUTED":
        raise click.exceptions.Exit(1)


@click.command(help="Run DUSK's fixed-command MCP server over stdio.")
@click.option("--config", "config_path", required=True, type=_CONFIG)
def mcp(config_path: Path) -> None:
    from dusk.mcp_server import create_server

    create_server(_runtime(config_path)).run(transport="stdio")
