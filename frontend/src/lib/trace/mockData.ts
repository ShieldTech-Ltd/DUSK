/**
 * Mock data aligned with real DUSK backend schemas.
 * Seeds the in-memory store on startup. Resets on server restart (MVP behavior).
 */

import type { TraceIssue, ExecutionPlan, AuditEvent, CustomerLead } from './traceTypes'

const H = (h: number) => new Date(Date.now() - h * 3_600_000).toISOString()

// ── Security issues ───────────────────────────────────────────────────────────

export const MOCK_ISSUES: TraceIssue[] = [
  {
    id: 'issue_001',
    type: 'gate',
    verdict: 'WOULD-BLOCK',
    agent_id: 'sales-agent-v2',
    action_type: 'firewall_rule_change',
    target: 'prod-firewall-rule-42',
    score: 0.85,
    reasons: [
      "action type 'firewall_rule_change' is new for this agent (normally: crm_read, send_email)",
      "introduces sensitive terms ['0.0.0.0/0']",
    ],
    mitre_attack: 'T1562.004 Impair Defenses: Disable or Modify System Firewall',
    mitre_atlas: 'AML.T0051 LLM Prompt Injection',
    blast_radius: 'high',
    predicted_next:
      'Expect lateral movement into newly reachable segment; watch east-west connections from this agent.',
    customer: 'Acme Ltd',
    timestamp: H(3),
    status: 'open',
  },
  {
    id: 'issue_002',
    type: 'gate',
    verdict: 'BLOCK',
    agent_id: 'finance-bot-01',
    action_type: 'role_assignment',
    target: 'admin-role/owner',
    score: 0.95,
    reasons: [
      "action type 'role_assignment' is new for this agent (normally: transaction_read)",
      "introduces privileged terms ['owner', 'admin']",
    ],
    mitre_attack: 'T1098 Account Manipulation',
    mitre_atlas: 'AML.T0051 LLM Prompt Injection',
    blast_radius: 'high',
    predicted_next:
      'Expect privilege use; watch for actions the newly granted role permits but this agent never took before.',
    customer: 'FinFlow Automation',
    timestamp: H(2),
    status: 'open',
  },
  {
    id: 'issue_003',
    type: 'detection',
    detection: 'port_sweep',
    source_ip: '10.2.4.17',
    mitre: 'T1046 Network Service Discovery',
    stage: 'Reconnaissance',
    confidence: 0.94,
    reason:
      '10.2.4.17 contacted 23 unique destinations in 8 s (threshold 15); inter-packet std 0.002 s (machine-regular)',
    prediction:
      'After Reconnaissance expect LateralMovement. Watch for east-west connections into segments this host has never reached.',
    customer: 'NovaCRM Labs',
    timestamp: H(1),
    status: 'open',
  },
  {
    id: 'issue_004',
    type: 'gate',
    verdict: 'WOULD-BLOCK',
    agent_id: 'crm-sync-agent',
    action_type: 'route_change',
    target: 'core-router/bgp-route-0.0.0.0/0',
    score: 0.75,
    reasons: [
      "action type 'route_change' is new for this agent",
      "target introduces unseen terms ['global', 'all']",
    ],
    mitre_attack: 'T1599 Network Boundary Bridging',
    mitre_atlas: 'AML.T0051 LLM Prompt Injection',
    blast_radius: 'medium',
    predicted_next:
      'Expect traffic redirection; watch for new flows toward the changed next hop.',
    customer: 'NovaCRM Labs',
    timestamp: H(4),
    status: 'in_review',
  },
  {
    id: 'issue_005',
    type: 'detection',
    detection: 'lateral_movement',
    source_ip: '192.168.10.44',
    mitre: 'T1021 Remote Services',
    stage: 'LateralMovement',
    confidence: 0.78,
    reason:
      '192.168.10.44 made first-time connections to 8 previously unreachable segments within 2 min of a firewall rule change.',
    prediction:
      'After LateralMovement expect Exfiltration. Watch for large or sustained outbound flows toward external destinations.',
    customer: 'HealthBridge AI',
    timestamp: H(5),
    status: 'open',
  },
]

