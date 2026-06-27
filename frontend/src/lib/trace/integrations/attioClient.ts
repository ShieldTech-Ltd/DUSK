/**
 * Attio adapter — system of record for customers, opportunities, approvals,
 * execution records and deployment readiness.
 *
 * Live when ATTIO_API_KEY + ATTIO_WORKSPACE_ID are set; returns Attio-ready
 * payload in demo mode otherwise.
 */

import type { IntegrationResult } from '../traceTypes'

export interface AttioSyncPayload {
  object_type: 'company' | 'opportunity' | 'execution' | 'deployment'
  [key: string]: unknown
}

export async function attioSync(payload: AttioSyncPayload): Promise<IntegrationResult> {
  const apiKey = process.env.ATTIO_API_KEY
  const workspaceId = process.env.ATTIO_WORKSPACE_ID

  if (!apiKey || !workspaceId) {
    return {
      integration_status: 'demo_mode',
      status: 'demo_payload_generated',
      message: 'ATTIO_API_KEY missing. Returning Attio-ready payload only.',
      payload,
    }
  }

  try {
    // Map object_type to Attio API endpoint
    const objectSlug = payload.object_type === 'company' ? 'companies'
      : payload.object_type === 'opportunity' ? 'opportunities'
      : payload.object_type === 'execution' ? 'records'
      : 'records'

    const res = await fetch(`https://api.attio.com/v2/objects/${objectSlug}/records`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ data: payload }),
    })

    if (!res.ok) throw new Error(`Attio API ${res.status}: ${await res.text()}`)

    const data = await res.json() as { data?: { id?: { record_id?: string } } }
    const recordId = data?.data?.id?.record_id

    return {
      integration_status: 'live',
      status: 'synced',
      message: `Attio record created: ${recordId}`,
      payload: { ...payload, attio_record_id: recordId },
    }
  } catch (err) {
    return {
      integration_status: 'failed',
      status: 'sync_failed',
      message: `Attio sync failed: ${err instanceof Error ? err.message : 'unknown error'}. Returning payload only.`,
      payload,
    }
  }
}

export function attioStatus(): 'live' | 'demo_mode' {
  return process.env.ATTIO_API_KEY && process.env.ATTIO_WORKSPACE_ID ? 'live' : 'demo_mode'
}
