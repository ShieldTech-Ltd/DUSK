"""Dusk command-line interface.

Commands:
    dusk scan --file <path.pcap>          analyse a pcap and print a verdict
    dusk scan --file <path.pcap> --json   machine-readable JSON output
    dusk watch --interface <iface>        live mode (coming in v0.2)

A global ``--verbose`` flag raises the root logger to DEBUG; otherwise the
log level comes from :class:`~dusk.config.Config` (``WARNING`` by default),
keeping output clean.
"""

from __future__ import annotations

import json
import logging
import sys

import click
from rich.console import Console

from dusk import __version__
from dusk.config import ConfigError, get_config
from dusk.core.engine import VERDICT_ALERT, Engine

logger = logging.getLogger("dusk.cli")
console = Console()


def _configure_logging(*, verbose: bool, level_name: str) -> None:
    """Configure the root logger.

    Args:
        verbose: When ``True``, force the root logger to ``DEBUG``.
        level_name: Otherwise, the level name to use (e.g. ``"WARNING"``).
    """
    level = logging.DEBUG if verbose else logging.getLevelName(level_name)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )


@click.group(help="Dusk — behavioral threat detection for agentic networks.")
@click.version_option(__version__, prog_name="dusk")
@click.option("--verbose", is_flag=True, default=False, help="Enable DEBUG logging.")
def main(verbose: bool) -> None:
    """Dusk CLI entry point: load config and configure logging."""
    try:
        config = get_config()
    except ConfigError as exc:
        # Logging isn't configured yet; surface the failure and exit.
        logging.basicConfig(level=logging.CRITICAL, stream=sys.stderr)
        logger.critical("Invalid configuration: %s", exc)
        console.print(f"[bold red]Configuration error:[/bold red] {exc}")
        raise SystemExit(2) from exc

    _configure_logging(verbose=verbose, level_name=config.log_level)
    logger.debug("Dusk %s starting (verbose=%s)", __version__, verbose)


@main.command(help="Analyse a pcap file and print a verdict.")
@click.option(
    "--file",
    "file_path",
    required=True,
    type=click.Path(),
    help="Path to the pcap file to analyse.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON instead of formatted output.",
)
def scan(file_path: str, as_json: bool) -> None:
    """Load a pcap, run the detection engine, and report the verdict.

    Exits ``1`` when the verdict is ALERT, ``0`` when CLEAR, and ``2`` on an
    input error (e.g. missing file).
    """
    # Import here so a missing scapy yields a clean message, not an import-time crash.
    try:
        from dusk.sensor.pcap import read_pcap
    except ImportError as exc:
        _fail(str(exc), as_json=as_json)
        return

    try:
        packets = read_pcap(file_path)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc), as_json=as_json)
        return

    # In JSON mode, suppress the responder's Rich/file side effects.
    engine = Engine(respond=not as_json)
    report = engine.run(packets)

    if as_json:
        payload = {
            "file": file_path,
            "packets_analysed": len(packets),
            **report.to_dict(),
        }
        click.echo(json.dumps(payload, indent=2))
    elif report.verdict == VERDICT_ALERT:
        console.print(
            f"[bold red]VERDICT: ALERT[/bold red] — analysed "
            f"{len(packets)} packets, {len(report.failures)} detection(s) fired."
        )
    else:
        console.print(
            f"[bold green]VERDICT: CLEAR[/bold green] — analysed "
            f"{len(packets)} packets, nothing suspicious."
        )

    sys.exit(1 if report.verdict == VERDICT_ALERT else 0)


@main.command(help="Live capture mode (coming in v0.2).")
@click.option("--interface", required=True, help="Network interface to watch.")
def watch(interface: str) -> None:
    """Stub for live capture mode."""
    logger.info("watch requested for interface %s (not yet implemented)", interface)
    console.print(
        f"[yellow]Live capture on '{interface}' is coming in v0.2.[/yellow]\n"
        "For now, capture traffic with tcpdump/tshark and run:\n"
        "    dusk scan --file <capture.pcap>"
    )


def _fail(message: str, *, as_json: bool) -> None:
    """Report an input error and exit with code 2."""
    logger.critical("%s", message)
    if as_json:
        click.echo(json.dumps({"error": message}, indent=2))
    else:
        console.print(f"[bold red]Error:[/bold red] {message}")
    sys.exit(2)


if __name__ == "__main__":
    main()
