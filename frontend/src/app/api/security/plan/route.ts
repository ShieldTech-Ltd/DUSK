import { NextResponse } from 'next/server'
import store from '@/lib/trace/traceStore'
import { generatePlan } from '@/lib/trace/riskPlanner'
import { writeAudit } from '@/lib/trace/auditService'

export async function POST(req: Request) {
  try {
    const body = await req.json() as { issue_id?: string }
    const issueId = body?.issue_id

    if (!issueId) {
      return NextResponse.json({ error: 'issue_id is required' }, { status: 400 })
    }

    const issue = store.getIssue(issueId)
    if (!issue) {
      return NextResponse.json({ error: `Issue ${issueId} not found` }, { status: 404 })
    }

    // Check for existing plan
    const existing = store.getPlanByIssue(issueId)
    if (existing) {
      return NextResponse.json(existing)
    }

    const plan = generatePlan(issue)
    store.upsertPlan(plan)

    writeAudit(
      'plan_generated',
      `Execution plan generated for issue ${issueId}: ${plan.recommended_fix.slice(0, 80)}...`,
      'trace_planner',
      { issue_id: issueId, metadata: { plan_id: plan.plan_id, dusk_action: plan.dusk_action } }
    )

    return NextResponse.json(plan, { status: 201 })
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 })
  }
}
