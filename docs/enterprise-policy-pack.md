# Enterprise agent-action policy pack

DUSK combines behavioural anomaly scoring with deterministic rules for consequential agent actions. Behaviour scoring asks whether an action is unusual. Policy asks whether the action is permitted at all. A deterministic denial always overrides an approval requirement or behavioural allow result.

The bundled `dusk-enterprise` pack contains 60 controls across identity, permits, broker integrity, filesystem, execution, network, cloud, secrets, data, communication, MCP, supply chain, and session behaviour. Fifteen controls are executable against the structured policy context. The remaining 45 controls are marked `planned` and name the telemetry or runtime state required before they can be enforced truthfully.

## Decision order

`DENY` takes precedence over `REQUIRE_APPROVAL`, which takes precedence over `ALLOW`.

Unknown consequential actions must be classified by the gateway before production enforcement. A deployment should fail closed when required identity, permit, tenant, tool, destination, or approval context is absent.

## Policy context

The evaluator accepts a nested mapping. Integrations normalize provider-specific events before evaluation.

```python
from dusk.policies import load_enterprise_pack

context = {
    "identity": {"tenant_id": "tenant-a"},
    "action": {
        "type": "network.firewall.update",
        "tenant_id": "tenant-a",
        "cidrs": ["0.0.0.0/0"],
    },
}

result = load_enterprise_pack().evaluate(context)
```

Decision evidence contains the policy-pack version and matched rule IDs, versions, and reasons. It does not copy action payloads or secrets.

## Rule lifecycle

- `enforced`: executable by the deterministic evaluator and covered by regression tests.
- `planned`: documented control with explicit missing prerequisites. It never affects a decision.

Rule IDs and versions are stable. Behaviour changes require a rule version update. Pack changes require a pack version update. Tenant overrides must be signed, scoped, and auditable. Exceptions require an owner, reason, mitigation, and expiry and must never disable protection of DUSK policy, credentials, or audit evidence.

## Production boundary

Catalogue validation and evaluator tests do not prove downstream enforcement. Production readiness additionally requires the gateway and credential-holding broker to supply trusted context, enforce the result before execution, reject bypass, and prove that denied actions leave downstream state unchanged.
