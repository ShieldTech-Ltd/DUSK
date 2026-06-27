/**
 * Trace execution layer — unit tests
 *
 * Tests cover the service modules directly (no HTTP needed).
 * The API routes are thin wrappers around these services,
 * so testing the services gives full coverage of the business logic.
 */

import store from '@/lib/trace/traceStore'
import { generatePlan } from '@/lib/trace/riskPlanner'
import { executeFix } from '@/lib/trace/fixExecutor'
import { writeAudit, getAudit } from '@/lib/trace/auditService'
import { prepareDeployment } from '@/lib/trace/deploymentService'
import { discoverCustomers, createOpportunity } from '@/lib/trace/customerDiscoveryService'
import { canTransition, transition } from '@/lib/trace/executionStateMachine'
import { attioStatus } from '@/lib/trace/integrations/attioClient'
import { tavilyStatus } from '@/lib/trace/integrations/tavilyClient'
import { n8nStatus } from '@/lib/trace/integrations/n8nClient'
import { superlinkedStatus } from '@/lib/trace/integrations/superlinkedClient'
import { mubitStatus } from '@/lib/trace/integrations/mubitClient'
import { geminiStatus } from '@/lib/trace/integrations/geminiClient'

// ── 1. Health — store initialises with mock data ──────────────────────────────

describe('TraceStore', () => {
  test('store is seeded with at least 3 mock issues', () => {
    const issues = store.getIssues()
    expect(issues.length).toBeGreaterThanOrEqual(3)
  })

  test('store is seeded with at least 3 audit events', () => {
    const events = store.getAudit()
    expect(events.length).toBeGreaterThanOrEqual(3)
  })

  test('store is seeded with at least 3 customer leads', () => {
    const leads = store.getLeads()
    expect(leads.length).toBeGreaterThanOrEqual(3)
  })
})

// ── 2. Issue list returns at least 3 issues ───────────────────────────────────

describe('Issues', () => {
  test('getIssues returns at least 3 issues', () => {
    const issues = store.getIssues()
    expect(issues.length).toBeGreaterThanOrEqual(3)
  })

  test('issues include gate and detection types', () => {
    const issues = store.getIssues()
    const types = new Set(issues.map(i => i.type))
    expect(types.has('gate')).toBe(true)
    expect(types.has('detection')).toBe(true)
  })

  test('getIssue returns the correct issue by id', () => {
    const issue = store.getIssue('issue_001')
    expect(issue).toBeDefined()
    expect(issue!.id).toBe('issue_001')
  })

  test('getIssue returns undefined for unknown id', () => {
    const issue = store.getIssue('not_an_issue')
    expect(issue).toBeUndefined()
  })
})

// ── 3. Plan generation returns required resources ─────────────────────────────

describe('riskPlanner', () => {
  test('generates a plan for a gate issue', () => {
    const issue = store.getIssue('issue_001')!
    const plan = generatePlan(issue)
    expect(plan.issue_id).toBe('issue_001')
    expect(plan.plan_id).toBeDefined()
    expect(plan.required_resources.length).toBeGreaterThan(0)
    expect(plan.required_permissions.length).toBeGreaterThan(0)
    expect(plan.dusk_action).toBeDefined()
    expect(plan.approval_required).toBe(true)
  })

  test('generates a plan for a detection issue', () => {
    const issue = store.getIssue('issue_003')!
    const plan = generatePlan(issue)
    expect(plan.issue_id).toBe('issue_003')
    expect(plan.required_resources).toContain('engineering_time')
  })

  test('plan includes backend_action pointing to /api/security/fix', () => {
    const issue = store.getIssue('issue_001')!
    const plan = generatePlan(issue)
    expect(plan.backend_action).toBe('POST /api/security/fix')
  })

  test('plan includes rollback_plan', () => {
    const issue = store.getIssue('issue_002')!
    const plan = generatePlan(issue)
    expect(plan.rollback_plan.length).toBeGreaterThan(10)
  })
})

// ── 4. Fix execution without approval returns needs_manual_review ──────────────

describe('fixExecutor — needs_manual_review', () => {
  test('returns needs_manual_review when approval is missing for required plan', () => {
    // Seed a plan with approval_required=true for issue_001
    store.upsertPlan({
      issue_id: 'issue_001',
      plan_id: 'plan_test_001',
      dusk_action: 'enforce_block',
      fix_type: 'restrict_tool_and_attach_policy',
      recommended_fix: 'Test fix',
      required_permissions: ['agent_workflow_write'],
      required_resources: ['engineering_time'],
      approval_required: true,
      rollback_plan: 'Revert',
      risk_before_fix: 'critical',
      risk_after_fix: 'low',
      backend_action: 'POST /api/security/fix',
      n8n_soar_trigger: false,
      estimated_time: '30 minutes',
    })

    const result = executeFix({ issue_id: 'issue_001' })
    expect(result.status).toBe('needs_manual_review')
    expect(result.logs.some(l => l.includes('BLOCKED'))).toBe(true)
  })

  test('returns needs_manual_review for unknown issue', () => {
    const result = executeFix({ issue_id: 'unknown_issue' })
    expect(result.status).toBe('needs_manual_review')
  })
})

