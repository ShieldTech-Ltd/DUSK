"""The agent action layer: controller-agnostic events for control-plane actions.

This package implements the ingest side of Dusk's v1 direction. Agent
actions arrive from whatever controller the environment uses (a cloud
network API, an SDN controller, a policy endpoint) and are normalised into
one canonical :class:`~dusk.actions.event.AgentAction` event that the rest
of the pipeline can reason about. Source-specific shapes are handled by
adapters (see :mod:`dusk.actions.adapters`).
"""

from dusk.actions.adapters.base import AdapterError, SourceAdapter
from dusk.actions.event import KNOWN_ACTION_TYPES, AgentAction
from dusk.actions.ingest import ingest_file
from dusk.actions.normaliser import known_sources, normalise_record

__all__ = [
    "KNOWN_ACTION_TYPES",
    "AdapterError",
    "AgentAction",
    "SourceAdapter",
    "ingest_file",
    "known_sources",
    "normalise_record",
]
