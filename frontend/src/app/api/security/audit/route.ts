import { NextResponse } from 'next/server'
import { writeAudit, getAudit } from '@/lib/trace/auditService'
import type { AuditEventType } from '@/lib/trace/traceTypes'

export function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const issueId = searchParams.get('issue_id') ?? undefined
  return NextResponse.json(getAudit(issueId))
}

export async function POST(req: Request) {
  try {
    const body = await req.json() as {
      event_type?: AuditEventType
      description?: string
      actor?: string
      issue_id?: string
      execution_id?: string
      metadata?: Record<string, string>
    }

    if (!body.event_type || !body.description) {
      return NextResponse.json(
        { error: 'event_type and description are required' },
        { status: 400 }
      )
    }

    const event = writeAudit(
      body.event_type,
      body.description,
      body.actor ?? 'api',
      {
        issue_id: body.issue_id,
        execution_id: body.execution_id,
        metadata: body.metadata,
      }
    )

    return NextResponse.json(event, { status: 201 })
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