// ── 5. Approval decision updates status ───────────────────────────────────────

describe('Approval flow', () => {
  test('upsertApproval stores and retrieves approval', () => {
    const approval = {
      approval_id: 'approval_test_001',
      issue_id: 'issue_002',
      requested_by: 'manager@example.com',
      approved_by: null,
      decision: null,
      notes: '',
      created_at: new Date().toISOString(),
      decided_at: null,
    }
    store.upsertApproval(approval)
    const retrieved = store.getApproval('approval_test_001')
    expect(retrieved).toBeDefined()
    expect(retrieved!.decision).toBeNull()

    // Simulate decision
    const decided = { ...approval, decision: 'approved' as const, approved_by: 'cto@example.com', decided_at: new Date().toISOString() }
    store.upsertApproval(decided)
    const final = store.getApproval('approval_test_001')
    expect(final!.decision).toBe('approved')
    expect(final!.approved_by).toBe('cto@example.com')
  })
})

// ── 6. Fix execution after approval returns fixed ─────────────────────────────

describe('fixExecutor — fixed', () => {
  test('returns fixed when approval is provided', () => {
    // Seed a plan that requires approval for issue_004
    const issue = store.getIssue('issue_004')!
    const plan = generatePlan(issue)
    store.upsertPlan(plan)

    const result = executeFix({
      issue_id: 'issue_004',
      plan_id: plan.plan_id,
      approved_by: 'manager@example.com',
      resources: plan.required_resources,
    })

    expect(result.status).toBe('fixed')
    expect(result.logs.length).toBeGreaterThan(0)
    expect(result.logs.some(l => l.includes('DEMO'))).toBe(true)
    expect(result.risk_after_fix).toBeDefined()
  })

  test('fix logs include execution started and completed', () => {
    const issue = store.getIssue('issue_005')!
    const plan = generatePlan(issue)
    store.upsertPlan(plan)

    const result = executeFix({
      issue_id: 'issue_005',
      plan_id: plan.plan_id,
      approved_by: 'manager@example.com',
      resources: ['engineering_time'],
    })

    expect(result.status).toBe('fixed')
    expect(result.logs.some(l => l.toLowerCase().includes('started'))).toBe(true)
    expect(result.logs.some(l => l.toLowerCase().includes('completed'))).toBe(true)
  })
})

// ── 7. Audit event is recorded ────────────────────────────────────────────────

describe('auditService', () => {
  test('writeAudit creates an event with id and timestamp', () => {
    const event = writeAudit('plan_generated', 'Test plan generated', 'test_actor', {
      issue_id: 'issue_001',
    })
    expect(event.id).toBeDefined()
    expect(event.timestamp).toBeDefined()
    expect(event.event_type).toBe('plan_generated')
    expect(event.actor).toBe('test_actor')
  })

  test('getAudit returns all events', () => {
    const events = getAudit()
    expect(events.length).toBeGreaterThan(0)
  })

  test('getAudit filters by issue_id', () => {
    writeAudit('issue_selected', 'Issue selected', 'frontend', { issue_id: 'filter_test_issue' })
    const filtered = getAudit('filter_test_issue')
    expect(filtered.length).toBeGreaterThan(0)
    filtered.forEach(e => expect(e.issue_id).toBe('filter_test_issue'))
  })
})

// ── 8. Deployment prepare returns generated config ────────────────────────────

describe('deploymentService', () => {
  test('prepareDeployment returns a deployment package with generated_config', () => {
    const pkg = prepareDeployment({
      company: 'Acme AI Ops',
      agent_workflow_url: 'https://example.com/workflow',
      api_access_type: 'read-only',
      database_type: 'postgres',
      tool_list: ['send_email', 'read_contacts'],
      manager_email: 'manager@acme.com',
      allowed_actions: ['read_contacts'],
      blocked_actions: ['export_contacts'],
      test_environment_url: 'https://staging.example.com',
      deployment_mode: 'shadow_monitoring',
    })

    expect(pkg.deployment_id).toBeDefined()
    expect(pkg.company).toBe('Acme AI Ops')
    expect(pkg.status).toBe('ready_for_manager_approval')
    expect(pkg.generated_config).toBeDefined()
    expect(pkg.generated_config.allowed_actions).toContain('read_contacts')
    expect(pkg.generated_config.blocked_actions).toContain('export_contacts')
    expect(pkg.connector_instructions.length).toBeGreaterThan(0)
    expect(pkg.required_permissions.length).toBeGreaterThan(0)
  })

  test('active_self_healing mode requires more permissions than shadow_monitoring', () => {
    const shadow = prepareDeployment({
      company: 'Test Co',
      agent_workflow_url: '',
      api_access_type: 'read-only',
      database_type: 'postgres',
      tool_list: [],
      manager_email: '',
      allowed_actions: [],
      blocked_actions: [],
      test_environment_url: '',
      deployment_mode: 'shadow_monitoring',
    })

    const active = prepareDeployment({
      company: 'Test Co',
      agent_workflow_url: '',
      api_access_type: 'read-write',
      database_type: 'postgres',
      tool_list: [],
      manager_email: '',
      allowed_actions: [],
      blocked_actions: [],
      test_environment_url: '',
      deployment_mode: 'active_self_healing',
    })

    expect(active.required_permissions.length).toBeGreaterThan(shadow.required_permissions.length)
  })
})

