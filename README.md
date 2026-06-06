# Dusk

Networks are filling with AI agents that operate autonomously — changing routing,
modifying firewall rules, reconfiguring infrastructure at machine speed. When one
of those agents is hijacked or poisoned, the attacker doesn't breach the network.
They command the network's own brain to breach it for them, through actions that
look completely legitimate.

Dusk watches how agents move through the network. It detects the machine-paced,
systematic patterns that signal an attack in progress, and stops it before it lands.

> Status: v0.1 — sweep and boundary detections active. Telemetry and lateral movement in progress.

## What it detects

| Detection | Behaviour | MITRE | Status |
|---|---|---|---|
| Sweep | Machine-paced scan of network segments | T1046 | v0.1 |
| Boundary probe | Port scan against a single destination | T1590 | v0.1 |
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

## Configuration

All thresholds are configurable. Copy `dusk.yaml.example` to `dusk.yaml` in your
working directory, or override any value with a `DUSK_*` environment variable
(e.g. `DUSK_SWEEP_THRESHOLD=20`).

## Try it locally

Generate the bundled lab fixtures and scan them:

```bash
python lab/scenarios/attack_sweep.py     # a hijacked agent sweeping a segment
python lab/scenarios/normal_traffic.py   # benign, human-paced browsing
python lab/scenarios/port_scan.py        # a port scan against one host

dusk scan --file tests/fixtures/attack_sweep.pcap     # -> ALERT (sweep)
dusk scan --file tests/fixtures/port_scan.pcap        # -> ALERT (boundary)
dusk scan --file tests/fixtures/normal_traffic.pcap   # -> CLEAR
```

Add `--verbose` to any `dusk` command for DEBUG logging on stderr.

## Development

```bash
pip install -e ".[dev]"
ruff check src/ tests/
mypy src/dusk/
bandit -r src/ -ll
pytest --cov=src/dusk
```

Pre-commit hooks are configured in `.pre-commit-config.yaml`:

```bash
pre-commit install
```

See [`docs/threat-model.md`](docs/threat-model.md) for the threat catalogue and
[`SECURITY.md`](SECURITY.md) for vulnerability reporting.

## License

Apache-2.0.
