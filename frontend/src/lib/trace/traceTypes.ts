/**
 * Trace Execution Layer — shared TypeScript types.
 *
 * Schemas are aligned with the real DUSK backend:
 *   GateIssue  ← ActionGate.evaluate() → GateVerdict.to_dict()
 *   DetectionIssue ← AlertResponder._persist() → dusk-alerts.json
 */

// ── Issue types ───────────────────────────────────────────────────────────────

export type Verdict = 'ALLOW' | 'WOULD-BLOCK' | 'BLOCK'
export type BlastRadius = 'low' | 'medium' | 'high'
export type KillChainStage = 'Reconnaissance' | 'LateralMovement' | 'Exfiltration'
export type IssueStatus = 'open' | 'in_review' | 'approved' | 'fixed'

export interface GateIssue {
  id: string
  type: 'gate'
  verdict: Verdict
  agent_id: string
  action_type: string
  target: string
  score: number
  reasons: string[]
  mitre_attack: string
  mitre_atlas: string
  blast_radius: BlastRadius
  predicted_next: string
  customer: string
  timestamp: string
  status: IssueStatus
}

export interface DetectionIssue {
  id: string
  type: 'detection'
  detection: string
  source_ip: string
  mitre: string
  stage: KillChainStage
  confidence: number
  reason: string
  prediction: string
  customer: string
  timestamp: string
  status: IssueStatus
}

export type TraceIssue = GateIssue | DetectionIssue

// ── Execution plan ────────────────────────────────────────────────────────────

export type DuskAction =
  | 'enforce_block'
  | 'rotate_credentials'
  | 'isolate_agent'
  | 'add_to_baseline'
  | 'restrict_tool_and_attach_policy'
  | 'rotate_api_key'
  | 'switch_to_readonly_policy'

export interface ExecutionPlan {
  issue_id: string
  plan_id: string
  dusk_action: DuskAction
  recommended_fix: string
  fix_type: string
  required_permissions: string[]
  required_resources: string[]
  approval_required: boolean
  rollback_plan: string
  risk_before_fix: 'critical' | 'high' | 'medium' | 'low'
  risk_after_fix: 'critical' | 'high' | 'medium' | 'low'
  backend_action: string
  tavily_enrichment_query?: string
  n8n_soar_trigger: boolean
  estimated_time: string
}

// ── Execution state machine ───────────────────────────────────────────────────

export type ExecutionStatus =
  | 'detected'
  | 'planned'
  | 'approval_requested'
  | 'approved'
  | 'resource_allocated'
  | 'executing'
  | 'fixed'
  | 'failed'
  | 'needs_manual_review'
  | 'rejected'

export interface Execution {
  execution_id: string
  issue_id: string
  plan_id?: string
  status: ExecutionStatus
  approved_by: string | null
  resources: string[]
  logs: string[]
  message: string
  risk_after_fix?: string
  created_at: string
  updated_at: string
}

// ── Approval ──────────────────────────────────────────────────────────────────

export type ApprovalDecision = 'approved' | 'rejected' | 'needs_more_info'

export interface Approval {
  approval_id: string
  issue_id: string
  execution_id?: string
  requested_by: string
  approved_by: string | null
  decision: ApprovalDecision | null
  notes: string
  created_at: string
  decided_at: string | null
}

// ── Audit trail ───────────────────────────────────────────────────────────────

export type AuditEventType =
  | 'issue_detected'
  | 'plan_generated'
  | 'approval_requested'
  | 'approval_decision'
  | 'resource_allocated'
  | 'fix_started'
  | 'fix_completed'
  | 'fix_failed'
  | 'deployment_prepared'
  | 'deployment_registered'
  | 'opportunity_created'
  | 'tavily_enrichment'
  | 'n8n_soar_triggered'
  | 'attio_synced'
  | 'issue_selected'

export interface AuditEvent {
  id: string
  timestamp: string
  event_type: AuditEventType
  description: string
  actor: string
  issue_id?: string
  execution_id?: string
  metadata?: Record<string, string>
}

// ── Deployment ────────────────────────────────────────────────────────────────

export type DeploymentMode = 'shadow_monitoring' | 'approval_gate' | 'active_self_healing'
export type DeploymentStatus =
  | 'ready_for_manager_approval'
  | 'approved'
  | 'registered'
  | 'active'

export interface DeploymentConfig {
  company: string
  agent_workflow_url: string
  api_access_type: string
  database_type: string
  tool_list: string[]
  manager_email: string
  allowed_actions: string[]
  blocked_actions: string[]
  test_environment_url: string
  deployment_mode: DeploymentMode
}

export interface DeploymentPackage {
  deployment_id: string
  company: string
  status: DeploymentStatus
  mode: DeploymentMode
  required_permissions: string[]
  blocked_actions: string[]
  approval_required: boolean
  manager_email: string
  generated_config: {
    monitoring_mode: string
    approval_required: boolean
    allowed_actions: string[]
    blocked_actions: string[]
  }
  connector_instructions: string[]
  attio_payload?: Record<string, unknown>
  created_at: string
}

// ── Customer lead ─────────────────────────────────────────────────────────────

export type LeadStatus =
  | 'ready_to_create_in_attio'
  | 'ready_to_review'
  | 'under_review'
  | 'created_in_attio'

export interface CustomerLead {
  id: string
  company: string
  use_case: string
  security_pain: string
  fit_score: number
  source: string
  suggested_pitch: string
  status: LeadStatus
}

// ── Integration status ────────────────────────────────────────────────────────

export type IntegrationStatus = 'live' | 'demo_mode' | 'failed' | 'not_configured'

export interface IntegrationResult {
  integration_status: IntegrationStatus
  status: string
  message: string
  payload?: unknown
}
