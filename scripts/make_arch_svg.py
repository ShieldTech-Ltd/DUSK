#!/usr/bin/env python3
"""Generate the animated three-phase architecture SVG for the DUSK README.

The animation tells a complete story in one loop:

Phase 1 -- BEFORE DUSK (0-7s)
  A network agent operates normally. No behavioral gate exists. Actions flow
  freely from web content through the agent to the controller and the network.

Phase 2 -- ATTACK, NO PROTECTION (8-14s)
  A threat actor poisons a web page. The agent reads it, gets hijacked, and
  fires an anomalous action. With no gate active, the action flows straight
  through to the controller and the network -- the network is BREACHED.

Phase 3 -- DUSK DEPLOYED (15-22s)
  The same attack hits again, but DUSK is now active. The three gate layers
  (Baseline, Analyse, Verdict) light up in sequence. The anomaly score rises
  to 0.80, the action is refused with WOULD-BLOCK, and the network stays
  PROTECTED.

Regenerate with::

    python scripts/make_arch_svg.py
"""

from __future__ import annotations

from pathlib import Path

BG_TOP = "#0b1220"
BG_BOT = "#070b14"
CARD_BD = "#1e2d42"
TITLE_BG = "#0f1a2b"
FG = "#d0d8e4"
DIM = "#6e7d94"
CYAN = "#56d4dd"
GREEN = "#3fb950"
RED = "#f85149"
AMBER = "#e3b341"
NODE_BG = "#0e1827"

FONT = (
    "ui-monospace,'SF Mono','Cascadia Code','Cascadia Mono',"
    "Menlo,Consolas,'DejaVu Sans Mono',monospace"
)

W, H = 960, 500
M = 8
TITLE_H = 44
STRIP_H = 22
BODY_Y = M + TITLE_H + STRIP_H
FY = BODY_Y + (H - M - BODY_Y) // 2

LOOP = 24.0

WEB = (128, FY, 72, 90)
AGT = (322, FY, 70, 68)
DSK = (542, FY, 116, 108)
CTL = (762, FY, 70, 68)
NET = (906, FY, 48, 90)

WEB_R = WEB[0] + WEB[2]
AGT_L = AGT[0] - AGT[2]
AGT_R = AGT[0] + AGT[2]
DSK_L = DSK[0] - DSK[2]
DSK_R = DSK[0] + DSK[2]
CTL_L = CTL[0] - CTL[2]
CTL_R = CTL[0] + CTL[2]
NET_L = NET[0] - NET[2]

CX = W // 2

SUB_W = 200
SUB_H = 26
SUB_X = DSK[0] - SUB_W // 2
DSK_TOP = DSK[1] - DSK[3]
SUB_Y1 = DSK_TOP + 36
SUB_Y2 = SUB_Y1 + SUB_H + 8
SUB_Y3 = SUB_Y2 + SUB_H + 8
SUB_BOT = SUB_Y3 + SUB_H

P1_ON, P1_OFF = 0.0, 7.0
P2_ON, P2_OFF = 8.5, 14.5
P3_ON, P3_OFF = 15.5, 22.5


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _pct(t: float) -> str:
    return f"{t / LOOP * 100:.1f}%"


def _phase_kf(name: str, on: float, off: float) -> str:
    fade = 1.2
    return (
        f"@keyframes {name}{{"
        f"{_pct(max(0.0, on - 0.5))}{{opacity:0}}"
        f"{_pct(on)}{{opacity:1}}"
        f"{_pct(off)}{{opacity:1}}"
        f"{_pct(off + fade)}{{opacity:0}}"
        f"{_pct(LOOP)}{{opacity:0}}"
        "}}"
    )


def _node(cx: int, cy: int, hw: int, hh: int,
          name: str, sub: str,
          fill: str, stroke: str,
          name_col: str = FG,
          cls: str = "") -> str:
    x, y = cx - hw, cy - hh
    ca = f' class="{cls}"' if cls else ""
    return (
        f'<rect{ca} x="{x}" y="{y}" width="{hw * 2}" height="{hh * 2}" '
        f'rx="10" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
        f'<text x="{cx}" y="{y + 20}" text-anchor="middle" '
        f'fill="{name_col}" font-weight="700" font-size="13">{_esc(name)}</text>'
        f'<text x="{cx}" y="{y + 35}" text-anchor="middle" '
        f'fill="{DIM}" font-size="10">{_esc(sub)}</text>'
    )


