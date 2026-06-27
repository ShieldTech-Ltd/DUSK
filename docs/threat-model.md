# DUSK Threat Model

This document maps each detection in DUSK to the adversarial techniques it is
designed to catch, using MITRE ATT&CK for network-layer techniques and MITRE
ATLAS for AI-specific attacks. It is written to a standard suitable for OWASP
submission.

## Threat landscape

Autonomous AI agents operating on network infrastructure represent a new attack
surface. A compromised or prompt-injected agent acts with the full privileges of
the legitimate system it replaced. Traditional perimeter controls see only
authorised traffic, because the traffic is authorised: it comes from the agent
that is supposed to be making changes. DUSK detects by behaviour, not identity.
The signal is not who is acting, but how: machine-paced, systematic, and
structured in ways human operators are not.

## Detection 1: Network Sweep

| Field | Value |
|---|---|
| Detection name | sweep |
| MITRE ATT&CK | T1046, Network Service Discovery |
| MITRE ATLAS | AML.T0051, LLM Prompt Injection |
| Kill-chain stage | Reconnaissance |
| Confidence scoring | Scaled by unique destination count above threshold |

**What it catches.** A hijacked or prompt-injected agent performs a systematic
scan across a network segment, probing many unique destinations in a short time
window at machine-regular intervals. Human-paced browsing is irregular and
low-volume. An automated sweep is fast, regular, and hits many hosts.

**Detection logic.** Groups packets by source IP. Within a sliding 10-second
window, counts unique destination IPs. If the count exceeds the configured
threshold and the inter-packet timing standard deviation is below 50ms
(machine-regular), the detection fires. Confidence scales with how far above the
threshold the count is.

**Attack example.** A network-operations agent is prompt-injected to enumerate
the cardholder data segment (10.0.99.0/24) before a lateral movement attempt. It
sends SYN packets to 25 hosts in 2.5 seconds at 100ms intervals. Dusk fires on
the 16th unique destination within the 10-second window.

**Kill-chain prediction.** After Reconnaissance, expect LateralMovement. Watch
for east-west connections from the scanning host into segments it has not
previously reached.

## Detection 2: Boundary Probe

| Field | Value |
|---|---|
| Detection name | boundary |
| MITRE ATT&CK | T1590, Gather Victim Network Information |
| Kill-chain stage | Reconnaissance |
| Confidence scoring | Scaled by unique port count above threshold |

**What it catches.** An agent probes a single destination host across many ports
within a time window, mapping which services are available before an
exploitation attempt.

**Detection logic.** Groups packets by source IP and destination IP pair. Within
a sliding 30-second window, counts unique destination ports per pair. If the
count exceeds the configured threshold, the detection fires.

**Attack example.** A hijacked agent targets 10.0.99.5, a database host,
scanning ports 20 through 40 within 5 seconds to identify open services. Dusk
fires when the 11th unique port is probed against the same destination.

**Kill-chain prediction.** After Reconnaissance, expect exploitation of a
discovered open service. Watch for unusual connection establishment on the
identified ports.

## Detection 3: Telemetry Silence (v0.2)

| Field | Value |
|---|---|
| Detection name | telemetry |
| MITRE ATT&CK | T1562.001, Impair Defenses: Disable or Modify Tools |
| Kill-chain stage | Defence Evasion |

**What it catches.** A compromised agent disables logging, SNMP polling, or
NetFlow export from a device it manages, creating a blind spot before executing
the primary attack.

**Detection logic.** Establishes a baseline of expected periodic flows (SNMP,
syslog, NetFlow) from each managed device. Fires when a previously regular flow
stops without a corresponding authorised maintenance window.

**Attack example.** A network management agent is instructed to suppress syslog
forwarding from the core switch before a configuration change that would
otherwise generate alerts.

## Detection 4: Lateral Movement (v0.2)

| Field | Value |
|---|---|
| Detection name | lateral |
| MITRE ATT&CK | T1210, Exploitation of Remote Services |
| Kill-chain stage | Lateral Movement |

**What it catches.** An agent establishes connections from a compromised host
into network segments it has never previously accessed, indicating
post-reconnaissance lateral movement.

**Detection logic.** Maintains a per-source baseline of destination subnets seen
during the learning period. Fires when a source makes a first-ever connection
into a new subnet within a short time of a sweep or boundary detection from the
same source.

**Attack example.** Following a sweep of the cardholder segment, the compromised
agent initiates an SSH connection to 10.0.99.10, a host it has never previously
contacted.

## Mapping to OWASP Top 10 for Agentic Applications

| OWASP risk | Dusk detection |
|---|---|
| Unbounded agent actions | Sweep, Boundary |
| Prompt injection leading to malicious tool use | Sweep |
| Excessive agent permissions | Lateral movement |
| Agent communication interception | Telemetry silence |
