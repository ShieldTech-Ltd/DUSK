/**
 * Superlinked adapter — semantic vector matching for ICP scoring
 * and incident similarity search.
 *
 * Live when SUPERLINKED_API_KEY + SUPERLINKED_ENDPOINT are set.
 */

import type { IntegrationResult } from '../traceTypes'

export interface SuperlinkedMatchRequest {
  company: string
  use_case: string
  security_pain: string
}

export interface SuperlinkedMatchResult {
  icp_score: number
  similar_incidents: { incident_id: string; similarity: number; description: string }[]
  recommended_tier: 'enterprise' | 'growth' | 'startup'
}

const DEMO_MATCH: SuperlinkedMatchResult = {
  icp_score: 0.84,
  similar_incidents: [
    { incident_id: 'inc_2024_001', similarity: 0.92, description: 'LLM agent with external email tool caused data exfiltration' },
    { incident_id: 'inc_2024_007', similarity: 0.78, description: 'Finance automation agent escalated privileges via role_assignment' },
  ],
  recommended_tier: 'enterprise',
}

export async function superlinkedMatch(req: SuperlinkedMatchRequest): Promise<IntegrationResult & { match?: SuperlinkedMatchResult }> {
  const apiKey = process.env.SUPERLINKED_API_KEY
  const endpoint = process.env.SUPERLINKED_ENDPOINT

  if (!apiKey || !endpoint) {
    return {
      integration_status: 'demo_mode',
      status: 'demo_match_returned',
      message: 'SUPERLINKED_API_KEY missing. Returning demo similarity score.',
      payload: req,
      match: DEMO_MATCH,
    }
  }

  try {
    const res = await fetch(`${endpoint}/match`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req),
    })

    if (!res.ok) throw new Error(`Superlinked API ${res.status}`)

    const match = await res.json() as SuperlinkedMatchResult

    return {
      integration_status: 'live',
      status: 'match_complete',
      message: 'Superlinked ICP match completed',
      payload: req,
      match,
    }
  } catch {
    return {
      integration_status: 'demo_mode',
      status: 'demo_match_returned',
      message: '[DEMO] Superlinked call failed. Returning demo result.',
      payload: req,
      match: DEMO_MATCH,
    }
  }
}

export function superlinkedStatus(): 'live' | 'demo_mode' {
  return process.env.SUPERLINKED_API_KEY && process.env.SUPERLINKED_ENDPOINT ? 'live' : 'demo_mode'
}