// ── Execution plans ───────────────────────────────────────────────────────────

export const MOCK_PLANS: ExecutionPlan[] = [
  {
    issue_id: 'issue_001',
    plan_id: 'plan_001',
    dusk_action: 'enforce_block',
    fix_type: 'restrict_tool_and_attach_policy',
    recommended_fix:
      'Add a hard-block policy for sales-agent-v2 on firewall_rule_change. Revert the specific rule and review 0.0.0.0/0 exposure.',
    required_permissions: ['agent_workflow_write', 'policy_update', 'firewall_admin'],
    required_resources: ['engineering_time', 'test_environment', 'security_team_review'],
    approval_required: true,
    rollback_plan:
      'Restore the previous firewall rule and revert baseline update if it causes workflow disruption.',
    risk_before_fix: 'critical',
    risk_after_fix: 'low',
    backend_action: 'POST /api/security/fix',
    tavily_enrichment_query: 'T1562.004 firewall rule change LLM agent threat 2026',
    n8n_soar_trigger: true,
    estimated_time: '30 minutes',
  },
  {
    issue_id: 'issue_002',
    plan_id: 'plan_002',
    dusk_action: 'rotate_credentials',
    fix_type: 'rotate_api_key',
    recommended_fix:
      'Revoke the role assignment. Rotate agent credentials. Enforce hard BLOCK on role_assignment for finance-bot-01.',
    required_permissions: ['iam_admin', 'agent_workflow_write', 'audit_log_read'],
    required_resources: ['engineering_time', 'security_team_review', 'identity_team'],
    approval_required: true,
    rollback_plan:
      'Restore previous role assignment and credentials if rotation causes workflow failure.',
    risk_before_fix: 'critical',
    risk_after_fix: 'low',
    backend_action: 'POST /api/security/fix',
    tavily_enrichment_query: 'T1098 account manipulation LLM privilege escalation 2026',
    n8n_soar_trigger: true,
    estimated_time: '45 minutes',
  },
  {
    issue_id: 'issue_003',
    plan_id: 'plan_003',
    dusk_action: 'isolate_agent',
    fix_type: 'switch_to_readonly_policy',
    recommended_fix:
      'Isolate 10.2.4.17 from further outbound connections. Apply DUSK sweep detection in enforce mode.',
    required_permissions: ['network_admin', 'firewall_write'],
    required_resources: ['engineering_time', 'network_team'],
    approval_required: true,
    rollback_plan:
      'Re-allow 10.2.4.17 if isolation causes legitimate service disruption after investigation.',
    risk_before_fix: 'high',
    risk_after_fix: 'medium',
    backend_action: 'POST /api/security/fix',
    tavily_enrichment_query: 'T1046 network service discovery agent reconnaissance 2026',
    n8n_soar_trigger: true,
    estimated_time: '20 minutes',
  },
  {
    issue_id: 'issue_004',
    plan_id: 'plan_004',
    dusk_action: 'add_to_baseline',
    fix_type: 'restrict_tool_and_attach_policy',
    recommended_fix:
      'Update crm-sync-agent baseline to include route_change if legitimate, or enforce block. Verify BGP route with network team.',
    required_permissions: ['agent_workflow_write', 'network_admin'],
    required_resources: ['engineering_time', 'network_team'],
    approval_required: false,
    rollback_plan:
      'Revert BGP route change to previous state if baseline update causes network disruption.',
    risk_before_fix: 'high',
    risk_after_fix: 'low',
    backend_action: 'POST /api/security/fix',
    tavily_enrichment_query: 'T1599 network boundary bridging BGP route manipulation 2026',
    n8n_soar_trigger: false,
    estimated_time: '15 minutes',
  },
  {
    issue_id: 'issue_005',
    plan_id: 'plan_005',
    dusk_action: 'isolate_agent',
    fix_type: 'restrict_tool_and_attach_policy',
    recommended_fix:
      'Isolate 192.168.10.44 and review east-west traffic logs. Contain before exfiltration begins.',
    required_permissions: ['network_admin', 'firewall_write', 'siem_access'],
    required_resources: ['engineering_time', 'network_team', 'security_team_review'],
    approval_required: true,
    rollback_plan:
      'Re-allow connectivity for 192.168.10.44 if investigation confirms the host is clean.',
    risk_before_fix: 'high',
    risk_after_fix: 'medium',
    backend_action: 'POST /api/security/fix',
    tavily_enrichment_query: 'T1021 lateral movement remote services agent compromise 2026',
    n8n_soar_trigger: true,
    estimated_time: '1 hour',
  },
]

