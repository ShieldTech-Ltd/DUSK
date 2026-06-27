/**
 * Trace Backend API Client
 *
 * Each function tries to call the real backend when NEXT_PUBLIC_BACKEND_API_URL is set.
 * Falls back to mock data so the demo works without a live backend.
 *
 * SECURITY: Never put real API keys in this file. Use environment variables only.
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
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
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

export async function triggerN8nWorkflow(payload: {
  customer_id: string
  workflow: string
}): Promise<{ success: boolean; execution_id?: string; message: string }> {
  if (isMockMode) {
    return {
      success: true,
      execution_id: `n8n_exec_${Date.now()}`,
      message: 'Demo mode: n8n follow-up workflow triggered.',
    }
  }
  return apiFetch('/api/workflows/n8n/trigger', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ── Security issues ───────────────────────────────────────────────────────────

export async function getSecurityIssues(): Promise<SecurityIssue[]> {
  if (isMockMode) return mockIssues
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
}

export interface FixResult {
  execution_id: string
  status: 'fixed' | 'pending' | 'failed' | 'needs_manual_review'
  message: string
  logs: string[]
}

export async function executeSecurityFix(payload: FixPayload): Promise<FixResult> {
  if (isMockMode) {
    return {
      execution_id: `exec_${payload.issue_id}_${Date.now()}`,
      status: 'fixed',
      message: 'Security policy attached and risky tool disabled',
      logs: [
        'Policy check created',
        'Risky tool access restricted',
        'Approval rule attached',
        'Attio audit record generated',
        'n8n post-fix notification triggered',
      ],
    }
  }
  return apiFetch<FixResult>('/api/security/fix', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

// ── Audit trail ───────────────────────────────────────────────────────────────

export async function writeAuditEvent(
  payload: Omit<AuditEvent, 'id' | 'timestamp'>
): Promise<{ success: boolean; audit_id: string }> {
  if (isMockMode) {
    return { success: true, audit_id: `audit_${Date.now()}` }
  }
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

export async function prepareDeployment(
  config: DeploymentConfig
): Promise<DeploymentPackage> {
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
      ],
      blocked_actions: config.blocked_actions.length
        ? config.blocked_actions
        : [
            'export_contacts',
            'send_external_email_without_approval',
            'database_write_without_policy',
          ],
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
      message: 'Demo mode: deployment package generated and ready for backend registration.',
    }
  }
  return apiFetch('/api/deployment/register', {
    method: 'POST',
    body: JSON.stringify({ deployment_id: deploymentId }),
  })
}
