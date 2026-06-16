# Changelog

All notable changes to DUSK are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- v1.1 agent action ingest layer: the controller-agnostic AgentAction event
  (timezone-aware timestamp, normalised action_type, target, before/after
  change, source, raw_ref) with strict validation and to_dict/from_dict
  round-tripping; a SourceAdapter base with AdapterError; Azure activity-log
  and generic adapters; a normaliser registry keyed by source name;
  ingest_file(path, source) reading a JSON list of records and skipping
  malformed ones; the `dusk actions --file --source [--json]` CLI command; a
  lab generator for the action fixtures; and docs/action-schema.md.
- Professional README with status badges, a CLI demo, a mermaid architecture
  diagram, a configuration reference, and a roadmap.
- README reference sections: table of contents, how it works, usage, JSON output,
  exit codes, use in CI, alerts, install from source, project layout, and
  references.
- Full threat model in docs/threat-model.md with MITRE ATT&CK, MITRE ATLAS, and
  OWASP Top 10 for Agentic Applications mappings.
- CONTRIBUTING.md documenting the branch model, issue-first rule, local checks,
  and how to add a detection.

### Changed
- Plain-text style across all docs, issue templates, alert panel, and code
  docstrings. Em dashes, en dashes, navigation arrows, and decorative emojis
  removed. No functional changes.
- Test runs force PYTHONIOENCODING=utf-8 (via pytest-env) so console capture
  cannot fall back to a platform default such as Windows cp1252.

## [0.1.0], 2026-06-05

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
