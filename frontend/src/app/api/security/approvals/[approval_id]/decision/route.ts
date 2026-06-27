import { NextResponse } from 'next/server'
import store from '@/lib/trace/traceStore'
import { writeAudit } from '@/lib/trace/auditService'
import type { ApprovalDecision } from '@/lib/trace/traceTypes'

const VALID_DECISIONS: ApprovalDecision[] = ['approved', 'rejected', 'needs_more_info']

export async function POST(
  req: Request,
  { params }: { params: { approval_id: string } }
) {
  try {
    const body = await req.json() as {
      decision?: ApprovalDecision
      approved_by?: string
      notes?: string
    }

    if (!body.decision || !VALID_DECISIONS.includes(body.decision)) {
      return NextResponse.json(
        { error: `decision must be one of: ${VALID_DECISIONS.join(', ')}` },
        { status: 400 }
      )
    }

    const approval = store.getApproval(params.approval_id)
    if (!approval) {
      return NextResponse.json(
        { error: `Approval ${params.approval_id} not found` },
        { status: 404 }
      )
    }

    const updated = {
      ...approval,
      decision: body.decision,
      approved_by: body.approved_by ?? 'manager',
      notes: body.notes ?? approval.notes,
      decided_at: new Date().toISOString(),
    }

    store.upsertApproval(updated)

    // Update issue status if approved
    const issue = store.getIssue(approval.issue_id)
    if (issue && body.decision === 'approved') {
      store.upsertIssue({ ...issue, status: 'approved' })
    }

    writeAudit(
      'approval_decision',
      `Approval decision for ${params.approval_id}: ${body.decision} by ${updated.approved_by}`,
      updated.approved_by,
      {
        issue_id: approval.issue_id,
        metadata: { approval_id: params.approval_id, decision: body.decision },
      }
    )

    return NextResponse.json(updated)
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
