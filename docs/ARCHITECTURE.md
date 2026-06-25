# DUSK architecture

DUSK is a layered, pluggable system. Each layer has one responsibility and a
narrow interface to the next, so sources, detections, and responders can be
added or replaced without touching the core.

For the full enterprise system view, see
[dusk-enterprise-flow.svg](dusk-enterprise-flow.svg).

## Layers

- Sensors (`dusk.sensor`): turn a traffic source (a pcap today, live capture and
  Zeek next) into a uniform stream of packet records.
- Actions (`dusk.actions`): ingest an agent's control-plane action from any
  source and normalise it into a single canonical AgentAction event. Adapters
  map vendor-specific records onto the canonical shape.
- Engine (`dusk.core`): runs the registered detections over the input, reaches a
  verdict, and predicts the next kill-chain stage.
- Responders (`dusk.respond`): act on a finding, from alerting today to active
  isolation later.

## Data flow

Input is normalised by a sensor or an action adapter, evaluated by the engine,
and turned into a verdict. A CLEAR verdict passes; an ALERT verdict is handed to
a responder. The agent action path and the packet path share the engine and
responder layers while keeping their own ingestion.

## Roadmap

- v1: agent action layer. Ingest control-plane actions, baseline each agent,
  analyse and predict, and render verdicts in watch mode.
- v2: data plane. Reposition the existing packet and flow detections (sweep,
  boundary, pcap sensor) as a confirmation layer that correlates what an agent
  commanded with what the network actually did.
- v3: reasoning layer. Inspect the agent's decision and tool-call reasoning to
  catch intent before the action is formed.

DUSK ships in watch mode first: it renders a verdict on every action but does
not enforce until its analysis is trusted in a given environment, because an
inline gate that wrongly blocks a legitimate action can disrupt a network.

## Oracle AI Database 26ai integration

See [ORACLE-INTEGRATION.md](ORACLE-INTEGRATION.md) for how DUSK and Oracle 26ai
work as complementary security layers.
