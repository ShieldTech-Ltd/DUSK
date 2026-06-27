/**
 * Trace × DUSK Backend API Client
 *
 * Calls the Next.js API routes at /api/... (same server when no BASE_URL is set)
 * or an external backend when NEXT_PUBLIC_BACKEND_API_URL is configured.
 *
 * The API route handlers contain all mock/live decision logic — this client
 * is always thin: just HTTP, types, and error handling.
 *
 * SECURITY: never put real secrets here. All secrets live server-side.
 */

// Re-export types from mock data files so existing component imports stay unchanged
export type { Customer } from '@/data/mockCustomers'
export type { SecurityIssue, GateIssue, DetectionIssue } from '@/data/mockIssues'
export type { ExecutionPlan } from '@/data/mockExecutionPlans'
export type { AuditEvent } from '@/data/mockAuditTrail'

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL ?? ''

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  // Relative URL when BASE_URL is empty → calls Next.js API routes on the same server
  const url = BASE_URL ? `${BASE_URL}${path}` : path
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

// ── Health ────────────────────────────────────────────────────────────────────

export async function getHealth(): Promise<{
  service: string
  status: string
  mode: string
}> {
  return apiFetch('/api/trace/health')
}

export async function getIntegrationStatus(): Promise<{
  attio: string
  tavily: string
  n8n: string
  superlinked: string
  mubit: string
  gemini: string
  aikido: string
}> {
  return apiFetch('/api/trace/integration-status')
}

// ── Customer discovery ────────────────────────────────────────────────────────

import type { Customer } from '@/data/mockCustomers'

export async function getCustomerLeads(): Promise<Customer[]> {
  return apiFetch<Customer[]>('/api/customers/discover')
}

export async function discoverCustomers(query?: string): Promise<Customer[]> {
  return apiFetch<Customer[]>('/api/customers/discover', {
    method: 'POST',
    body: JSON.stringify({ query }),
  })
}

export async function createAttioOpportunity(
  leadId: string
): Promise<{ success: boolean; attio_record_id?: string; message: string }> {
  return apiFetch('/api/customers/create-opportunity', {
    method: 'POST',
    body: JSON.stringify({ lead_id: leadId }),
  })
}

export async function createOpportunity(
  leadId: string
): Promise<{ success: boolean; attio_record_id?: string; message: string }> {
  return createAttioOpportunity(leadId)
}

// ── Security issues ───────────────────────────────────────────────────────────

import type { SecurityIssue } from '@/data/mockIssues'

export async function getSecurityIssues(): Promise<SecurityIssue[]> {
  return apiFetch<SecurityIssue[]>('/api/security/issues')
}

export async function getSecurityIssueDetail(issueId: string): Promise<SecurityIssue> {
  return apiFetch<SecurityIssue>(`/api/security/issues/${issueId}`)
}

// When NEXT_PUBLIC_BACKEND_API_URL is set, these call the dedicated backend routes
// (GET /api/dusk/gate-verdicts and GET /api/dusk/alerts) which return real DUSK
// gate verdicts from ActionGate and AlertResponder respectively.
// When the env var is empty, they fall through to the local Next.js routes.
export async function getDuskGateVerdicts(): Promise<SecurityIssue[]> {
  if (BASE_URL) {
    return apiFetch<SecurityIssue[]>('/api/dusk/gate-verdicts')
  }
  const issues = await getSecurityIssues()
  return issues.filter(i => i.type === 'gate')
}

export async function getDuskAlerts(): Promise<SecurityIssue[]> {
  if (BASE_URL) {
    return apiFetch<SecurityIssue[]>('/api/dusk/alerts')
  }
  const issues = await getSecurityIssues()
  return issues.filter(i => i.type === 'detection')
}

// ── Tavily threat enrichment ──────────────────────────────────────────────────

export interface TavilyEnrichment {
  query: string
  summary?: string
  results: { title: string; url: string; content: string }[]
  sources: string[]
}

export async function getTavilyEnrichment(
  agentId: string,
  actionType: string,
  mitreId: string
): Promise<TavilyEnrichment> {
  // When live backend is set, call the dedicated /api/dusk/tavily-enrichment route
  // which calls Python enrich_alert() when TAVILY_API_KEY is present.
  const path = BASE_URL ? '/api/dusk/tavily-enrichment' : '/api/integrations/tavily/research'

  const result = await apiFetch<{
    query: string
    summary?: string
    sources: { title: string; url: string; snippet: string }[]
    enrichment?: { query: string; summary?: string; sources: { title: string; url: string; snippet: string }[] }
    mode?: string
  }>(path, {
    method: 'POST',
    body: JSON.stringify({ agent_id: agentId, action_type: actionType, mitre_id: mitreId }),
  })

  // Direct backend response (mode field present) or Next.js wrapped response
  const data = result.enrichment ?? result
  return {
    query: data.query,
    summary: data.summary,
    results: (data.sources ?? []).map(s => ({
      title: s.title,
      url: s.url,
      content: s.snippet,
    })),
    sources: (data.sources ?? []).map(s => s.url),
  }
}

// ── Fix planning ──────────────────────────────────────────────────────────────

import type { ExecutionPlan } from '@/data/mockExecutionPlans'

