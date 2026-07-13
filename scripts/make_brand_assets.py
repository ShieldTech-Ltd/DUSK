#!/usr/bin/env python3
# ruff: noqa: E501
"""Generate the DUSK README hero and compact workflow strip."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
SOURCE_ARCH = ROOT / "examples" / "agent-action-monitor" / "docs" / "architecture.svg"


def _logo_uri() -> str:
    match = re.search(r'href="(data:image/png;base64,[^"]+)"', SOURCE_ARCH.read_text())
    if match is None:
        raise RuntimeError("embedded DUSK logo not found in architecture.svg")
    return match.group(1)


def hero() -> str:
    logo = _logo_uri()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="390" viewBox="0 0 1200 390" role="img" aria-labelledby="title desc">
<title id="title">DUSK behavioral security for AI agents</title><desc id="desc">DUSK evaluates a proposed agent action, explains behavioral risk, and prevents anomalous actions from reaching infrastructure.</desc>
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0 10 5 0 10Z" fill="#111827"/></marker><filter id="sh" x="-15%" y="-15%" width="130%" height="140%"><feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#111827" flood-opacity=".08"/></filter><style>text{{font-family:Inter,Arial,sans-serif;fill:#111827}}.k{{font-size:11px;font-weight:800;letter-spacing:1.5px}}.b{{font-size:13px}}.s{{font-size:11px;fill:#667085}}.box{{fill:#fff;stroke:#d8dee8;stroke-width:1.4}}.path{{fill:none;stroke:#111827;stroke-width:2;stroke-dasharray:7 6;marker-end:url(#a);animation:m 1.4s linear infinite}}@keyframes m{{to{{stroke-dashoffset:-26}}}}@keyframes p{{50%{{opacity:.3}}}}.pulse{{animation:p 1.8s ease-in-out infinite}}</style></defs>
<rect width="1200" height="390" rx="24" fill="#f7f9fb"/><rect x="0" y="0" width="12" height="390" rx="6" fill="#111827"/>
<image href="{logo}" x="38" y="35" width="250" height="81" preserveAspectRatio="xMinYMid meet"/>
<text x="42" y="161" class="k">BEHAVIOURAL AI SECURITY FOR AGENTIC SYSTEMS</text>
<text x="42" y="210" font-size="38" font-weight="880">Security for what</text><text x="42" y="255" font-size="38" font-weight="880">AI agents do next.</text>
<text x="42" y="294" class="b" fill="#475467">Detect abnormal actions before they become infrastructure impact.</text>
<rect x="42" y="324" width="208" height="40" rx="20" fill="#111827"/><text x="146" y="349" text-anchor="middle" class="k" style="fill:#fff">OPEN SOURCE / APACHE 2.0</text>

<rect x="605" y="44" width="548" height="302" rx="20" class="box" filter="url(#sh)"/>
<text x="635" y="78" class="k">ACTION JOURNEY</text><text x="1124" y="78" text-anchor="end" class="s">decision before execution</text>
<rect x="635" y="108" width="126" height="84" rx="13" fill="#f8fafc" stroke="#d8dee8"/><text x="698" y="138" text-anchor="middle" class="k">AI AGENT</text><text x="698" y="166" text-anchor="middle" class="b">proposes action</text>
<rect x="820" y="98" width="164" height="104" rx="15" fill="#fff" stroke="#111827" stroke-width="1.7"/><text x="902" y="130" text-anchor="middle" class="k">DUSK GATE</text><text x="902" y="157" text-anchor="middle" class="b">baseline + SIE</text><text x="902" y="180" text-anchor="middle" class="s">score 0.80</text>
<rect x="1044" y="108" width="80" height="84" rx="13" fill="#fff8f7" stroke="#e9b7b1"/><text x="1084" y="140" text-anchor="middle" class="k" fill="#a52d2d">TARGET</text><text x="1084" y="166" text-anchor="middle" class="s">protected</text>
<path d="M761 150H814" class="path"/><circle cx="787" cy="150" r="5" fill="#111827" class="pulse"/><path d="M984 150H1031" fill="none" stroke="#c73b3b" stroke-width="2" stroke-dasharray="5 4"/><path d="m1010 137 18 26m0-26-18 26" stroke="#c73b3b" stroke-width="3" stroke-linecap="round"/>
<rect x="635" y="232" width="489" height="84" rx="13" fill="#fff" stroke="#d8dee8"/><text x="657" y="258" class="k">EXPLAINABLE VERDICT</text><text x="657" y="290" font-size="22" font-weight="850" fill="#c73b3b">WOULD-BLOCK</text><text x="1102" y="270" text-anchor="end" class="s">new target / privileged value</text><text x="1102" y="293" text-anchor="end" class="s">MITRE ATT&amp;CK + ATLAS mapped</text>
</svg>'''


def workflow() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="190" viewBox="0 0 1200 190" role="img" aria-labelledby="title desc">
<title id="title">How DUSK works in five steps</title><desc id="desc">Agent, structured action, behavioral analysis with SIE, explainable verdict, and conditional target execution.</desc>
<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 10 5 0 10Z" fill="#98a2b3"/></marker><style>text{font-family:Inter,Arial,sans-serif;fill:#111827}.k{font-size:11px;font-weight:800;letter-spacing:1.2px}.s{font-size:10px;fill:#667085}.n{fill:#fff;stroke:#d8dee8;stroke-width:1.3}.f{fill:none;stroke:#98a2b3;stroke-width:1.8;stroke-dasharray:6 5;marker-end:url(#a);animation:m 1.4s linear infinite}@keyframes m{to{stroke-dashoffset:-22}}</style></defs>
<rect width="1200" height="190" rx="18" fill="#fff" stroke="#d8dee8"/><text x="30" y="34" class="k">HOW DUSK WORKS</text><text x="1170" y="34" text-anchor="end" class="s">inline behavioral control for proposed agent actions</text>
<path d="M210 106H263M430 106H483M650 106H703M870 106H923" class="f"/>
<g><circle cx="55" cy="106" r="19" fill="#111827"/><text x="55" y="111" text-anchor="middle" style="fill:#fff;font-size:12px;font-weight:800">1</text><rect x="82" y="70" width="128" height="72" rx="12" class="n"/><text x="146" y="101" text-anchor="middle" class="k">AGENT</text><text x="146" y="122" text-anchor="middle" class="s">proposes a tool action</text></g>
<g><circle cx="275" cy="106" r="19" fill="#111827"/><text x="275" y="111" text-anchor="middle" style="fill:#fff;font-size:12px;font-weight:800">2</text><rect x="302" y="70" width="128" height="72" rx="12" class="n"/><text x="366" y="101" text-anchor="middle" class="k">STRUCTURE</text><text x="366" y="122" text-anchor="middle" class="s">normalize AgentAction</text></g>
<g><circle cx="495" cy="106" r="19" fill="#111827"/><text x="495" y="111" text-anchor="middle" style="fill:#fff;font-size:12px;font-weight:800">3</text><rect x="522" y="64" width="128" height="84" rx="12" fill="#f8fafc" stroke="#111827" stroke-width="1.5"/><text x="586" y="96" text-anchor="middle" class="k">ANALYSE</text><text x="586" y="117" text-anchor="middle" class="s">baseline + SIE signals</text><text x="586" y="134" text-anchor="middle" class="s">risk + evidence</text></g>
<g><circle cx="715" cy="106" r="19" fill="#111827"/><text x="715" y="111" text-anchor="middle" style="fill:#fff;font-size:12px;font-weight:800">4</text><rect x="742" y="70" width="128" height="72" rx="12" class="n"/><text x="806" y="101" text-anchor="middle" class="k">VERDICT</text><text x="806" y="122" text-anchor="middle" class="s">allow / flag / block</text></g>
<g><circle cx="935" cy="106" r="19" fill="#16834b"/><text x="935" y="111" text-anchor="middle" style="fill:#fff;font-size:12px;font-weight:800">5</text><rect x="962" y="70" width="208" height="72" rx="12" fill="#f5fbf7" stroke="#9bcfaf"/><text x="1066" y="99" text-anchor="middle" class="k" style="fill:#12693d">EXECUTE CONDITIONALLY</text><text x="1066" y="121" text-anchor="middle" class="s">target called only when policy permits</text></g>
</svg>"""


def main() -> None:
    assets = {"dusk-hero-banner.svg": hero(), "dusk-workflow-strip.svg": workflow()}
    for name, content in assets.items():
        out = DOCS / name
        out.write_text(content, encoding="utf-8")
        print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
