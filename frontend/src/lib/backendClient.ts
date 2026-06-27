/**
 * Trace × DUSK Backend API Client
 *
 * All functions use NEXT_PUBLIC_BACKEND_API_URL when set and fall back to
 * mock data when the backend is unavailable — so the demo always works.
 *
 * API shapes match the real DUSK backend schemas:
 *   - GateVerdict: verdict (ALLOW|WOULD-BLOCK|BLOCK), score, mitre_attack,
 *     mitre_atlas, blast_radius, predicted_next, reasons
 *   - DetectionAlert: detection, source, mitre, stage, confidence, reason,
 *     prediction  (written to dusk-alerts.json by AlertResponder)
 *   - n8n webhook payload: { verdict, analysis: { agent_id, score, ... } }
 *   - Tavily enrichment: enrich_alert(agent_id, action_type, mitre_id)
 *
 * SECURITY: never put real secrets here. Use environment variables only.
 */

import { mockCustomers, type Customer } from '@/data/mockCustomers'
import { mockIssues, type SecurityIssue } from '@/data/mockIssues'
import { mockExecutionPlans, type ExecutionPlan } from '@/data/mockExecutionPlans'
import { initialAuditTrail, type AuditEvent } from '@/data/mockAuditTrail'

const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL ?? ''
const isMockMode = !BASE_URL

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`)
  return res.json() as Promise<T>
}

// ── Customer discovery ────────────────────────────────────────────────────────

export async function getCustomerLeads(): Promise<Customer[]> {
  if (isMockMode) return mockCustomers
  return apiFetch<Customer[]>('/api/customers/leads')
}

export async function createAttioOpportunity(
  customerId: string
): Promise<{ success: boolean; attio_record_id?: string; message: string }> {
  if (isMockMode) {
    return {
      success: true,
      attio_record_id: `attio_${customerId}_${Date.now()}`,
      message: 'Demo mode: Attio company and opportunity payload generated.',
    }
  }
  return apiFetch('/api/crm/attio/opportunity', {
    method: 'POST',
    body: JSON.stringify({ customer_id: customerId }),
  })
}

// ── DUSK gate verdicts and detection alerts ───────────────────────────────────

export async function getSecurityIssues(): Promise<SecurityIssue[]> {
  if (isMockMode) return mockIssues
  // Real backend: GET /api/security/issues returns merged gate verdicts + alerts
  return apiFetch<SecurityIssue[]>('/api/security/issues')
}

export async function getSecurityIssueDetail(issueId: string): Promise<SecurityIssue> {
  if (isMockMode) {
    const issue = mockIssues.find((i) => i.id === issueId)
    if (!issue) throw new Error(`Issue ${issueId} not found`)
    return issue
  }
  return apiFetch<SecurityIssue>(`/api/security/issues/${issueId}`)
}

/**
 * Fetch raw DUSK gate verdicts from the real backend.
 * Schema: GateVerdict.to_dict() — { verdict, agent_id, action_type, target,
 * score, reasons, mitre_attack, mitre_atlas, blast_radius, predicted_next }
 */
export async function getDuskGateVerdicts(): Promise<SecurityIssue[]> {
  if (isMockMode) return mockIssues.filter((i) => i.type === 'gate')
  return apiFetch<SecurityIssue[]>('/api/security/gate/verdicts')
}

/**
 * Fetch DUSK network detection alerts from dusk-alerts.json via the API.
 * Schema: AlertResponder._persist() — { timestamp, detection, source, mitre,
 * stage, confidence, reason, prediction }
 */
export async function getDuskAlerts(): Promise<SecurityIssue[]> {
  if (isMockMode) return mockIssues.filter((i) => i.type === 'detection')
  return apiFetch<SecurityIssue[]>('/api/security/alerts')
}

// ── Tavily threat enrichment ──────────────────────────────────────────────────

export interface TavilyEnrichment {
  query: string
  results: { title: string; url: string; content: string }[]
  sources: string[]
}

/**
 * Calls the DUSK Tavily enrichment backend which wraps TavilyClient.search().
 * Backend function: enrich_alert(agent_id, action_type, mitre_id)
 * Query pattern: "{mitre_id} {action_type} threat actor technique 2026"
 */
export async function getTavilyEnrichment(
  agentId: string,
  actionType: string,
  mitreId: string
): Promise<TavilyEnrichment> {
  if (isMockMode) {
    const query = `${mitreId} ${actionType} threat actor technique 2026`
    return {
      query,
      results: [
        {
          title: `${mitreId} — MITRE ATT&CK Technique Analysis`,
          url: `https://attack.mitre.org/techniques/${mitreId.split(' ')[0].replace('.', '/')}/`,
          content: `Threat actors use ${actionType} to ${mitreId.toLowerCase()}. Commonly observed in APT campaigns targeting AI agent infrastructure.`,
        },
        {
          title: `${actionType} threat intel — 2026 threat landscape`,
          url: `https://www.crowdstrike.com/adversary-intelligence/${actionType}/`,
          content: `Recent campaigns by threat actors targeting agent ${agentId} workflow types via ${actionType}. Observed blast radius: high.`,
        },
      ],
      sources: [
        `https://attack.mitre.org/techniques/${mitreId.split(' ')[0].replace('.', '/')}/`,
        `https://www.crowdstrike.com/adversary-intelligence/`,
      ],
    }
  }
  return apiFetch<TavilyEnrichment>('/api/security/enrich', {
    method: 'POST',
    body: JSON.stringify({ agent_id: agentId, action_type: actionType, mitre_id: mitreId }),
  })
}

// ── Fix planning ──────────────────────────────────────────────────────────────