// ── Seed audit events ─────────────────────────────────────────────────────────

export const SEED_AUDIT: AuditEvent[] = [
  {
    id: 'audit_seed_001',
    timestamp: H(3),
    event_type: 'issue_detected',
    description: 'DUSK gate WOULD-BLOCK: sales-agent-v2 firewall_rule_change (score 0.85, blast_radius high)',
    actor: 'dusk_gate',
    issue_id: 'issue_001',
    metadata: { verdict: 'WOULD-BLOCK', score: '0.85', mitre: 'T1562.004', blast_radius: 'high' },
  },
  {
    id: 'audit_seed_002',
    timestamp: H(2),
    event_type: 'issue_detected',
    description: 'DUSK gate BLOCK: finance-bot-01 role_assignment → admin-role/owner (score 0.95)',
    actor: 'dusk_gate',
    issue_id: 'issue_002',
    metadata: { verdict: 'BLOCK', score: '0.95', mitre: 'T1098', blast_radius: 'high' },
  },
  {
    id: 'audit_seed_003',
    timestamp: H(1),
    event_type: 'issue_detected',
    description: 'DUSK detector port_sweep from 10.2.4.17 — 23 destinations in 8 s (confidence 0.94)',
    actor: 'dusk_detector',
    issue_id: 'issue_003',
    metadata: { mitre: 'T1046', stage: 'Reconnaissance', confidence: '0.94' },
  },
]

// ── Customer leads ────────────────────────────────────────────────────────────

export const MOCK_LEADS: CustomerLead[] = [
  {
    id: 'lead_001',
    company: 'Acme AI Ops',
    use_case: 'Customer-facing support agent',
    security_pain: 'Agent can access customer data and send external messages',
    fit_score: 87,
    source: 'Tavily research + Superlinked ICP match',
    suggested_pitch: 'Secure your AI agent workflows with approval, monitoring and self-healing execution.',
    status: 'ready_to_create_in_attio',
  },
  {
    id: 'lead_002',
    company: 'FinFlow Automation',
    use_case: 'Finance workflow automation',
    security_pain: 'Agent has API access to sensitive transaction workflows',
    fit_score: 81,
    source: 'Tavily research + Mubit classification',
    suggested_pitch: 'Add a controlled execution layer before agents can access finance APIs.',
    status: 'ready_to_review',
  },
  {
    id: 'lead_003',
    company: 'NovaCRM Labs',
    use_case: 'AI-powered CRM automation',
    security_pain: 'Agent has write access to all contacts without approval policy',
    fit_score: 76,
    source: 'Tavily research + Superlinked ICP match',
    suggested_pitch: 'Protect your CRM data with an approval gateway before every agent write operation.',
    status: 'under_review',
  },
  {
    id: 'lead_004',
    company: 'HealthBridge AI',
    use_case: 'Healthcare data processing agent',
    security_pain: 'Patient data accessible to agent without access audit trail',
    fit_score: 92,
    source: 'Tavily research + Superlinked ICP match',
    suggested_pitch: 'Meet compliance requirements with immutable audit logs for every agent action on patient data.',
    status: 'ready_to_create_in_attio',
  },
  {
    id: 'lead_005',
    company: 'LegalMind Systems',
    use_case: 'Contract review and negotiation agent',
    security_pain: 'Agent can commit to contract terms without human approval',
    fit_score: 79,
    source: 'Tavily research + Mubit classification',
    suggested_pitch: 'Add an approval gate so no AI agent can commit to legal obligations without a human sign-off.',
    status: 'ready_to_review',
  },
]
