"""The agent action layer: ingest, baseline, analyse, and gate agent actions.

Agent actions arrive from whatever controller the environment uses (a cloud
network API, an SDN controller, a policy endpoint) and are normalised into one
canonical :class:`~dusk_harness.actions.event.AgentAction` event. The gate then learns
each agent's normal behaviour, scores a new action against that baseline, and
renders a verdict (ALLOW, WOULD-BLOCK, BLOCK) with reasons and MITRE mappings.
Source-specific shapes are handled by adapters (see :mod:`dusk_harness.actions.adapters`).
"""

from dusk_harness.actions.adapters.base import AdapterError, SourceAdapter
from dusk_harness.actions.analyse import AnalysisResult, analyse
from dusk_harness.actions.baseline import AgentProfile, Baseline
from dusk_harness.actions.event import KNOWN_ACTION_TYPES, AgentAction
from dusk_harness.actions.ingest import ingest_file
from dusk_harness.actions.normaliser import known_sources, normalise_record
from dusk_harness.actions.verdict import ALLOW, BLOCK, WOULD_BLOCK, ActionGate, GateVerdict

__all__ = [
    "ALLOW",
    "BLOCK",
    "KNOWN_ACTION_TYPES",
    "WOULD_BLOCK",
    "ActionGate",
    "AdapterError",
    "AgentAction",
    "AgentProfile",
    "AnalysisResult",
    "Baseline",
    "GateVerdict",
    "SourceAdapter",
    "analyse",
    "ingest_file",
    "known_sources",
    "normalise_record",
]
