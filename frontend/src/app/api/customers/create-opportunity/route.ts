import { NextResponse } from 'next/server'
import { createOpportunity } from '@/lib/trace/customerDiscoveryService'
import { n8nTrigger } from '@/lib/trace/integrations/n8nClient'
import { attioSync } from '@/lib/trace/integrations/attioClient'

export async function POST(req: Request) {
  try {
    const body = await req.json() as {
      lead_id?: string
      company?: string
      requested_by?: string
    }

    if (!body.lead_id) {
      return NextResponse.json({ error: 'lead_id is required' }, { status: 400 })
    }

    const result = createOpportunity(body.lead_id, body.requested_by)

    if (!result.success) {
      return NextResponse.json({ error: result.message }, { status: 404 })
    }

    // Sync to Attio (live or demo)
    const attioResult = await attioSync({
      object_type: 'company',
      company: result.lead?.company ?? body.company ?? 'Unknown',
      lead_id: body.lead_id,
      attio_record_id: result.attio_record_id,
      status: 'opportunity_created',
      created_at: new Date().toISOString(),
    })

    // Trigger n8n follow-up workflow (live or demo)
    const n8nResult = await n8nTrigger({
      workflow_type: 'customer_followup',
      company: result.lead?.company ?? body.company ?? 'Unknown',
      suggested_pitch: result.lead?.suggested_pitch ?? '',
      contact_email: '',
    })

    return NextResponse.json({
      ...result,
      attio: attioResult,
      n8n: n8nResult,
    }, { status: 201 })
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