// ── 9. Customer discovery returns mock leads ───────────────────────────────────

describe('customerDiscoveryService', () => {
  test('discoverCustomers returns at least 3 leads', () => {
    const leads = discoverCustomers()
    expect(leads.length).toBeGreaterThanOrEqual(3)
  })

  test('leads have fit_score and suggested_pitch', () => {
    const leads = discoverCustomers()
    leads.forEach(lead => {
      expect(lead.fit_score).toBeGreaterThan(0)
      expect(lead.suggested_pitch.length).toBeGreaterThan(0)
    })
  })

  test('createOpportunity returns success for known lead', () => {
    const result = createOpportunity('lead_001')
    expect(result.success).toBe(true)
    expect(result.attio_record_id).toBeDefined()
  })

  test('createOpportunity returns error for unknown lead', () => {
    const result = createOpportunity('not_a_lead')
    expect(result.success).toBe(false)
  })
})

// ── 10. Integration endpoints return demo_mode when keys missing ──────────────

describe('Integration status (no API keys in test env)', () => {
  test('attio returns demo_mode when ATTIO_API_KEY is not set', () => {
    delete process.env.ATTIO_API_KEY
    delete process.env.ATTIO_WORKSPACE_ID
    expect(attioStatus()).toBe('demo_mode')
  })

  test('tavily returns demo_mode when TAVILY_API_KEY is not set', () => {
    delete process.env.TAVILY_API_KEY
    expect(tavilyStatus()).toBe('demo_mode')
  })

  test('n8n returns demo_mode when N8N_WEBHOOK_URL is not set', () => {
    delete process.env.N8N_WEBHOOK_URL
    expect(n8nStatus()).toBe('demo_mode')
  })

  test('superlinked returns demo_mode when keys are not set', () => {
    delete process.env.SUPERLINKED_API_KEY
    delete process.env.SUPERLINKED_ENDPOINT
    expect(superlinkedStatus()).toBe('demo_mode')
  })

  test('mubit returns demo_mode when MUBIT_API_KEY is not set', () => {
    delete process.env.MUBIT_API_KEY
    expect(mubitStatus()).toBe('demo_mode')
  })

  test('gemini returns demo_mode when GEMINI_API_KEY is not set', () => {
    delete process.env.GEMINI_API_KEY
    expect(geminiStatus()).toBe('demo_mode')
  })
})

// ── 11. Integration status endpoint covers all sponsors ───────────────────────

describe('All integration statuses are known values', () => {
  const VALID = ['live', 'demo_mode', 'screenshot_present', 'screenshot_required']

  test('attio status is a valid value', () => {
    expect(VALID).toContain(attioStatus())
  })

  test('tavily status is a valid value', () => {
    expect(VALID).toContain(tavilyStatus())
  })

  test('n8n status is a valid value', () => {
    expect(VALID).toContain(n8nStatus())
  })

  test('superlinked status is a valid value', () => {
    expect(VALID).toContain(superlinkedStatus())
  })

  test('mubit status is a valid value', () => {
    expect(VALID).toContain(mubitStatus())
  })

  test('gemini status is a valid value', () => {
    expect(VALID).toContain(geminiStatus())
  })
})

// ── Bonus: Execution state machine ────────────────────────────────────────────

describe('executionStateMachine', () => {
  test('can transition from detected to planned', () => {
    expect(canTransition('detected', 'planned')).toBe(true)
  })

  test('cannot transition from fixed to executing', () => {
    expect(canTransition('fixed', 'executing')).toBe(false)
  })

  test('transition returns ok for valid transitions', () => {
    const result = transition('planned', 'approval_requested')
    expect(result.ok).toBe(true)
  })

  test('transition returns error for invalid transitions', () => {
    const result = transition('fixed', 'executing')
    expect(result.ok).toBe(false)
    if (!result.ok) {
      expect(result.error).toContain("Cannot transition")
    }
  })
})
