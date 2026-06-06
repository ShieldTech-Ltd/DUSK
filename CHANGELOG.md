# Changelog

All notable changes to DUSK are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] — 2026-06-05

### Added
- Sweep detection: machine-paced network scan identification (T1046)
- Boundary detection: port scan identification (T1590)
- pcap sensor via Scapy
- CLI: dusk scan --file [--json] [--verbose]
- Configuration system: dusk.yaml + DUSK_* environment variables
- Structured logging throughout
- Kill chain stage prediction
- Alert output: Rich terminal panel + dusk-alerts.json
- CI: lint, typecheck, security scan, test with coverage gate
- OWASP-oriented threat model in docs/threat-model.md
