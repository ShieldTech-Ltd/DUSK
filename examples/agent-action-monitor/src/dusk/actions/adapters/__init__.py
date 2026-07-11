"""Source adapters: map one controller's record shape into AgentAction.

Each adapter knows the record format of a single control-plane source (a
cloud activity log, an SDN controller, a policy endpoint) and maps it onto
the canonical :class:`~dusk.actions.event.AgentAction`. Adapters make ingest
source-agnostic: the rest of the pipeline never sees a vendor-specific shape.
"""

from dusk.actions.adapters.base import AdapterError, SourceAdapter

__all__ = ["AdapterError", "SourceAdapter"]
