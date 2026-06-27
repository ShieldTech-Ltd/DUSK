from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ThreatEnrichment:
    query: str
    results: list[dict[str, object]]
    sources: list[str]


def enrich_alert(agent_id: str, action_type: str, mitre_id: str) -> ThreatEnrichment:
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))
        query = f"{mitre_id} {action_type} threat actor technique 2026"
        response = client.search(query=query, search_depth="basic", max_results=3)
        results: list[dict[str, object]] = response.get("results", [])
        sources = [str(item.get("url", "")) for item in results]
        return ThreatEnrichment(query=query, results=results, sources=sources)
    except Exception:
        return ThreatEnrichment(query="", results=[], sources=[])
