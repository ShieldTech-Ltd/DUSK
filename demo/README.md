# DUSK interactive demo

`index.html` is a standalone, self-contained interactive walkthrough of the DUSK
concept: the problem it addresses, where it sits in the enterprise stack, and the
four-layer inline-gate architecture.

## How to view it

GitHub does not render this page in the repository view, because it uses
JavaScript and inline interactivity that GitHub strips for safety. To see it,
either:

- download `index.html` and open it in a web browser, or
- host the `demo/` directory on any static web host or GitHub Pages.

The file has no external dependencies; everything (styles, animations, and the
click interactions) is inline.

## What it is, and what it is not

This demo is illustrative. It communicates the vision and positioning, not the
current shipped behaviour.

- The depicted inline gate (ingest, baseline, analyse, predict, verdict) shows
  the v1 roadmap direction. Today DUSK ships the v0.1 behavioural network
  detections (sweep and boundary over packet captures) and the v1.1 agent action
  ingest layer. The baseline, analysis, and blocking stages are in progress. See
  the project [README](../README.md) and [roadmap](../README.md#roadmap) for what
  is shipped versus planned.
- The vendor cards (AWS Bedrock, Microsoft Sentinel, Cisco, Oracle SQL Firewall,
  Google DeepMind) describe how DUSK is positioned relative to each layer. They
  are short illustrative summaries, not authoritative statements about those
  products.
- The Oracle 26ai layer reflects integration directions, not shipped features.

For the accurate, current capability description, always defer to the main
[README](../README.md) and [docs/](../docs/).
