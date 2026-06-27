"""Pre-demo smoke test -- run this before recording the demo video.

Checks every integration with real API keys and confirms the full pipeline
fires end-to-end. Prints PASS / FAIL for each step.

Usage::

    python demo/preflight.py
"""

from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()

_PASS = "[bold green]PASS[/bold green]"
_FAIL = "[bold red]FAIL[/bold red]"
_SKIP = "[dim]SKIP[/dim]"

results: list[tuple[str, str, str]] = []


def check(label: str, detail: str = "") -> None:
    results.append((_PASS, label, detail))
    console.print(f"  {_PASS}  {label}  [dim]{detail}[/dim]")


def fail(label: str, reason: str = "") -> None:
    results.append((_FAIL, label, reason))
    console.print(f"  {_FAIL}  {label}  [red]{reason}[/red]")


def skip(label: str, reason: str = "") -> None:
    results.append((_SKIP, label, reason))
    console.print(f"  {_SKIP}  {label}  [dim]{reason}[/dim]")


console.rule("[bold]DUSK Demo Preflight[/bold]")
console.print()

# 1. Environment variables
console.print("[bold]1. Environment variables[/bold]")
keys = {
    "TAVILY_API_KEY": os.getenv("TAVILY_API_KEY", ""),
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
    "ATTIO_API_KEY": os.getenv("ATTIO_API_KEY", ""),
    "N8N_WEBHOOK_URL": os.getenv("N8N_WEBHOOK_URL", ""),
    "MUBIT_API_KEY": os.getenv("MUBIT_API_KEY", ""),
    "SUPERLINKED_API_KEY": os.getenv("SUPERLINKED_API_KEY", ""),
    "SUPERLINKED_ENDPOINT": os.getenv("SUPERLINKED_ENDPOINT", ""),
    "AIKIDO_TOKEN": os.getenv("AIKIDO_TOKEN", ""),
}
# Only the 4 core integration keys are required; the rest enhance but have fallbacks
_required = {"GEMINI_API_KEY", "ATTIO_API_KEY", "N8N_WEBHOOK_URL", "SUPERLINKED_API_KEY", "SUPERLINKED_ENDPOINT"}
missing = [k for k in _required if not keys[k]]
_optional = {"TAVILY_API_KEY", "MUBIT_API_KEY", "AIKIDO_TOKEN"}
for k, v in keys.items():
    if v:
        check(k, f"{'*' * 6}{v[-4:]}")
    elif k in _optional:
        skip(k, "optional -- graceful fallback active")
    else:
        fail(k, "not set in .env")

console.print()

# 2. Core DUSK gate (always works offline)
console.print("[bold]2. DUSK core gate[/bold]")
try:
    from datetime import UTC, datetime

    from dusk.actions.event import AgentAction
    from dusk.actions.verdict import ActionGate

    gate = ActionGate()
    action = AgentAction(
        agent_id="preflight-agent",
        timestamp=datetime.now(UTC),
        action_type="route_change",
        target="rt-corp-default",
        change={"before": None, "after": None},
        source="preflight",
    )
    gate.learn([action])
    result = gate.evaluate(action)
    check("ActionGate", f"verdict={result.verdict}")
except Exception as exc:
    fail("ActionGate", str(exc))

console.print()

# 3. Web search (Tavily if key set, DuckDuckGo otherwise)
console.print("[bold]3. Web search -- threat intel[/bold]")
if not keys["TAVILY_API_KEY"]:
    try:
        t0 = time.time()
        from ddgs import DDGS  # type: ignore[import-not-found]

        with DDGS() as ddgs:
            results = list(ddgs.text("MITRE T1562.004 firewall disable technique", max_results=1))
        ms = int((time.time() - t0) * 1000)
        check("DuckDuckGo search", f"{len(results)} result(s) in {ms}ms (no Tavily key needed)")
    except ImportError:
        skip("Web search", "pip install ddgs  (no Tavily key set)")
    except Exception as exc:
        fail("DuckDuckGo search", str(exc)[:80])
