/**
 * n8n adapter — approval, follow-up and escalation workflow automation.
 *
 * Live when N8N_WEBHOOK_URL is set.
 * Payload matches the DUSK n8n webhook schema from demo/n8n_workflow.json.
 */

import type { IntegrationResult } from '../traceTypes'

export interface N8nTriggerPayload {
  verdict?: string
  analysis?: {
    agent_id?: string
    score?: number
    action_type?: string
    target?: string
    mitre_attack?: string
    blast_radius?: string
    predicted_next?: string
  }
  workflow_type?: 'soar_alert' | 'approval_request' | 'customer_followup'
  company?: string
  contact_email?: string
  suggested_pitch?: string
  [key: string]: unknown
}

const DEMO_SOAR_RESULT = {
  workflow_run_id: 'demo_run_001',
  status: 'demo_triggered',
  steps_completed: [
    'Webhook received',
    'Alert formatted for SOAR',
    'SOAR incident opened (demo)',
    'Escalation email queued (demo)',
  ],
}

export async function n8nTrigger(payload: N8nTriggerPayload): Promise<IntegrationResult> {
  const webhookUrl = process.env.N8N_WEBHOOK_URL

  if (!webhookUrl) {
    return {
      integration_status: 'demo_mode',
      status: 'demo_workflow_triggered',
      message: '[DEMO] N8N_WEBHOOK_URL missing. Returning demo workflow result.',
      payload: { ...DEMO_SOAR_RESULT, input: payload },
    }
  }

  try {
    const res = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!res.ok) throw new Error(`n8n webhook ${res.status}: ${await res.text()}`)

    const data = await res.json() as unknown

    return {
      integration_status: 'live',
      status: 'workflow_triggered',
      message: 'n8n workflow triggered successfully',
      payload: data,
    }
  } catch (err) {
    return {
      integration_status: 'demo_mode',
      status: 'demo_workflow_triggered',
      message: `[DEMO] n8n call failed: ${err instanceof Error ? err.message : 'unknown'}. Returning demo result.`,
      payload: { ...DEMO_SOAR_RESULT, input: payload },
    }
  }
}

export function n8nStatus(): 'live' | 'demo_mode' {
  return process.env.N8N_WEBHOOK_URL ? 'live' : 'demo_mode'
}
