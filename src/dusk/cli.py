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


@click.group(help="Dusk, behavioral threat detection for agentic networks.")
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
            f"[bold red]VERDICT: ALERT[/bold red], analysed "
            f"{len(packets)} packets, {len(report.failures)} detection(s) fired."
        )
    else:
        console.print(
            f"[bold green]VERDICT: CLEAR[/bold green], analysed "
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


@main.command(help="Ingest an agent action file (JSON list) and summarise it.")
@click.option(
    "--file",
    "file_path",
    required=True,
    type=click.Path(),
    help="Path to the JSON action file (a list of raw records) to ingest.",
)
@click.option(
    "--source",
    default="generic",
    show_default=True,
    help="Source name selecting the adapter (for example 'azure' or 'generic').",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit a machine-readable JSON summary instead of formatted output.",
)
def actions(file_path: str, source: str, as_json: bool) -> None:
    """Ingest a control-plane action file and report what was found.

    This is the v1.1 ingest stage: it normalises the records into AgentAction
    events and summarises them. It assigns no severity or verdict; later
    layers do that. Exits ``0`` on success and ``2`` on an input error.
    """
    from dusk.actions.ingest import ingest_file

    try:
        ingested = ingest_file(file_path, source)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc), as_json=as_json)
        return

    agents = sorted({a.agent_id for a in ingested})
    by_action_type: dict[str, int] = {}
    for entry in ingested:
        by_action_type[entry.action_type] = by_action_type.get(entry.action_type, 0) + 1

    if as_json:
        payload = {
            "file": file_path,
            "source": source,
            "actions_ingested": len(ingested),
            "agents": agents,
            "by_action_type": by_action_type,
        }
        click.echo(json.dumps(payload, indent=2))
    else:
        console.print(
            f"[bold green]INGESTED[/bold green] {len(ingested)} action(s) from "
            f"{len(agents)} agent(s) via the '{source}' adapter."
        )
        for action_type, count in sorted(by_action_type.items()):
            console.print(f"  {action_type}: {count}")

    sys.exit(0)


@main.command(help="Gate agent actions against a learned per-agent baseline.")
@click.option(
    "--baseline",
    "baseline_path",
    required=True,
    type=click.Path(),
    help="JSON list of known-good actions to learn each agent's normal behaviour.",
)
@click.option(
    "--check",
    "check_path",
    required=True,
    type=click.Path(),
    help="JSON list of actions to evaluate against the baseline.",
)
@click.option(
    "--source",
    default="generic",
    show_default=True,
    help="Source name selecting the adapter for both files.",
)
@click.option(
    "--enforce",
    is_flag=True,
    default=False,
    help="Render BLOCK instead of WOULD-BLOCK for refused actions.",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit a machine-readable JSON report instead of formatted output.",
)
def gate(baseline_path: str, check_path: str, source: str, enforce: bool, as_json: bool) -> None:
    """Learn a baseline, then render a verdict for each checked action.

    Exits ``1`` when any action is refused (WOULD-BLOCK or BLOCK), ``0`` when
    every action is allowed, and ``2`` on an input error.
    """
    from dusk.actions.ingest import ingest_file
    from dusk.actions.verdict import ActionGate

    try:
        known_good = ingest_file(baseline_path, source)
        to_check = ingest_file(check_path, source)
    except (FileNotFoundError, ValueError) as exc:
        _fail(str(exc), as_json=as_json)
        return

    gate_engine = ActionGate(enforce=enforce)
    gate_engine.learn(known_good)
    verdicts = gate_engine.evaluate_all(to_check)
    refused = [v for v in verdicts if v.refused]

    if as_json:
        payload = {
            "baseline": baseline_path,
            "check": check_path,
            "actions_evaluated": len(verdicts),
            "refused": len(refused),
            "results": [v.to_dict() for v in verdicts],
        }
        click.echo(json.dumps(payload, indent=2))
    else:
        for v in verdicts:
            a = v.analysis
            colour = {"ALLOW": "green", "WOULD-BLOCK": "yellow", "BLOCK": "red"}[v.verdict]
            console.print(
                f"[bold {colour}]{v.verdict:<11}[/bold {colour}] "
                f"{a.agent_id} {a.action_type} {a.target}  "
                f"[dim]score={a.score:.2f} blast={a.blast_radius}[/dim]"
            )
            if v.refused:
                console.print(f"            [dim]ATT&CK[/dim] {a.mitre_attack}")
                console.print(f"            [dim]ATLAS[/dim]  {a.mitre_atlas}")
                for reason in a.reasons:
                    console.print(f"            [dim]reason[/dim] {reason}")
                console.print(f"            [dim]next[/dim]   {a.predicted_next}")
        console.print(
            f"\n[bold]GATE[/bold] evaluated {len(verdicts)} action(s), refused {len(refused)}."
        )

    sys.exit(1 if refused else 0)


@main.command(help="Research a company and score it as a prospect.")
@click.argument("company")
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Emit machine-readable JSON instead of formatted output.",
)
def research(company: str, as_json: bool) -> None:
    """Fetch live intelligence on COMPANY and score it with Gemini Flash."""
    from dusk.agent import research_company

    try:
        decision = research_company(company)
    except Exception as exc:  # noqa: BLE001
        _fail(str(exc), as_json=as_json)
        return

    if as_json:
        click.echo(json.dumps(decision.to_dict(), indent=2))
    else:
        risk_colour = {"high": "red", "medium": "yellow", "low": "green"}[decision.risk_level.value]
        verdict = "QUALIFIED" if decision.score >= 65 else "FLAGGED"
        verdict_colour = "green" if verdict == "QUALIFIED" else "yellow"
        console.print(
            f"\n[bold {verdict_colour}]{verdict}[/bold {verdict_colour}]  "
            f"[bold]{decision.subject}[/bold]  "
            f"score=[bold {risk_colour}]{decision.score}/100[/bold {risk_colour}]  "
            f"confidence={decision.confidence:.0%}"
        )
        console.print(f"  [dim]reasoning:[/dim] {decision.reasoning}")
        if decision.risk_flags:
            console.print(f"  [dim]risk flags:[/dim] {', '.join(decision.risk_flags)}")
        console.print(
            f"  [dim]latency:[/dim] tavily={decision.latency_tavily_ms}ms  "
            f"gemini={decision.latency_gemini_ms}ms  "
            f"[dim]id:[/dim] {decision.id}"
        )

    sys.exit(0)


@main.command(help="Start the DUSK research API server.")
@click.option("--port", default=5000, show_default=True, help="Port to listen on.")
def serve(port: int) -> None:
    """Run the Flask API server."""
    import os as _os

    _os.environ.setdefault("FLASK_PORT", str(port))
    from dusk.api import run

    console.print(f"[bold]DUSK API[/bold] starting on port {port}")
    run()


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