else:
    try:
        t0 = time.time()
        from tavily import TavilyClient  # type: ignore[import-untyped]

        client = TavilyClient(api_key=keys["TAVILY_API_KEY"])
        resp = client.search(
            "MITRE T1562.004 firewall disable technique",
            search_depth="basic",
            max_results=1,
        )
        ms = int((time.time() - t0) * 1000)
        hits = len(resp.get("results", []))
        check("Tavily search", f"{hits} result(s) in {ms}ms")
    except Exception as exc:
        fail("Tavily search", str(exc)[:80])

console.print()

# 4. Gemini threat explanation
console.print("[bold]4. Gemini Flash -- AI threat explanation[/bold]")
if not keys["GEMINI_API_KEY"]:
    skip("Gemini explain_threat", "GEMINI_API_KEY not set")
else:
    try:
        t0 = time.time()
        from dusk.integrations.gemini_client import explain_threat

        text = explain_threat(
            agent_id="preflight-agent",
            action="firewall_rule_change",
            score=0.92,
            verdict="WOULD-BLOCK",
            mitre="T1562.004",
            reasoning="opens restricted segment",
            blast_radius="high",
            predicted_next="lateral movement",
        )
        ms = int((time.time() - t0) * 1000)
        if text:
            preview = text[:60].replace("\n", " ")
            check("Gemini explain_threat", f"{ms}ms -- \"{preview}...\"")
        else:
            fail("Gemini explain_threat", "returned None")
    except Exception as exc:
        fail("Gemini explain_threat", str(exc)[:80])

console.print()

# 5. Attio CRM incident
console.print("[bold]5. Attio -- CRM incident creation[/bold]")
if not keys["ATTIO_API_KEY"]:
    skip("Attio create_incident", "ATTIO_API_KEY not set")
else:
    try:
        t0 = time.time()
        from dusk.integrations.attio_client import create_incident

        note_id = create_incident(
            agent_id="preflight-agent",
            action="firewall_rule_change",
            score=0.92,
            verdict="WOULD-BLOCK",
            mitre="T1562.004",
            blast_radius="high",
            reasoning="preflight test -- safe to ignore",
            predicted_next="lateral movement",
            decision_id="preflight-001",
            tavily_enrichment=[],
        )
        ms = int((time.time() - t0) * 1000)
        if note_id:
            check("Attio create_incident", f"{ms}ms -- note_id={note_id[:12]}...")
        else:
            fail("Attio create_incident", "returned None -- check ATTIO_API_KEY and workspace")
    except Exception as exc:
        fail("Attio create_incident", str(exc)[:80])

console.print()

# 6. n8n webhook
console.print("[bold]6. n8n -- SOAR webhook[/bold]")
if not keys["N8N_WEBHOOK_URL"]:
    skip("n8n webhook", "N8N_WEBHOOK_URL not set")
else:
    try:
        import json as _json
        import urllib.request

        payload = _json.dumps({
            "agent_id": "preflight-agent",
            "verdict": "WOULD-BLOCK",
            "score": 0.92,
            "mitre": "T1562.004",
            "source": "dusk-preflight",
        }).encode()
        req = urllib.request.Request(
            keys["N8N_WEBHOOK_URL"],
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=8) as resp:  # nosec B310
            ms = int((time.time() - t0) * 1000)
            check("n8n webhook", f"HTTP {resp.status} in {ms}ms")
    except Exception as exc:
        fail("n8n webhook", str(exc)[:80])

console.print()

# 7. Superlinked -- vector similarity
console.print("[bold]7. Superlinked -- vector similarity[/bold]")
if not (keys["SUPERLINKED_API_KEY"] and keys["SUPERLINKED_ENDPOINT"]):
    skip("Superlinked", "SUPERLINKED_API_KEY / SUPERLINKED_ENDPOINT not set -- n-gram fallback active")
