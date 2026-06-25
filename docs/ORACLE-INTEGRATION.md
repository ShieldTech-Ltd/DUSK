# DUSK and Oracle AI Database 26ai

## Overview

Enterprise databases increasingly serve autonomous AI agents as well as human
users and applications. An agent that reads or writes enterprise data is a new
consumer of the database, and therefore a new attack surface: if the agent is
hijacked or prompt-injected, its queries carry the agent's full privileges and
look entirely legitimate at the point of execution.

A database-layer control such as Oracle's SQL Firewall inspects SQL at the
database boundary, where the query is about to run. DUSK operates one layer
upstream, at the agent action layer: it inspects the agent's control-plane
action before that action ever becomes a database query. The two controls guard
different boundaries and reinforce each other.

## Complementary security layers

| Layer | Control | What it guards |
|---|---|---|
| Agent action layer | DUSK | Inspects and reasons about an agent's request before it executes |
| Database layer | Oracle SQL Firewall | Inspects SQL at the database boundary |

The controls are complementary, not redundant. By the time a hijacked agent's
query is evaluated at the database boundary, the agent has already reached the
database. DUSK aims to stop the action earlier, at the point where the agent
states its intent, so a malicious request is caught before it propagates
downstream.

## How DUSK can use Oracle 26ai

DUSK can persist normalised AgentAction events in Oracle AI Database 26ai and
draw on its capabilities for richer detection. The following are integration
directions, not shipped features:

- AI Vector Search: similarity-based anomaly detection across historical agent
  actions, to surface behaviour that departs from an agent's established pattern.
- Property graphs: modelling agent relationship networks to detect coordinated
  multi-agent activity that no single action would reveal.
- LLM integration: generating concise natural-language summaries of alerts for
  responders.
- JSON and relational duality: storing and querying AgentAction events flexibly,
  as documents or as relations, without duplicating the data model.

## Architecture

See [dusk-enterprise-flow.svg](dusk-enterprise-flow.svg) for the full four-layer
enterprise system diagram: agents, the DUSK inline gate, the decision split, and
the Oracle AI Database 26ai integration at the data layer.
