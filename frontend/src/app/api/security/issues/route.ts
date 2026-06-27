import { NextResponse } from 'next/server'
import store from '@/lib/trace/traceStore'
import { writeAudit } from '@/lib/trace/auditService'

export function GET() {
  return NextResponse.json(store.getIssues())
}

export async function POST(req: Request) {
  try {
    const body = await req.json() as {
      id?: string
      type?: string
      [key: string]: unknown
    }

    if (!body.id || !body.type) {
      return NextResponse.json({ error: 'id and type are required' }, { status: 400 })
    }

    store.upsertIssue(body as unknown as Parameters<typeof store.upsertIssue>[0])

    writeAudit('issue_detected', `New issue reported: ${body.id}`, 'api', { issue_id: body.id as string })

    return NextResponse.json(body, { status: 201 })
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
