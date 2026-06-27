"""Seed Attio with demo data before recording the demo video.

Creates company records with DUSK research scores and a sample security
incident so the CRM looks live and populated when the camera is rolling.

Run once before the demo:

    python demo/seed_attio.py
"""

from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()

_COMPANIES = [
    {
        "name": "Anthropic",
        "score": 82,
        "confidence": 0.91,
        "risk_level": "high",
        "reasoning": "AI safety leader with major funding and enterprise traction. Series E funded, $7.3B raised.",
        "risk_flags": ["high_valuation"],
    },
    {
        "name": "Mistral AI",
        "score": 74,
        "confidence": 0.85,
        "risk_level": "high",
        "reasoning": "Fast-growing open-model lab with strong European enterprise pipeline. 1.1B EUR raised.",
        "risk_flags": [],
    },
    {
        "name": "Cohere",
        "score": 68,
        "confidence": 0.78,
        "risk_level": "medium",
        "reasoning": "Enterprise NLP APIs with proven B2B revenue but crowded market. $270M raised.",
        "risk_flags": ["competitive_market"],
    },
    {
        "name": "Scale AI",
        "score": 71,
        "confidence": 0.82,
        "risk_level": "high",
        "reasoning": "Data labelling and evaluation platform critical to AI pipelines. $1B+ revenue reported.",
        "risk_flags": [],
    },
    {
        "name": "Weights & Biases",
        "score": 58,
        "confidence": 0.70,
        "risk_level": "medium",
        "reasoning": "MLOps tooling used by most AI labs. Strong retention but niche TAM for enterprise security.",
        "risk_flags": ["niche_market"],
    },
]

_INCIDENTS = [
    {
        "agent_id": "netops-agent",
        "action": "firewall_rule_change",
        "score": 0.92,
        "verdict": "WOULD-BLOCK",
        "mitre": "T1562.004",
        "blast_radius": "HIGH",
        "reasoning": "Agent attempted to open fw-guest-to-restricted path. Hidden prompt injection detected.",
        "predicted_next": "Lateral movement into restricted segment via newly opened path.",
        "decision_id": "demo-seed-001",
    },
    {
        "agent_id": "iam-agent",
        "action": "role_assignment",
        "score": 0.78,
        "verdict": "WOULD-BLOCK",
        "mitre": "T1098",
        "blast_radius": "CRITICAL",
        "reasoning": "Agent assigned admin role to an external service account outside its normal pattern.",
        "predicted_next": "Privilege escalation and lateral movement using newly acquired admin access.",
        "decision_id": "demo-seed-002",
    },
]


def main() -> int:
    api_key = os.getenv("ATTIO_API_KEY", "")
    if not api_key:
        console.print("[red]ATTIO_API_KEY not set in .env -- cannot seed Attio[/red]")
        return 1

    from dusk.integrations.attio_client import create_incident, push_company_score

    console.rule("[bold]Seeding Attio with DUSK demo data[/bold]")
    console.print()

    console.print("[bold]Company research scores[/bold]")
    for c in _COMPANIES:
        t0 = time.time()
        note_id = push_company_score(
            company=c["name"],
            score=int(c["score"]),
            confidence=float(str(c["confidence"])),
            risk_level=str(c["risk_level"]),
            reasoning=str(c["reasoning"]),
            risk_flags=[str(f) for f in c["risk_flags"]],
            decision_id=f"seed-{c['name'].lower().replace(' ', '-')}",
        )
        ms = int((time.time() - t0) * 1000)
        verdict = "QUALIFIED" if int(c["score"]) >= 65 else "FLAGGED"
        if note_id:
            console.print(
                f"  [green]ok[/green]  {c['name']:<22} [{verdict}] score={c['score']}  "
                f"[dim]{ms}ms note={note_id[:8]}...[/dim]"
            )
        else:
            console.print(f"  [red]fail[/red]  {c['name']} -- check ATTIO_API_KEY and workspace permissions")

    console.print()
    console.print("[bold]Security incidents[/bold]")
    for inc in _INCIDENTS:
        t0 = time.time()
        note_id = create_incident(
            agent_id=str(inc["agent_id"]),
            action=str(inc["action"]),
            score=float(str(inc["score"])),
            verdict=str(inc["verdict"]),
            mitre=str(inc["mitre"]),
            blast_radius=str(inc["blast_radius"]),
            reasoning=str(inc["reasoning"]),
            predicted_next=str(inc["predicted_next"]),
            decision_id=str(inc["decision_id"]),
        )
        ms = int((time.time() - t0) * 1000)
        if note_id:
            console.print(
                f"  [green]ok[/green]  {inc['agent_id']:<18} {inc['verdict']}  score={inc['score']}  "
                f"[dim]{ms}ms note={note_id[:8]}...[/dim]"
            )
        else:
            console.print(f"  [red]fail[/red]  {inc['agent_id']} -- note not created")

    console.print()
    console.rule("[bold green]Attio seeded -- open app.attio.com to verify[/bold green]")
    console.print()
    console.print(
        "You should see:\n"
        "  - 5 company records (Anthropic, Mistral AI, Cohere, Scale AI, Weights & Biases)\n"
        "  - Each with a DUSK research note showing score + risk level\n"
        "  - 2 security incident notes (netops-agent, iam-agent)\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
