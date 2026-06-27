import { NextResponse } from 'next/server'
import { randomUUID } from 'crypto'
import store from '@/lib/trace/traceStore'
import { writeAudit } from '@/lib/trace/auditService'
import type { Approval } from '@/lib/trace/traceTypes'

export async function POST(req: Request) {
  try {
    const body = await req.json() as {
      issue_id?: string
      execution_id?: string
      requested_by?: string
      notes?: string
    }

    if (!body.issue_id) {
      return NextResponse.json({ error: 'issue_id is required' }, { status: 400 })
    }

    const issue = store.getIssue(body.issue_id)
    if (!issue) {
      return NextResponse.json({ error: `Issue ${body.issue_id} not found` }, { status: 404 })
    }

    const approval: Approval = {
      approval_id: `approval_${randomUUID().slice(0, 8)}`,
      issue_id: body.issue_id,
      execution_id: body.execution_id,
      requested_by: body.requested_by ?? 'manager',
      approved_by: null,
      decision: null,
      notes: body.notes ?? '',
      created_at: new Date().toISOString(),
      decided_at: null,
    }

    store.upsertApproval(approval)

    // Update issue status
    store.upsertIssue({ ...issue, status: 'in_review' })

    writeAudit(
      'approval_requested',
      `Approval requested for issue ${body.issue_id} by ${approval.requested_by}`,
      approval.requested_by,
      { issue_id: body.issue_id, metadata: { approval_id: approval.approval_id } }
    )

    return NextResponse.json(approval, { status: 201 })
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}

export function GET() {
  return NextResponse.json(Array.from(store.approvals.values()))
}
