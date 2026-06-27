export interface ExecutionPlan {
  issue_id: string
  recommended_fix: string
  required_permissions: string[]
  required_resources: string[]
  backend_action: string
  rollback_plan: string
  risk_after_fix: string
  approval_required: boolean
  estimated_time: string
}

export const mockExecutionPlans: Record<string, ExecutionPlan> = {
  issue_001: {
    issue_id: 'issue_001',
    recommended_fix:
      'Disable external email tool until approval policy is attached. Block all agent actions that reference injected external content.',
    required_permissions: ['agent_workflow_write', 'policy_update'],
    required_resources: ['engineering_time', 'test_environment'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Re-enable previous workflow version if fix fails',
    risk_after_fix: 'low',
    approval_required: true,
    estimated_time: '30 minutes',
  },
  issue_002: {
    issue_id: 'issue_002',
    recommended_fix:
      'Rotate API key and create a minimal-permission key scoped to read-only operations required by the workflow.',
    required_permissions: ['api_key_management', 'workflow_update'],
    required_resources: ['engineering_time', 'api_access'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Restore previous API key if rotated key causes workflow failure',
    risk_after_fix: 'low',
    approval_required: true,
    estimated_time: '15 minutes',
  },
  issue_003: {
    issue_id: 'issue_003',
    recommended_fix:
      'Remove database write permissions from agent role. Add approval gate that requires manager sign-off before any write operation.',
    required_permissions: ['database_schema_access', 'policy_update'],
    required_resources: ['engineering_time', 'database_schema_access'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Restore previous database permissions if approval gate breaks workflow',
    risk_after_fix: 'medium',
    approval_required: true,
    estimated_time: '45 minutes',
  },
  issue_004: {
    issue_id: 'issue_004',
    recommended_fix:
      'Immediately suspend agent workflow. Block all outbound HTTP calls not on the approved domain allowlist.',
    required_permissions: ['agent_workflow_write', 'network_policy_update'],
    required_resources: ['engineering_time', 'test_environment', 'security_team_review'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Restore agent workflow from last known-good snapshot',
    risk_after_fix: 'low',
    approval_required: true,
    estimated_time: '2 hours',
  },
  issue_005: {
    issue_id: 'issue_005',
    recommended_fix:
      'Add time-window enforcement to email tool. Emails outside business hours require explicit manager approval via n8n workflow.',
    required_permissions: ['email_tool_config', 'policy_update'],
    required_resources: ['engineering_time'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Disable time-window enforcement if it blocks legitimate workflows',
    risk_after_fix: 'low',
    approval_required: false,
    estimated_time: '20 minutes',
  },
}
