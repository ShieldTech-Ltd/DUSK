"""Terminal landing screen, kept separate from machine-readable command output."""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from dusk import __version__


def show_welcome(console: Console) -> None:
    """Display the product identity and the first real setup commands."""
    heading = Text("DUSK", style="bold cyan")
    heading.append(f"  v{__version__}", style="dim")
    heading.append("\nAgent action security", style="white")
    console.print(Panel(heading, border_style="cyan", padding=(1, 2), expand=False))
    console.print("Protection starts when configured operations run through DUSK.")
    console.print()
    console.print("[bold]Get started[/bold]")
    console.print("  dusk doctor --config PATH    Check your operation configuration")
    console.print("  dusk run NAME --config PATH --request-id UUID")
    console.print("                               Run an approved operation")
    console.print("  dusk mcp --config PATH       Connect an MCP client")
    console.print("  dusk --help                  See all commands")
    console.print()
    console.print(
        "[dim]Setup: https://github.com/ShieldTech-Ltd/DUSK/blob/"
        "feat/terminal-mcp-release/docs/terminal-install.md[/dim]"
    )