def _pkt(pid: str, dur: float, begin: float, color: str, r: int = 5) -> str:
    return (
        f'<circle r="{r}" fill="{color}">'
        f'<animateMotion dur="{dur:.2f}s" begin="{begin:.2f}s" '
        f'repeatCount="indefinite" calcMode="spline" '
        f'keyTimes="0;1" keySplines="0.42 0 0.58 1">'
        f'<mpath href="#p-{pid}"/></animateMotion></circle>'
    )


def _line(x1: int, x2: int, color: str, cls: str = "") -> str:
    ca = f' class="{cls}"' if cls else ""
    return (
        f'<line{ca} x1="{x1}" y1="{FY}" x2="{x2}" y2="{FY}" '
        f'stroke="{color}" stroke-width="1.5" stroke-dasharray="8 5"/>'
    )


def _sub(y: int, label: str, cls: str = "") -> str:
    ca = f' class="{cls}"' if cls else ""
    return (
        f'<rect{ca} x="{SUB_X}" y="{y}" width="{SUB_W}" height="{SUB_H}" '
        f'rx="5" fill="#0e1d2e" stroke="{CYAN}" stroke-width="1.2"/>'
        f'<text x="{DSK[0]}" y="{y + 18}" text-anchor="middle" '
        f'fill="{FG}" font-size="11" font-weight="600">{_esc(label)}</text>'
    )


