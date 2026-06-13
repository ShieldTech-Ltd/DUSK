"""The agent action layer: controller-agnostic events for control-plane actions.

This package implements the ingest side of Dusk's v1 direction. Agent
actions arrive from whatever controller the environment uses (a cloud
network API, an SDN controller, a policy endpoint) and are normalised into
one canonical :class:`~dusk.actions.event.AgentAction` event that the rest
of the pipeline can reason about.
"""

from dusk.actions.event import AgentAction
from dusk.actions.ingest import ActionParseError, normalise, read_actions

__all__ = ["ActionParseError", "AgentAction", "normalise", "read_actions"]
