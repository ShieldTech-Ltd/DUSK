/**
 * Mubit Minima adapter — cost-aware model recommendation for security analysis.
 *
 * Live when MUBIT_API_KEY is set; returns demo recommendation otherwise.
 */

import type { IntegrationResult } from '../traceTypes'

export interface MubitRecommendRequest {
  task: string
  context?: string
  budget_priority?: 'cost' | 'speed' | 'quality'
}

export interface MubitRecommendation {
  recommended_model: string
  estimated_cost_per_1k_tokens: number
  latency_estimate_ms: number
  reasoning: string
}

const DEMO_RECOMMENDATIONS: Record<string, MubitRecommendation> = {
  cost: {
    recommended_model: 'gemini-1.5-flash',
    estimated_cost_per_1k_tokens: 0.002,
    latency_estimate_ms: 800,
    reasoning: 'For security classification tasks, Gemini Flash offers the best cost/accuracy tradeoff at sub-second latency.',
  },
  speed: {
    recommended_model: 'gemini-1.5-flash',
    estimated_cost_per_1k_tokens: 0.002,
    latency_estimate_ms: 600,
    reasoning: 'Optimized for lowest latency — ideal for real-time agent action gating.',
  },
  quality: {
    recommended_model: 'gemini-1.5-pro',
    estimated_cost_per_1k_tokens: 0.007,
    latency_estimate_ms: 2200,
    reasoning: 'For high-stakes security decisions requiring deep reasoning, Gemini Pro provides the highest accuracy.',
  },
}

export async function mubitRecommend(req: MubitRecommendRequest): Promise<IntegrationResult & { recommendation?: MubitRecommendation }> {
  const apiKey = process.env.MUBIT_API_KEY

  if (!apiKey) {
    const priority = req.budget_priority ?? 'cost'
    return {
      integration_status: 'demo_mode',
      status: 'demo_recommendation_returned',
      message: 'MUBIT_API_KEY missing. Returning demo model recommendation.',
      payload: req,
      recommendation: DEMO_RECOMMENDATIONS[priority] ?? DEMO_RECOMMENDATIONS.cost,
    }
  }

  try {
    const res = await fetch('https://api.mubit.io/v1/recommend', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(req),
    })

    if (!res.ok) throw new Error(`Mubit API ${res.status}`)

    const recommendation = await res.json() as MubitRecommendation

    return {
      integration_status: 'live',
      status: 'recommendation_returned',
      message: 'Mubit model recommendation received',
      payload: req,
      recommendation,
    }
  } catch {
    const priority = req.budget_priority ?? 'cost'
    return {
      integration_status: 'demo_mode',
      status: 'demo_recommendation_returned',
      message: '[DEMO] Mubit call failed. Returning demo recommendation.',
      payload: req,
      recommendation: DEMO_RECOMMENDATIONS[priority] ?? DEMO_RECOMMENDATIONS.cost,
    }
  }
}

export function mubitStatus(): 'live' | 'demo_mode' {
  return process.env.MUBIT_API_KEY ? 'live' : 'demo_mode'
}
