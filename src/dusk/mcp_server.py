"""MCP transport for the same fixed-command runtime used by the CLI."""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from dusk import __version__
from dusk.terminal import TerminalRuntime


def create_server(runtime: TerminalRuntime) -> MCPServer:
    server = MCPServer(
        "DUSK",
        version=__version__,
        instructions=(
            "Only operator-configured fixed commands are available. Use a fresh UUID "
            "for each intended operation and reuse it on retries. No arbitrary shell, "
            "arguments or machine-wide protection is provided."
        ),
    )

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    def dusk_operations() -> list[dict[str, object]]:
        """List configured operation names and whether they are enabled."""
        return runtime.catalogue()

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=True,
            open_world_hint=True,
        )
    )
    def dusk_execute(operation: str, request_id: str) -> dict[str, str]:
        """Execute a fixed configured operation once; request_id must be a UUID.

        Effects depend on the trusted operator's configured command. Output is suppressed.
        An unapproved operation is blocked, and duplicate IDs are never executed again.
        """
        return runtime.execute(operation, request_id)

    return server