export async function generateSecurityPlan(issueId: string): Promise<ExecutionPlan> {
  return apiFetch<ExecutionPlan>('/api/security/plan', {
    method: 'POST',
    body: JSON.stringify({ issue_id: issueId }),
  })
}

// ── Approval flow ─────────────────────────────────────────────────────────────

export async function requestApproval(payload: {
  issue_id: string
  execution_id?: string
  requested_by?: string
  notes?: string
}): Promise<{
  approval_id: string
  issue_id: string
  decision: string | null
  created_at: string
}> {
  return apiFetch('/api/security/approvals', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function submitApprovalDecision(
  approvalId: string,
  payload: {
    decision: 'approved' | 'rejected' | 'needs_more_info'
    approved_by?: string
    notes?: string
  }
): Promise<{
  approval_id: string
  decision: string
  decided_at: string
}> {
  return apiFetch(`/api/security/approvals/${approvalId}/decision`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ── Fix execution ─────────────────────────────────────────────────────────────

export interface FixPayload {
  issue_id: string
  plan_id?: string
  approved_by?: string
  resources?: string[]
  action_plan?: string
  dusk_action?: string
}

export interface FixResult {
  execution_id: string
  status: 'fixed' | 'planned' | 'failed' | 'needs_manual_review'
  message: string
  logs: string[]
  risk_after_fix?: string
}

export async function executeSecurityFix(payload: FixPayload): Promise<FixResult> {
  return apiFetch<FixResult>('/api/security/fix', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getExecutionStatus(executionId: string): Promise<FixResult> {
  return apiFetch<FixResult>(`/api/security/executions/${executionId}`)
}

// ── n8n SOAR integration ──────────────────────────────────────────────────────

export async function triggerN8nWorkflow(payload: {
  customer_id?: string
  workflow?: string
  verdict?: string
  workflow_type?: string
  analysis?: {
    agent_id: string
    score: number
    mitre_attack: string
    blast_radius: string
  }
}): Promise<{ success: boolean; execution_id?: string; message: string }> {
  // When live backend is set, call /api/dusk/n8n-soar which uses Python fire_webhook()
  // with the real N8N_WEBHOOK_URL. Falls back to /api/integrations/n8n/trigger (Next.js).
  const path = BASE_URL ? '/api/dusk/n8n-soar' : '/api/integrations/n8n/trigger'

  const result = await apiFetch<{
    integration_status?: string
    mode?: string
    status: string
    message: string
    payload?: { workflow_run_id?: string }
  }>(path, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  const isLive = result.mode === 'live' || result.integration_status === 'live' || result.status.includes('triggered')
  return {
    success: isLive,
    execution_id: (result.payload as { workflow_run_id?: string } | undefined)?.workflow_run_id,
    message: result.message,
  }
}

// ── Audit trail ───────────────────────────────────────────────────────────────

import type { AuditEvent } from '@/data/mockAuditTrail'

export async function writeAuditEvent(
  payload: Omit<AuditEvent, 'id' | 'timestamp'>
): Promise<{ success: boolean; audit_id: string }> {
  const result = await apiFetch<AuditEvent>('/api/security/audit', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  return { success: true, audit_id: result.id }
}

export async function getAuditTrail(issueId?: string): Promise<AuditEvent[]> {
  const qs = issueId ? `?issue_id=${issueId}` : ''
  return apiFetch<AuditEvent[]>(`/api/security/audit${qs}`)
}

// ── Deployment ────────────────────────────────────────────────────────────────

export interface DeploymentConfig {
  company: string
  agent_workflow_url: string
  api_access_type: string
  database_type: string
  tool_list: string[]
  approval_manager_email: string
  allowed_actions: string[]
  blocked_actions: string[]
  test_environment_url: string
  deployment_mode: 'shadow_monitoring' | 'approval_gate' | 'active_self_healing'
}

export interface DeploymentPackage {
  deployment_id: string
  company: string
  mode: string
  required_permissions: string[]
  blocked_actions: string[]
  approval_required: boolean
  manager_email: string
  status: string
  generated_config?: {
    monitoring_mode: string
    approval_required: boolean
    allowed_actions: string[]
    blocked_actions: string[]
  }
  connector_instructions?: string[]
}

export async function prepareDeployment(config: DeploymentConfig): Promise<DeploymentPackage> {
  return apiFetch<DeploymentPackage>('/api/deployment/prepare', {
    method: 'POST',
    body: JSON.stringify({
      ...config,
      manager_email: config.approval_manager_email,
    }),
  })
}

export async function registerDeployment(
  deploymentId: string
): Promise<{ success: boolean; message: string }> {
  const result = await apiFetch<DeploymentPackage>('/api/deployment/register', {
    method: 'POST',
    body: JSON.stringify({ deployment_id: deploymentId }),
  })
  return {
    success: result.status === 'registered',
    message: `Deployment ${deploymentId} registered successfully.`,
  }
}

// ── Sponsor integrations ──────────────────────────────────────────────────────

export async function syncAttio(payload: {
  object_type: 'company' | 'opportunity' | 'execution' | 'deployment'
  [key: string]: unknown
}): Promise<{ integration_status: string; message: string }> {
  return apiFetch('/api/integrations/attio/sync', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
