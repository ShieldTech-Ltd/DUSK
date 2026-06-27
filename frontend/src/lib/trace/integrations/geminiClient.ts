/**
 * Gemini / Google DeepMind adapter — risk explanation, deployment summary
 * and manager-facing security recommendation.
 *
 * Live when GEMINI_API_KEY is set; returns demo explanation otherwise.
 */

import type { IntegrationResult } from '../traceTypes'

export interface GeminiExplainRequest {
  issue_id: string
  issue_summary: string
  mitre_id?: string
  blast_radius?: string
  audience?: 'technical' | 'manager' | 'executive'
}

export interface GeminiExplanation {
  summary: string
  risk_explanation: string
  recommended_action: string
  urgency: 'critical' | 'high' | 'medium' | 'low'
  model_used: string
}

const DEMO_EXPLANATIONS: Record<string, GeminiExplanation> = {
  critical: {
    summary: 'An AI agent attempted a privileged action that is outside its normal behavior profile.',
    risk_explanation: 'This action matches the MITRE ATT&CK technique for impair defenses and could allow the attacker to remove security controls, enabling further lateral movement across your environment.',
    recommended_action: 'Immediately block this agent action and request manager approval to investigate the agent\'s recent conversation history for signs of prompt injection.',
    urgency: 'critical',
    model_used: 'gemini-1.5-pro (demo)',
  },
  high: {
    summary: 'A network scanning pattern was detected from an internal host.',
    risk_explanation: 'The host contacted an unusually large number of internal destinations in a short time window. This is a strong indicator of reconnaissance activity — a precursor to lateral movement.',
    recommended_action: 'Isolate the host from further outbound connections and initiate an incident investigation. Review recent access logs for this host.',
    urgency: 'high',
    model_used: 'gemini-1.5-pro (demo)',
  },
  medium: {
    summary: 'An agent performed an action that is new to its behavioral baseline.',
    risk_explanation: 'While the action may be legitimate, the deviation from established behavior increases the probability of an adversarial prompt injection attack or misconfigured automation.',
    recommended_action: 'Review the agent\'s recent actions, update the baseline if legitimate, or apply a policy block if the behavior is unauthorized.',
    urgency: 'medium',
    model_used: 'gemini-1.5-flash (demo)',
  },
}

export async function geminiExplain(req: GeminiExplainRequest): Promise<IntegrationResult & { explanation?: GeminiExplanation }> {
  const apiKey = process.env.GEMINI_API_KEY

  if (!apiKey) {
    const urgency = req.blast_radius === 'high' ? 'critical'
      : req.blast_radius === 'medium' ? 'high'
      : 'medium'

    return {
      integration_status: 'demo_mode',
      status: 'demo_explanation_returned',
      message: 'GEMINI_API_KEY missing. Returning demo risk explanation.',
      payload: req,
      explanation: DEMO_EXPLANATIONS[urgency] ?? DEMO_EXPLANATIONS.medium,
    }
  }

  try {
    const audience = req.audience ?? 'manager'
    const prompt = `You are a security advisor. Explain the following security issue to a ${audience}.

Issue: ${req.issue_summary}
MITRE Technique: ${req.mitre_id ?? 'unknown'}
Blast Radius: ${req.blast_radius ?? 'unknown'}

Provide:
1. A one-sentence summary
2. A risk explanation (2-3 sentences)
3. A recommended action (1-2 sentences)
4. An urgency level (critical/high/medium/low)

Respond in JSON format: { summary, risk_explanation, recommended_action, urgency }`

    const res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key=${apiKey}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: prompt }] }],
          generationConfig: { responseMimeType: 'application/json' },
        }),
      }
    )

    if (!res.ok) throw new Error(`Gemini API ${res.status}`)

    const data = await res.json() as {
      candidates?: { content?: { parts?: { text?: string }[] } }[]
    }
    const text = data?.candidates?.[0]?.content?.parts?.[0]?.text ?? '{}'
    const parsed = JSON.parse(text) as Partial<GeminiExplanation>

    return {
      integration_status: 'live',
      status: 'explanation_generated',
      message: 'Gemini risk explanation generated',
      payload: req,
      explanation: {
        summary: parsed.summary ?? '',
        risk_explanation: parsed.risk_explanation ?? '',
        recommended_action: parsed.recommended_action ?? '',
        urgency: parsed.urgency ?? 'medium',
        model_used: 'gemini-1.5-pro',
      },
    }
  } catch {
    const urgency = req.blast_radius === 'high' ? 'critical'
      : req.blast_radius === 'medium' ? 'high'
      : 'medium'
    return {
      integration_status: 'demo_mode',
      status: 'demo_explanation_returned',
      message: '[DEMO] Gemini call failed. Returning demo explanation.',
      payload: req,
      explanation: DEMO_EXPLANATIONS[urgency] ?? DEMO_EXPLANATIONS.medium,
    }
  }
}

export function geminiStatus(): 'live' | 'demo_mode' {
  return process.env.GEMINI_API_KEY ? 'live' : 'demo_mode'
}