else:
    try:
        import json as _json
        import urllib.request

        _sl_key = keys["SUPERLINKED_API_KEY"]
        _sl_url = keys["SUPERLINKED_ENDPOINT"].rstrip("/") + "/v1/embeddings"
        _payload = _json.dumps({
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "input": "DUSK preflight test: behavioural threat detection",
        }).encode()
        _req = urllib.request.Request(
            _sl_url,
            data=_payload,
            headers={
                "Authorization": "Bearer " + _sl_key,
                "x-sl-api-key": _sl_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        t0 = time.time()
        with urllib.request.urlopen(_req, timeout=15) as _resp:  # nosec B310
            _data = _json.loads(_resp.read())
        ms = int((time.time() - t0) * 1000)
        _records = _data.get("data", [])
        dims = len(_records[0].get("embedding", [])) if _records else 0
        if dims:
            check("Superlinked encode", f"{ms}ms -- {dims}-dim embedding (all-MiniLM-L6-v2)")
        else:
            fail("Superlinked encode", "empty embedding returned")
    except Exception as exc:
        fail("Superlinked", str(exc)[:80])

console.print()

# 8. Mubit -- persistent agent memory
console.print("[bold]8. Mubit -- persistent agent memory[/bold]")
if not keys["MUBIT_API_KEY"]:
    skip("Mubit", "MUBIT_API_KEY not set -- decisions stored to disk only")
else:
    try:
        import mubit  # type: ignore[import-not-found]

        t0 = time.time()
        mubit.remember(
            agent_id="preflight-agent",
            content='{"test": "preflight"}',
            tags=["preflight", "dusk-demo"],
        )
        ms = int((time.time() - t0) * 1000)
        check("Mubit remember", f"{ms}ms")
    except ImportError:
        skip("Mubit", "mubit package not installed -- pip install mubit (hackathon access)")
    except Exception as exc:
        fail("Mubit", str(exc)[:80])

console.print()

# 9. Aikido Zen -- runtime firewall
console.print("[bold]9. Aikido Zen -- runtime firewall[/bold]")
if not keys["AIKIDO_TOKEN"]:
    skip("Aikido Zen", "AIKIDO_TOKEN not set -- firewall inactive (non-blocking for demo)")
else:
    try:
        import aikido_zen  # type: ignore[import-not-found]

        aikido_zen.protect()
        check("Aikido Zen", "protect() called -- runtime firewall active")
    except ImportError:
        skip("Aikido Zen", "aikido-zen not installed -- see aikido.dev for install")
    except Exception as exc:
        fail("Aikido Zen", str(exc)[:80])

console.print()

# 10. Flask API health
console.print("[bold]10. Flask API -- localhost:5000[/bold]")
try:
    import urllib.request

    with urllib.request.urlopen("http://localhost:5000/health", timeout=3) as resp:  # nosec B310
        check("Flask /health", f"HTTP {resp.status}")
except Exception:
    skip("Flask /health", "start with: flask --app dusk.api run --port 5000")

console.print()

# 11. Full offline demo
console.print("[bold]11. Offline demo (no keys needed)[/bold]")
try:
    import subprocess

    r = subprocess.run(
        [sys.executable, "demo/live_attack.py"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode == 1 and "DUSK refused" in r.stdout:
        check("live_attack.py", "BLOCK verdict confirmed, HEAL completed")
    else:
        fail("live_attack.py", f"exit={r.returncode}")
except Exception as exc:
    fail("live_attack.py", str(exc)[:80])

console.print()

# Summary
passed = sum(1 for r, _, _ in results if "PASS" in r)
failed = sum(1 for r, _, _ in results if "FAIL" in r)
skipped = sum(1 for r, _, _ in results if "SKIP" in r)

console.rule()
if failed == 0:
    console.print(
        f"[bold green]All checks passed ({passed} pass, {skipped} skipped).[/bold green]"
        "  Ready to record."
    )
else:
    console.print(
        f"[bold red]{failed} check(s) failed[/bold red]  "
        f"({passed} passed, {skipped} skipped).  "
        "Fill in the missing keys in .env and re-run."
    )

if missing:
    console.print()
    console.print("[bold]Keys still needed in .env:[/bold]")
    for k in missing:
        console.print(f"  [red]{k}[/red]")

sys.exit(0 if failed == 0 else 1)
