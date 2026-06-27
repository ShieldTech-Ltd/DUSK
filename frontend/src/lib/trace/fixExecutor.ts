/**
 * Demo fix executor.
 *
 * Rules:
 * - If approval is missing → needs_manual_review
 * - If resources are missing → needs_manual_review
 * - If approved → simulate fix steps and return fixed
 * - Never performs destructive actions
 * - Never calls real customer systems
 * - All simulated changes are clearly labelled as demo mode
 */

import { randomUUID } from 'crypto'
import store from './traceStore'
import { writeAudit } from './auditService'
import type { Execution, DuskAction } from './traceTypes'

const FIX_LOGS: Record<DuskAction, string[]> = {
  enforce_block: [
    '[DEMO] Execution started',
    '[DEMO] Approval verified ✓',
    '[DEMO] Resources verified ✓',
    '[DEMO] DUSK gate policy created: action_type=blocked, scope=agent',
    '[DEMO] Agent tool access restricted',
    '[DEMO] Approval rule attached to agent workflow',
    '[DEMO] Audit record generated',
    '[DEMO] Execution completed — risk reduced to low',
  ],
  rotate_credentials: [
    '[DEMO] Execution started',
    '[DEMO] Approval verified ✓',
    '[DEMO] Resources verified ✓',
    '[DEMO] Previous role assignment revoked',
    '[DEMO] Agent credentials rotated (demo key generated)',
    '[DEMO] Hard BLOCK enforced on role_assignment for this agent',
    '[DEMO] Audit record generated',
    '[DEMO] Execution completed — credentials rotated, risk reduced to low',
  ],
  isolate_agent: [
    '[DEMO] Execution started',
    '[DEMO] Approval verified ✓',
    '[DEMO] Resources verified ✓',
    '[DEMO] Host isolated from outbound network connections',
    '[DEMO] DUSK sweep detection set to enforce mode',
    '[DEMO] Network segment firewall rules updated',
    '[DEMO] Audit record generated',
    '[DEMO] Execution completed — host isolated, risk reduced to medium',
  ],
  add_to_baseline: [
    '[DEMO] Execution started',
    '[DEMO] Resources verified ✓',
    '[DEMO] Agent baseline updated to include new action type',
    '[DEMO] BGP route change reviewed and flagged for network team',
    '[DEMO] Audit record generated',
    '[DEMO] Execution completed — baseline updated, risk reduced to low',
  ],
  restrict_tool_and_attach_policy: [
    '[DEMO] Execution started',
    '[DEMO] Approval verified ✓',
    '[DEMO] Resources verified ✓',
    '[DEMO] Tool access restricted',
    '[DEMO] Approval policy attached',
    '[DEMO] Audit record generated',
    '[DEMO] Execution completed',
  ],
  rotate_api_key: [
    '[DEMO] Execution started',
    '[DEMO] Approval verified ✓',
    '[DEMO] Resources verified ✓',
    '[DEMO] Old API key revoked',
    '[DEMO] New scoped API key generated (demo)',
    '[DEMO] Agent reconfigured with new key',
    '[DEMO] Audit record generated',
    '[DEMO] Execution completed',
  ],
  switch_to_readonly_policy: [
    '[DEMO] Execution started',
    '[DEMO] Approval verified ✓',
    '[DEMO] Resources verified ✓',
    '[DEMO] Agent access downgraded to read-only policy',
    '[DEMO] Write operations blocked at policy layer',
    '[DEMO] Audit record generated',
    '[DEMO] Execution completed',
  ],
}

export interface FixRequest {
  issue_id: string
  plan_id?: string
  approved_by?: string
  resources?: string[]
}

export function executeFix(req: FixRequest): Execution {
  const now = new Date().toISOString()
  const execId = `exec_${randomUUID().slice(0, 8)}`

  const issue = store.getIssue(req.issue_id)
  if (!issue) {
    const exec: Execution = {
      execution_id: execId,
      issue_id: req.issue_id,
      status: 'needs_manual_review',
      approved_by: null,
      resources: [],
      logs: ['[ERROR] Issue not found in store'],
      message: `Issue ${req.issue_id} not found.`,
      created_at: now,
      updated_at: now,
    }
    store.upsertExecution(exec)
    return exec
  }

  // Find the plan
  const plan = req.plan_id
    ? store.getPlan(req.plan_id)
    : store.getPlanByIssue(req.issue_id)

  if (!plan) {
    const exec: Execution = {
      execution_id: execId,
      issue_id: req.issue_id,
      status: 'needs_manual_review',
      approved_by: null,
      resources: [],
      logs: ['[ERROR] No execution plan found. Generate a plan first.'],
      message: 'No execution plan found. Generate a plan before executing.',
      created_at: now,
      updated_at: now,
    }
    store.upsertExecution(exec)
    return exec
  }

  // Check approval requirement
  if (plan.approval_required && !req.approved_by) {
    const exec: Execution = {
      execution_id: execId,
      issue_id: req.issue_id,
      plan_id: plan.plan_id,
      status: 'needs_manual_review',
      approved_by: null,
      resources: [],
      logs: [
        '[BLOCKED] Execution started',
        '[BLOCKED] Approval required but not provided',
        '[BLOCKED] Execution halted — needs_manual_review',
      ],
      message: 'Approval required before execution. Use POST /api/security/approvals to request approval.',
      created_at: now,
      updated_at: now,
    }
    store.upsertExecution(exec)

    writeAudit('fix_started', `Fix execution blocked — approval required for issue ${req.issue_id}`, 'trace_executor', {
      issue_id: req.issue_id,
      execution_id: execId,
    })

    return exec
  }

  // Check resources
  const resources = req.resources ?? plan.required_resources
  if (!resources || resources.length === 0) {
    const exec: Execution = {
      execution_id: execId,
      issue_id: req.issue_id,
      plan_id: plan.plan_id,
      status: 'needs_manual_review',
      approved_by: req.approved_by ?? null,
      resources: [],
      logs: [
        '[BLOCKED] Execution started',
        '[BLOCKED] No resources allocated',
        '[BLOCKED] Execution halted — needs_manual_review',
      ],
      message: 'Resources required before execution. Provide required_resources in the request.',
      created_at: now,
      updated_at: now,
    }
    store.upsertExecution(exec)
    return exec
  }

  // Execute fix (demo mode)
  writeAudit('fix_started', `Fix execution started for issue ${req.issue_id} by ${req.approved_by ?? 'system'}`, 'trace_executor', {
    issue_id: req.issue_id,
    execution_id: execId,
  })

  const logs = FIX_LOGS[plan.dusk_action] ?? FIX_LOGS.restrict_tool_and_attach_policy

  const exec: Execution = {
    execution_id: execId,
    issue_id: req.issue_id,
    plan_id: plan.plan_id,
    status: 'fixed',
    approved_by: req.approved_by ?? 'auto_approved',
    resources,
    logs,
    message: `[DEMO] Fix completed. ${plan.recommended_fix}`,
    risk_after_fix: plan.risk_after_fix,
    created_at: now,
    updated_at: new Date().toISOString(),
  }

  store.upsertExecution(exec)

  // Update issue status
  store.upsertIssue({ ...issue, status: 'fixed' })

  writeAudit('fix_completed', `Fix execution completed for issue ${req.issue_id} — status: fixed, risk: ${plan.risk_after_fix}`, req.approved_by ?? 'trace_executor', {
    issue_id: req.issue_id,
    execution_id: execId,
    metadata: { risk_after_fix: plan.risk_after_fix, dusk_action: plan.dusk_action },
  })

  return exec
}
