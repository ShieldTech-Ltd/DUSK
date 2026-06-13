"""The AgentAction event: one normalised control-plane action.

An :class:`AgentAction` is controller-agnostic by design. Whatever system an
agent used to change the network (a cloud API, an SDN controller, a policy
endpoint), the event records the same canonical facts: who acted, what verb,
on what resource, when, and through which controller. Controller-specific
extras travel in :attr:`AgentAction.details` without affecting the canonical
shape.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentAction:
    """One normalised action an agent performed on the network control plane.

    Attributes:
        agent_id: Identity of the acting agent (service account, role, or
            agent name as reported by the controller).
        action: The verb, for example ``"create"``, ``"update"``,
            ``"delete"``.
        resource_type: The kind of resource touched, for example
            ``"firewall_rule"``, ``"route"``, ``"security_group"``,
            ``"segment"``.
        resource_id: Identifier of the specific resource that was touched.
        timestamp: When the action happened, in epoch seconds.
        source: Which controller produced the record, for example
            ``"cloud"``, ``"sdn"``, ``"policy_api"``.
        details: Controller-specific extras that do not fit the canonical
            fields. Never required by the pipeline.
    """

    agent_id: str
    action: str
    resource_type: str
    resource_id: str
    timestamp: float
    source: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the event."""
        return {
            "agent_id": self.agent_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "details": self.details,
        }