export async function generateSecurityPlan(issueId: string): Promise<ExecutionPlan> {
  if (isMockMode) {
    const plan = mockExecutionPlans[issueId]
    if (!plan) throw new Error(`No plan for issue ${issueId}`)
    return plan
  }
  return apiFetch<ExecutionPlan>('/api/security/plan', {
    method: 'POST',
    body: JSON.stringify({ issue_id: issueId }),
  })
}

// ── Fix execution ─────────────────────────────────────────────────────────────

export interface FixPayload {
  issue_id: string
  approved_by: string
  resources: string[]
  action_plan: string
  dusk_action?: string
}

export interface FixResult {
  execution_id: string
  status: 'fixed' | 'pending' | 'failed' | 'needs_manual_review'
  message: string
  logs: string[]
}

export async function executeSecurityFix(payload: FixPayload): Promise<FixResult> {
  if (isMockMode) {
    const issue = mockIssues.find((i) => i.id === payload.issue_id)
    const plan = mockExecutionPlans[payload.issue_id]
    const duskAction = plan?.dusk_action ?? 'enforce_block'
    return {
      execution_id: `exec_${payload.issue_id}_${Date.now()}`,
      status: 'fixed',
      message: `DUSK action '${duskAction}' applied successfully`,
      logs: [
        `DUSK gate policy updated for ${issue?.type === 'gate' ? (issue as {agent_id: string}).agent_id : 'detected host'}`,
        duskAction === 'add_to_baseline'
          ? 'Agent baseline updated with legitimate action pattern'
          : duskAction === 'rotate_credentials'
          ? 'Agent credentials rotated and previous credentials revoked'
          : duskAction === 'isolate_agent'
          ? 'Agent/host isolated from further network connections'
          : 'Hard block policy enforced for agent/action pair',
        `Tavily threat intel query triggered for ${plan?.tavily_enrichment_query ?? 'MITRE technique'}`,
        ...(plan?.n8n_soar_trigger
          ? ['n8n SOAR workflow triggered — DUSK alert sent to incident tracker']
          : []),
        'Attio customer security record updated',
        'Audit event written to dusk-alerts.json',
      ],
    }
  }
  return apiFetch<FixResult>('/api/security/fix', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ── n8n SOAR integration ──────────────────────────────────────────────────────

/**
 * Triggers the real DUSK n8n SOAR workflow.
 * Payload schema from demo/n8n_workflow.json:
 *   POST <N8N_WEBHOOK_URL>/webhook/dusk-alert
 *   Body: { verdict, analysis: { agent_id, score, mitre_attack, blast_radius } }
 */
export async function triggerN8nWorkflow(payload: {
  customer_id?: string
  workflow?: string
  verdict?: string
  analysis?: {
    agent_id: string
    score: number
    mitre_attack: string
    blast_radius: string
  }
}): Promise<{ success: boolean; execution_id?: string; message: string }> {
  if (isMockMode) {
    return {
      success: true,
      execution_id: `n8n_exec_${Date.now()}`,
      message: payload.verdict
        ? `Demo mode: DUSK alert (${payload.verdict}) sent to n8n SOAR — SOAR incident would be opened.`
        : 'Demo mode: n8n follow-up workflow triggered.',
    }
  }

  const n8nUrl = process.env.N8N_WEBHOOK_URL
  if (n8nUrl) {
    // Call real n8n webhook directly (server-side only in production)
    const res = await fetch(`${n8nUrl}/webhook/dusk-alert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    const data = (await res.json()) as { received?: boolean; agent_id?: string }
    return {
      success: data.received === true,
      message: `n8n acknowledged: agent ${data.agent_id}`,
    }
  }

  return apiFetch('/api/workflows/n8n/trigger', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ── Audit trail ───────────────────────────────────────────────────────────────

export async function writeAuditEvent(
  payload: Omit<AuditEvent, 'id' | 'timestamp'>
): Promise<{ success: boolean; audit_id: string }> {
  if (isMockMode) return { success: true, audit_id: `audit_${Date.now()}` }
  return apiFetch('/api/security/audit', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function getAuditTrail(): Promise<AuditEvent[]> {
  if (isMockMode) return initialAuditTrail
  return apiFetch<AuditEvent[]>('/api/security/audit')
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
}

export async function prepareDeployment(config: DeploymentConfig): Promise<DeploymentPackage> {
  if (isMockMode) {
    return {
      deployment_id: `deploy_${Date.now()}`,
      company: config.company,
      mode: config.deployment_mode,
      required_permissions: [
        'read_agent_workflow',
        'read_api_schema',
        'read_database_schema',
        'create_policy_hook',
        'dusk_gate_integration',
      ],
      blocked_actions: config.blocked_actions.length
        ? config.blocked_actions
        : ['firewall_rule_change_unapproved', 'role_assignment_unapproved', 'route_change_unapproved'],
      approval_required: true,
      manager_email: config.approval_manager_email || 'manager@example.com',
      status: 'ready_for_manager_approval',
    }
  }
  return apiFetch<DeploymentPackage>('/api/deployment/prepare', {
    method: 'POST',
    body: JSON.stringify(config),
  })
}

export async function registerDeployment(
  deploymentId: string
): Promise<{ success: boolean; message: string }> {
  if (isMockMode) {
    return {
      success: true,
      message: 'Demo mode: DUSK gate connector registered. Agent actions will be evaluated against the baseline in shadow monitoring mode.',
    }
  }
  return apiFetch('/api/deployment/register', {
    method: 'POST',
    body: JSON.stringify({ deployment_id: deploymentId }),
  })
}
