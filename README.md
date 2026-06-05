# Dusk

Networks are filling with AI agents that operate autonomously — changing routing,
modifying firewall rules, reconfiguring infrastructure at machine speed. When one
of those agents is hijacked or poisoned, the attacker doesn't breach the network.
They command the network's own brain to breach it for them, through actions that
look completely legitimate.

Dusk watches how agents move through the network. It detects the machine-paced,
systematic patterns that signal an attack in progress, and stops it before it lands.

> Status: v0.1 — sweep detection active. Boundary, telemetry, and lateral movement in progress.

## What it detects

| Detection | Behaviour | MITRE | Status |
|---|---|---|---|
| Sweep | Machine-paced scan of network segments | T1046 | v0.1 |
| Boundary probe | Repeated probing of segment boundaries | T1590 | coming |
| Telemetry silence | Agent suddenly stops expected flows | T1562.001 | coming |
| Lateral movement | East-west movement across segments | T1210 | coming |

## Quickstart

```bash
pip install dusk-security

dusk scan --file capture.pcap
dusk scan --file capture.pcap --json
```

`dusk scan` exits `0` when traffic is **CLEAR** and `1` when it raises an
**ALERT**, so it drops straight into CI and automation.

## How it works

Dusk is built from four composable layers:

- **Sensors** (`dusk.sensor`) turn a traffic source — a pcap today, live
  interfaces and Zeek logs next — into a uniform stream of packet records.
- **Detections** (`dusk.detections`) each look for one behavioural attack
  pattern and return a verdict with a MITRE technique, kill-chain stage, and
  confidence.
- **Engine** (`dusk.core`) runs every detection, reaches an overall verdict,
  and predicts the attacker's next kill-chain stage.
- **Responders** (`dusk.respond`) act on findings — alerting today, active
  isolation next.

## Try it locally

Generate the bundled lab fixtures and scan them:

```bash
python lab/scenarios/attack_sweep.py     # a hijacked agent sweeping a segment
python lab/scenarios/normal_traffic.py   # benign, human-paced browsing

dusk scan --file tests/fixtures/attack_sweep.pcap     # -> ALERT
dusk scan --file tests/fixtures/normal_traffic.pcap   # -> CLEAR
```

## Development

```bash
pip install -e ".[dev]"
pytest -v
```

See [`docs/threat-model.md`](docs/threat-model.md) for the threat catalogue.

## License

Apache-2.0.