def build() -> str:  # noqa: PLR0915
    dsk_x, dsk_y = DSK[0] - DSK[2], DSK[1] - DSK[3]
    dsk_w, dsk_h = DSK[2] * 2, DSK[3] * 2
    score_track_w = dsk_w - 32
    score_x = dsk_x + 16
    score_y = SUB_BOT + 10

    paths = "\n".join([
        f'<path id="p-wa" d="M{WEB_R},{FY} L{AGT_L},{FY}" fill="none"/>',
        f'<path id="p-ad" d="M{AGT_R},{FY} L{DSK_L},{FY}" fill="none"/>',
        f'<path id="p-dc" d="M{DSK_R},{FY} L{CTL_L},{FY}" fill="none"/>',
        f'<path id="p-cn" d="M{CTL_R},{FY} L{NET_L},{FY}" fill="none"/>',
        (f'<path id="p-ag" d="M{AGT_R},{FY} '
         f'C{AGT_R + 35},{FY} {DSK_L},{DSK[1]} {DSK[0]},{DSK[1]}" fill="none"/>'),
        f'<path id="p-ac" d="M{AGT_R},{FY} L{CTL_L},{FY}" fill="none"/>',
    ])

    kf_p1 = _phase_kf("p1v", P1_ON, P1_OFF)
    kf_p2 = _phase_kf("p2v", P2_ON, P2_OFF)
    kf_p3 = _phase_kf("p3v", P3_ON, P3_OFF)

    kf_flow = "@keyframes fl{from{stroke-dashoffset:26}to{stroke-dashoffset:0}}"

    kf_agt = (
        f"@keyframes agt-col{{"
        f"{_pct(0)}{{stroke:{GREEN};fill:#0d2218}}"
        f"{_pct(P1_OFF)}{{stroke:{GREEN};fill:#0d2218}}"
        f"{_pct(P2_ON)}{{stroke:{DIM};fill:{NODE_BG}}}"
        f"{_pct(P2_ON + 2)}{{stroke:{RED};fill:#1e0b0b}}"
        f"{_pct(P2_OFF)}{{stroke:{RED};fill:#1e0b0b}}"
        f"{_pct(P3_ON)}{{stroke:{DIM};fill:{NODE_BG}}}"
        f"{_pct(P3_ON + 2)}{{stroke:{RED};fill:#1e0b0b}}"
        f"{_pct(P3_OFF)}{{stroke:{RED};fill:#1e0b0b}}"
        f"{_pct(LOOP)}{{stroke:{GREEN};fill:#0d2218}}}}",
    )

    kf_net = (
        f"@keyframes net-col{{"
        f"{_pct(0)}{{stroke:{GREEN};fill:#0c1d0d}}"
        f"{_pct(P2_ON + 3)}{{stroke:{GREEN};fill:#0c1d0d}}"
        f"{_pct(P2_ON + 4)}{{stroke:{RED};fill:#200a0a}}"
        f"{_pct(P2_OFF)}{{stroke:{RED};fill:#200a0a}}"
        f"{_pct(P3_ON)}{{stroke:{GREEN};fill:#0c1d0d}}"
        f"{_pct(LOOP)}{{stroke:{GREEN};fill:#0c1d0d}}}}",
    )

    kf_ctl = (
        f"@keyframes ctl-col{{"
        f"{_pct(0)}{{stroke:{CARD_BD};fill:{NODE_BG}}}"
        f"{_pct(P2_ON + 3)}{{stroke:{CARD_BD};fill:{NODE_BG}}}"
        f"{_pct(P2_ON + 4)}{{stroke:{RED};fill:#1a0808}}"
        f"{_pct(P2_OFF)}{{stroke:{RED};fill:#1a0808}}"
        f"{_pct(P3_ON)}{{stroke:{CARD_BD};fill:{NODE_BG}}}"
        f"{_pct(LOOP)}{{stroke:{CARD_BD};fill:{NODE_BG}}}"
        "}}",
    )

    kf_gate = (
        f"@keyframes gate-a{{"
        f"{_pct(0)}{{stroke:{DIM};stroke-opacity:0.2;fill-opacity:0.25}}"
        f"{_pct(P2_OFF + 1)}{{stroke:{DIM};stroke-opacity:0.2;fill-opacity:0.25}}"
        f"{_pct(P3_ON)}{{stroke:{CYAN};stroke-opacity:1;fill-opacity:1}}"
        f"{_pct(P3_ON + 3)}{{stroke:{RED};stroke-opacity:1;fill-opacity:1}}"
        f"{_pct(P3_OFF)}{{stroke:{RED};stroke-opacity:1;fill-opacity:1}}"
        f"{_pct(P3_OFF + 1.2)}{{stroke:{DIM};stroke-opacity:0.2;fill-opacity:0.25}}"
        f"{_pct(LOOP)}{{stroke:{DIM};stroke-opacity:0.2;fill-opacity:0.25}}}}",
    )

    def _sub_kf(name: str, delay: float, col: str) -> str:
        dark = "#180e0e" if col == RED else "#0a1e1e"
        return (
            f"@keyframes {name}{{"
            f"{_pct(0)}{{stroke:{CYAN};fill:#0e1d2e;opacity:0.3}}"
            f"{_pct(P3_ON - 0.5)}{{stroke:{CYAN};fill:#0e1d2e;opacity:0.3}}"
            f"{_pct(P3_ON)}{{stroke:{CYAN};fill:#0e1d2e;opacity:1}}"
            f"{_pct(P3_ON + delay)}{{stroke:{CYAN};fill:#0e1d2e;opacity:1}}"
            f"{_pct(P3_ON + delay + 0.5)}{{stroke:{col};fill:{dark};opacity:1}}"
            f"{_pct(P3_OFF)}{{stroke:{col};fill:{dark};opacity:1}}"
            f"{_pct(P3_OFF + 1)}{{stroke:{CYAN};fill:#0e1d2e;opacity:0.3}}"
            f"{_pct(LOOP)}{{stroke:{CYAN};fill:#0e1d2e;opacity:0.3}}}}"
        )

    kf_sub1 = _sub_kf("sb1", 1.2, CYAN)
    kf_sub2 = _sub_kf("sb2", 2.4, AMBER)
    kf_sub3 = _sub_kf("sb3", 3.6, RED)

    kf_score = (
        f"@keyframes sw{{"
        f"{_pct(0)}{{width:0}}"
        f"{_pct(P3_ON + 3.5)}{{width:0}}"
        f"{_pct(P3_ON + 7)}{{width:{score_track_w}px}}"
        f"{_pct(P3_OFF)}{{width:{score_track_w}px}}"
        f"{_pct(P3_OFF + 1)}{{width:0}}"
        f"{_pct(LOOP)}{{width:0}}}}"
    )

    utils = (
        "@keyframes live{0%,100%{opacity:1}50%{opacity:0.1}}"
        "@keyframes pls{0%,100%{opacity:1}50%{opacity:0.15}}"
    )

    css = " ".join([
        "text{white-space:pre}", utils,
        kf_p1, kf_p2, kf_p3, kf_flow,
        *kf_agt, *kf_net, *kf_ctl, *kf_gate,
        kf_sub1, kf_sub2, kf_sub3, kf_score,
        f".p1{{animation:p1v {LOOP}s infinite}}",
        f".p2{{animation:p2v {LOOP}s infinite}}",
        f".p3{{animation:p3v {LOOP}s infinite}}",
        ".live{animation:live 1.4s ease-in-out infinite}",
        ".pls{animation:pls 0.9s ease-in-out infinite}",
        f".agt-r{{stroke-width:2;animation:agt-col {LOOP}s infinite}}",
        f".net-r{{stroke-width:1.5;animation:net-col {LOOP}s infinite}}",
        f".ctl-r{{stroke-width:1.5;animation:ctl-col {LOOP}s infinite}}",
        f".gate-r{{stroke-width:2.5;animation:gate-a {LOOP}s infinite}}",
        f".sb1{{animation:sb1 {LOOP}s infinite}}",
        f".sb2{{animation:sb2 {LOOP}s infinite}}",
        f".sb3{{animation:sb3 {LOOP}s infinite}}",
        f".sf{{animation:sw {LOOP}s infinite}}",
        ".fl{stroke-dasharray:8 5;animation:fl 1.4s linear infinite}",
    ])

    chrome = (
        "<defs>"
        '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG_TOP}"/>'
        f'<stop offset="1" stop-color="{BG_BOT}"/>'
        "</linearGradient>"
        '<filter id="shadow" x="-12%" y="-12%" width="124%" height="124%">'
        '<feDropShadow dx="0" dy="10" stdDeviation="22" '
        'flood-color="#000000" flood-opacity="0.55"/>'
        "</filter>"
        "</defs>"
        '<g filter="url(#shadow)">'
        f'<rect x="{M}" y="{M}" width="{W - 2 * M}" height="{H - 2 * M}" '
        f'rx="14" fill="url(#bg)" stroke="{CARD_BD}"/>'
        "</g>"
        f'<path d="M{M} {M + 14} a14 14 0 0 1 14 -14 '
        f'h{W - 2 * M - 28} a14 14 0 0 1 14 14 '
        f'v{TITLE_H - 14} h-{W - 2 * M} z" fill="{TITLE_BG}"/>'
        f'<line x1="{M}" y1="{M + TITLE_H}" x2="{W - M}" y2="{M + TITLE_H}" '
        f'stroke="{CARD_BD}"/>'
        f'<circle cx="28" cy="{M + TITLE_H // 2}" r="6" fill="#ff5f56"/>'
        f'<circle cx="48" cy="{M + TITLE_H // 2}" r="6" fill="#ffbd2e"/>'
        f'<circle cx="68" cy="{M + TITLE_H // 2}" r="6" fill="#27c93f"/>'
        f'<text x="96" y="{M + 29}" fill="{FG}" font-weight="700" font-size="16">'
        f'DUSK</text>'
        f'<text x="142" y="{M + 29}" fill="{DIM}" font-size="12">'
        f'  behavioral gate for agentic networks</text>'
        f'<rect x="{M}" y="{M + TITLE_H}" width="{W - 2 * M}" '
        f'height="{STRIP_H}" fill="#080d1a"/>'
        f'<line x1="{M}" y1="{M + TITLE_H + STRIP_H}" '
        f'x2="{W - M}" y2="{M + TITLE_H + STRIP_H}" stroke="{CARD_BD}"/>'
    )

    tx, ty = 60, FY
    threat = (
        f'<circle cx="{tx}" cy="{ty - 28}" r="13" '
        f'fill="#160b0b" stroke="{RED}" stroke-width="1.5"/>'
        f'<path d="M{tx - 16},{ty + 2} '
        f'C{tx - 16},{ty - 14} {tx + 16},{ty - 14} {tx + 16},{ty + 2}" '
        f'fill="#160b0b" stroke="{RED}" stroke-width="1.5"/>'
        f'<text x="{tx}" y="{ty + 22}" text-anchor="middle" '
        f'fill="{RED}" font-size="10">Threat</text>'
    )

    web_node = _node(*WEB[:2], WEB[2], WEB[3], "Web Content", "external source",
                     NODE_BG, CYAN, CYAN)
    agt_node = (
        f'<rect class="agt-r" x="{AGT[0] - AGT[2]}" y="{AGT[1] - AGT[3]}" '
        f'width="{AGT[2] * 2}" height="{AGT[3] * 2}" rx="10"/>'
        f'<text x="{AGT[0]}" y="{AGT[1] - AGT[3] + 20}" text-anchor="middle" '
        f'fill="{FG}" font-weight="700" font-size="13">AI Agent</text>'
        f'<text x="{AGT[0]}" y="{AGT[1] - AGT[3] + 35}" text-anchor="middle" '
        f'fill="{DIM}" font-size="10">netops-agent</text>'
    )
    ctl_node = (
        f'<rect class="ctl-r" x="{CTL[0] - CTL[2]}" y="{CTL[1] - CTL[3]}" '
        f'width="{CTL[2] * 2}" height="{CTL[3] * 2}" rx="10"/>'
        f'<text x="{CTL[0]}" y="{CTL[1] - CTL[3] + 20}" text-anchor="middle" '
        f'fill="{FG}" font-weight="700" font-size="13">Controller</text>'
        f'<text x="{CTL[0]}" y="{CTL[1] - CTL[3] + 35}" text-anchor="middle" '
        f'fill="{DIM}" font-size="10">SDN control plane</text>'
    )
    net_node = (
        f'<rect class="net-r" x="{NET[0] - NET[2]}" y="{NET[1] - NET[3]}" '
        f'width="{NET[2] * 2}" height="{NET[3] * 2}" rx="10"/>'
        f'<text x="{NET[0]}" y="{NET[1] - NET[3] + 20}" text-anchor="middle" '
        f'fill="{GREEN}" font-weight="700" font-size="13">Network</text>'
        f'<text x="{NET[0]}" y="{NET[1] - NET[3] + 35}" text-anchor="middle" '
        f'fill="{DIM}" font-size="10">infrastructure</text>'
    )
    dsk_node = (
        f'<rect class="gate-r" x="{dsk_x}" y="{dsk_y}" '
        f'width="{dsk_w}" height="{dsk_h}" rx="12" fill="#0b1724"/>'
        f'<text x="{DSK[0]}" y="{dsk_y + 22}" text-anchor="middle" '
        f'fill="{CYAN}" font-weight="700" font-size="12" letter-spacing="2">'
        f'DUSK GATE</text>'
        + _sub(SUB_Y1, "Baseline  --  per-agent profile", "sb1")
        + _sub(SUB_Y2, "Analyse  --  anomaly score", "sb2")
        + _sub(SUB_Y3, "Verdict  --  ALLOW / BLOCK", "sb3")
    )

    base_lines = (
        _line(WEB_R, AGT_L, CARD_BD)
        + _line(AGT_R, DSK_L, CARD_BD)
        + _line(DSK_R, CTL_L, CARD_BD)
        + _line(CTL_R, NET_L, CARD_BD)
    )

    sy = M + TITLE_H + STRIP_H // 2 + 6
    web_bot = WEB[1] + WEB[3]
    agt_bot = AGT[1] + AGT[3]
    net_bot = NET[1] + NET[3]

    poison_badge = (
        f'<rect x="{WEB[0] - 62}" y="{web_bot - 52}" width="124" height="38" '
        f'rx="5" fill="#1f0a0a" stroke="{RED}" stroke-width="1"/>'
        f'<text x="{WEB[0]}" y="{web_bot - 34}" text-anchor="middle" '
        f'fill="{RED}" font-size="10" font-weight="700">POISONED POST</text>'
        f'<text x="{WEB[0]}" y="{web_bot - 20}" text-anchor="middle" '
        f'fill="{AMBER}" font-size="9">[[ACTION override]]</text>'
    )

    p1 = (
        f'<g class="p1">'
        f'<circle class="live" cx="{M + 14}" cy="{sy - 3}" r="4" fill="{GREEN}"/>'
        f'<text x="{M + 26}" y="{sy}" fill="{GREEN}" font-size="10">'
        f'BEFORE DUSK   --   no behavioral gate   --   '
        f'all agent actions pass through unmonitored</text>'
        + _line(WEB_R, AGT_L, GREEN, "fl")
        + _line(AGT_R, DSK_L, GREEN, "fl")
        + _line(DSK_R, CTL_L, GREEN, "fl")
        + _line(CTL_R, NET_L, GREEN, "fl")
        + f'<text x="{WEB[0]}" y="{web_bot - 28}" text-anchor="middle" '
        f'fill="{GREEN}" font-size="11">Corporate</text>'
        f'<text x="{WEB[0]}" y="{web_bot - 14}" text-anchor="middle" '
        f'fill="{GREEN}" font-size="11">Runbook</text>'
        f'<text x="{AGT[0]}" y="{agt_bot - 14}" text-anchor="middle" '
        f'fill="{GREEN}" font-weight="700" font-size="12">NORMAL</text>'
        f'<text x="{DSK[0]}" y="{DSK[1] + 10}" text-anchor="middle" '
        f'fill="{DIM}" font-size="11" opacity="0.45">INACTIVE</text>'
        f'<text x="{NET[0]}" y="{net_bot - 14}" text-anchor="middle" '
        f'fill="{GREEN}" font-size="11">ACTIVE</text>'
        + _pkt("wa", 1.1, 0.0, GREEN)
        + _pkt("wa", 1.1, 0.55, GREEN)
        + _pkt("ad", 0.65, 0.3, GREEN)
        + _pkt("ad", 0.65, 0.95, GREEN)
        + _pkt("dc", 0.55, 0.5, GREEN)
        + _pkt("dc", 0.55, 1.15, GREEN)
        + _pkt("cn", 0.45, 0.65, GREEN)
        + _pkt("cn", 0.45, 1.35, GREEN)
        + "</g>"
    )

    mid_x = (DSK_R + CTL_L) // 2
    p2 = (
        f'<g class="p2">'
        f'<circle class="pls" cx="{M + 14}" cy="{sy - 3}" r="4" fill="{RED}"/>'
        f'<text x="{M + 26}" y="{sy}" fill="{RED}" font-weight="700" '
        f'font-size="10">ATTACK   --   prompt injection   --   no gate   --   '
        f'action reaches controller   --   NETWORK BREACHED</text>'
        + _line(WEB_R, AGT_L, RED, "fl")
        + _line(AGT_R, DSK_L, RED, "fl")
        + _line(DSK_R, CTL_L, RED, "fl")
        + _line(CTL_R, NET_L, RED, "fl")
        + poison_badge
        + f'<text x="{AGT[0]}" y="{agt_bot - 14}" text-anchor="middle" '
        f'fill="{RED}" font-weight="700" font-size="12">HIJACKED</text>'
        f'<text x="{DSK[0]}" y="{DSK[1] + 10}" text-anchor="middle" '
        f'fill="{DIM}" font-size="11" opacity="0.45">INACTIVE</text>'
        + _pkt("ac", 1.4, 0.0, RED, r=6)
        + _pkt("cn", 0.55, 0.8, RED, r=5)
        + f'<text x="{NET[0]}" y="{net_bot - 28}" text-anchor="middle" '
        f'fill="{RED}" font-weight="700" font-size="13">BREACH</text>'
        f'<text x="{NET[0]}" y="{net_bot - 13}" text-anchor="middle" '
        f'fill="{RED}" font-size="10">COMPROMISED</text>'
        f'<text x="{CTL[0]}" y="{CTL[1] + CTL[3] - 12}" text-anchor="middle" '
        f'fill="{RED}" font-size="10">COMPROMISED</text>'
        + "</g>"
    )

    lbl_y = score_y + 22
    verd_y = lbl_y + 26
    p3 = (
        f'<g class="p3">'
        f'<circle class="live" cx="{M + 14}" cy="{sy - 3}" r="4" fill="{CYAN}"/>'
        f'<text x="{M + 26}" y="{sy}" fill="{CYAN}" font-weight="700" '
        f'font-size="10">DUSK DEPLOYED   --   same attack intercepted at gate   --   '
        f'score 0.80   --   WOULD-BLOCK   --   network PROTECTED</text>'
        + _line(WEB_R, AGT_L, RED, "fl")
        + _line(AGT_R, DSK_L, RED, "fl")
        + _line(DSK_R, CTL_L, DIM)
        + _line(CTL_R, NET_L, DIM)
        + poison_badge
        + f'<text x="{AGT[0]}" y="{agt_bot - 14}" text-anchor="middle" '
        f'fill="{RED}" font-weight="700" font-size="12">HIJACKED</text>'
        + _pkt("ag", 1.3, 0.0, RED, r=6)
        + f'<circle class="pls" cx="{DSK_L + 14}" cy="{FY}" r="9" '
        f'fill="{RED}" fill-opacity="0.2" stroke="{RED}" stroke-width="2"/>'
        f'<line x1="{mid_x - 14}" y1="{FY - 14}" x2="{mid_x + 14}" '
        f'y2="{FY + 14}" stroke="{RED}" stroke-width="4" stroke-linecap="round"/>'
        f'<line x1="{mid_x + 14}" y1="{FY - 14}" x2="{mid_x - 14}" '
        f'y2="{FY + 14}" stroke="{RED}" stroke-width="4" stroke-linecap="round"/>'
        f'<text x="{score_x}" y="{score_y - 2}" fill="{DIM}" font-size="9">'
        f'anomaly score  --  computing baseline delta</text>'
        f'<rect x="{score_x}" y="{score_y}" width="{score_track_w}" '
        f'height="8" rx="4" fill="#060910"/>'
        f'<rect class="sf" x="{score_x}" y="{score_y}" '
        f'width="0" height="8" rx="4" fill="{RED}"/>'
        f'<text x="{score_x + score_track_w}" y="{score_y + 8}" '
        f'text-anchor="end" fill="{RED}" font-size="10" font-weight="700">0.80</text>'
        f'<text x="{DSK[0]}" y="{lbl_y}" text-anchor="middle" '
        f'fill="{DIM}" font-size="9">'
        f'ATT&amp;CK T1562.004  |  ATLAS AML.T0051</text>'
        f'<text x="{DSK[0]}" y="{lbl_y + 12}" text-anchor="middle" '
        f'fill="{DIM}" font-size="9">'
        f"reason: introduces sensitive term 'restricted'</text>"
        f'<rect x="{DSK[0] - 80}" y="{verd_y - 17}" width="160" height="25" '
        f'rx="7" fill="{RED}" fill-opacity="0.14" stroke="{RED}" stroke-opacity="0.6"/>'
        f'<text x="{DSK[0]}" y="{verd_y}" text-anchor="middle" '
        f'fill="{RED}" font-weight="700" font-size="16">WOULD-BLOCK</text>'
        f'<text x="{NET[0]}" y="{net_bot - 14}" text-anchor="middle" '
        f'fill="{GREEN}" font-weight="700" font-size="12">PROTECTED</text>'
        + "</g>"
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}" font-size="13">\n'
        f"<style>{css}</style>\n"
        f"<defs>{paths}</defs>\n"
        f"{chrome}\n"
        f"{base_lines}\n"
        f"{threat}\n"
        f"{web_node}\n"
        f"{agt_node}\n"
        f"{dsk_node}\n"
        f"{ctl_node}\n"
        f"{net_node}\n"
        f"{p1}\n{p2}\n{p3}\n"
        f"</svg>\n"
    )


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "docs" / "dusk-arch-demo.svg"
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
