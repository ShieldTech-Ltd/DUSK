# Dusk Threat Model

Dusk detects the behaviours a hijacked or poisoned AI agent exhibits when it
turns the network's own automation against it. Each detection below maps to a
MITRE ATT&CK technique and a kill-chain stage. This document is intended for
submission to OWASP as part of the agentic-network threat catalogue.

## Sweep

- **MITRE technique:** T1046, Network Service Discovery
- **Kill-chain stage:** Reconnaissance

A compromised agent enumerates a network segment by contacting many
destinations in a short window. Unlike a human operator, the agent moves at a
fixed machine cadence, producing inter-packet timing that is far too regular to
be organic. Dusk flags a single source that touches a high number of unique
destinations within a sliding window when the timing's standard deviation is
suspiciously low.

Attack example: TODO

## Boundary

- **MITRE technique:** T1590, Gather Victim Network Information
- **Kill-chain stage:** Reconnaissance

The agent probes a single destination across many ports in a short window, mapping which services are exposed on a target host before attempting an
exploit. Dusk groups packets by ``(src_ip, dst_ip)`` pair, slides a window
across the pair's traffic, and flags any pair whose unique destination-port
count exceeds the configured threshold.

Attack example: TODO

## Telemetry Silence

- **MITRE technique:** T1562.001, Impair Defenses: Disable or Modify Tools
- **Kill-chain stage:** Defense Evasion

An agent that normally emits a steady baseline of flows suddenly goes quiet.
The absence of expected telemetry is itself a signal: the attacker has likely
disabled logging or monitoring to operate unseen. Dusk treats a sharp,
unexplained drop in an agent's expected flows as a potential evasion event.

Attack example: TODO

## Lateral Movement

- **MITRE technique:** T1210, Exploitation of Remote Services
- **Kill-chain stage:** LateralMovement

The agent reaches east-west into peers it has never communicated with,
expanding a single foothold toward network-wide compromise. Dusk watches for
new cross-segment connections from a host whose baseline contains no such
traffic, especially when they follow a recent reconnaissance event.

Attack example: TODO
