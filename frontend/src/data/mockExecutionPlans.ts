/**
 * Mock execution plans for DUSK gate verdicts and detection alerts.
 *
 * Each plan maps to a SecurityIssue id and describes the recommended fix,
 * required resources and what the backend action will do.
 *
 * In DUSK terms, "fixing" a gate verdict means:
 *   - Updating the baseline to retrain on legitimate actions
 *   - Enforcing a block policy for the specific agent/action pair
 *   - Rotating credentials if a role escalation was attempted
 *   - Triggering a Tavily threat intel search for the MITRE technique
 *   - Notifying the SOAR via n8n webhook
 */

export interface ExecutionPlan {
  issue_id: string
  recommended_fix: string
  dusk_action: 'add_to_baseline' | 'enforce_block' | 'rotate_credentials' | 'isolate_agent'
  required_permissions: string[]
  required_resources: string[]
  backend_action: string
  rollback_plan: string
  risk_after_fix: 'low' | 'medium' | 'high'
  approval_required: boolean
  estimated_time: string
  tavily_enrichment_query?: string
  n8n_soar_trigger: boolean
}

export const mockExecutionPlans: Record<string, ExecutionPlan> = {
  issue_001: {
    issue_id: 'issue_001',
    recommended_fix:
      'Add legitimate firewall rule changes to the agent baseline if they are expected, or enforce a hard block policy for sales-agent-v2 on firewall_rule_change actions. Revert the specific rule change and review the 0.0.0.0/0 exposure.',
    dusk_action: 'enforce_block',
    required_permissions: ['agent_workflow_write', 'policy_update', 'firewall_admin'],
    required_resources: ['engineering_time', 'test_environment', 'security_team_review'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Restore the previous firewall rule and revert the agent baseline update if it causes legitimate workflow disruption.',
    risk_after_fix: 'low',
    approval_required: true,
    estimated_time: '30 minutes',
    tavily_enrichment_query: 'T1562.004 firewall rule change LLM agent threat 2026',
    n8n_soar_trigger: true,
  },
  issue_002: {
    issue_id: 'issue_002',
    recommended_fix:
      'Immediately revoke the role assignment. Rotate the agent credentials. Enforce a hard BLOCK on role_assignment actions for finance-bot-01. Audit all actions taken with the escalated privileges.',
    dusk_action: 'rotate_credentials',
    required_permissions: ['iam_admin', 'agent_workflow_write', 'audit_log_read'],
    required_resources: ['engineering_time', 'security_team_review', 'identity_team'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Restore previous role assignment and original agent credentials if rotation causes workflow failure.',
    risk_after_fix: 'low',
    approval_required: true,
    estimated_time: '45 minutes',
    tavily_enrichment_query: 'T1098 account manipulation LLM privilege escalation 2026',
    n8n_soar_trigger: true,
  },
  issue_003: {
    issue_id: 'issue_003',
    recommended_fix:
      'Isolate 10.2.4.17 from further outbound connections. Review the agent or process on that host. Apply the DUSK sweep detection in enforce mode for this source. Trigger Tavily external threat research for T1046.',
    dusk_action: 'isolate_agent',
    required_permissions: ['network_admin', 'firewall_write'],
    required_resources: ['engineering_time', 'network_team'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Re-allow 10.2.4.17 network access if isolation causes legitimate service disruption after investigation.',
    risk_after_fix: 'medium',
    approval_required: true,
    estimated_time: '20 minutes',
    tavily_enrichment_query: 'T1046 network service discovery agent reconnaissance 2026',
    n8n_soar_trigger: true,
  },
  issue_004: {
    issue_id: 'issue_004',
    recommended_fix:
      'Update the crm-sync-agent baseline to include route_change if this action is legitimate, or enforce a block for this agent on route_change. Verify the BGP route change was intentional with the network team.',
    dusk_action: 'add_to_baseline',
    required_permissions: ['agent_workflow_write', 'network_admin'],
    required_resources: ['engineering_time', 'network_team'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Revert the BGP route change to the previous state if the baseline update causes network disruption.',
    risk_after_fix: 'low',
    approval_required: false,
    estimated_time: '15 minutes',
    tavily_enrichment_query: 'T1599 network boundary bridging BGP route manipulation 2026',
    n8n_soar_trigger: false,
  },
  issue_005: {
    issue_id: 'issue_005',
    recommended_fix:
      'Isolate 192.168.10.44 and review east-west traffic logs. Contain the host before exfiltration begins. Trigger the DUSK lateral movement response playbook via n8n SOAR integration.',
    dusk_action: 'isolate_agent',
    required_permissions: ['network_admin', 'firewall_write', 'siem_access'],
    required_resources: ['engineering_time', 'network_team', 'security_team_review'],
    backend_action: 'POST /api/security/fix',
    rollback_plan: 'Re-allow connectivity for 192.168.10.44 if investigation confirms the host is clean.',
    risk_after_fix: 'medium',
    approval_required: true,
    estimated_time: '1 hour',
    tavily_enrichment_query: 'T1021 lateral movement remote services agent compromise 2026',
    n8n_soar_trigger: true,
  },
}
