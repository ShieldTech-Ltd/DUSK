/**
 * Tavily adapter — external content intelligence for customer discovery and threat enrichment.
 *
 * Live when TAVILY_API_KEY is set; falls back to demo data otherwise.
 */

import type { IntegrationResult } from '../traceTypes'

export interface TavilyResearchResult {
  query: string
  summary: string
  sources: { title: string; url: string; snippet: string }[]
  companies_mentioned?: string[]
  integration_status: 'live' | 'demo_mode'
}

const DEMO_RESEARCH: TavilyResearchResult = {
  query: 'companies using AI agents workflow automation security',
  summary:
    'Multiple companies across fintech, healthcare, and SaaS are deploying autonomous AI agents for workflow automation. Key security gaps include unaudited API access, missing approval gates, and agents with database write permissions.',
  sources: [
    {
      title: 'The Rise of Agentic AI in Enterprise Workflows',
      url: 'https://example.com/agentic-ai-enterprise',
      snippet: 'Companies like Acme AI Ops and FinFlow Automation are deploying agents that handle customer data and financial workflows without human approval gates.',
    },
    {
      title: 'Security Challenges of AI Agent Deployments',
      url: 'https://example.com/ai-agent-security',
      snippet: 'Prompt injection, over-permissive API keys, and lack of audit trails are the top three security risks cited by security teams working with AI agents.',
    },
    {
      title: 'MITRE ATLAS: LLM Prompt Injection Threat Model',
      url: 'https://atlas.mitre.org/techniques/AML.T0051',
      snippet: 'LLM Prompt Injection (AML.T0051) remains the most common attack vector for AI agents with external tool access.',
    },
  ],
  companies_mentioned: ['Acme AI Ops', 'FinFlow Automation', 'NovaCRM Labs', 'HealthBridge AI'],
  integration_status: 'demo_mode',
}

export async function tavilyResearch(query: string): Promise<TavilyResearchResult> {
  const apiKey = process.env.TAVILY_API_KEY

  if (!apiKey) {
    return { ...DEMO_RESEARCH, query }
  }

  try {
    const res = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: apiKey,
        query,
        search_depth: 'advanced',
        include_answer: true,
        max_results: 5,
      }),
    })

    if (!res.ok) throw new Error(`Tavily API ${res.status}`)

    const data = await res.json() as {
      answer?: string
      results?: { title: string; url: string; content: string }[]
    }

    return {
      query,
      summary: data.answer ?? 'No summary available.',
      sources: (data.results ?? []).map(r => ({
        title: r.title,
        url: r.url,
        snippet: r.content.slice(0, 200),
      })),
      integration_status: 'live',
    }
  } catch {
    return { ...DEMO_RESEARCH, query, integration_status: 'demo_mode' }
  }
}

export async function tavilyEnrich(
  agentId: string,
  actionType: string,
  mitreId: string
): Promise<IntegrationResult & { enrichment?: TavilyResearchResult }> {
  const query = `${mitreId} ${actionType} LLM agent threat ${new Date().getFullYear()}`
  const enrichment = await tavilyResearch(query)

  return {
    integration_status: enrichment.integration_status === 'live' ? 'live' : 'demo_mode',
    status: 'enrichment_complete',
    message: enrichment.integration_status === 'live'
      ? `Tavily live enrichment for ${agentId} (${mitreId})`
      : `[DEMO] Tavily enrichment for ${agentId} (${mitreId})`,
    payload: { agent_id: agentId, action_type: actionType, mitre_id: mitreId },
    enrichment,
  }
}

export function tavilyStatus(): 'live' | 'demo_mode' {
  return process.env.TAVILY_API_KEY ? 'live' : 'demo_mode'
}
