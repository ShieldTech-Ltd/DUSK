/**
 * Rule-based execution plan generator.
 *
 * Maps DUSK issue types → recommended fixes, required resources, and DUSK actions.
 * Each rule matches on issue properties and returns a full ExecutionPlan.
 */

import { randomUUID } from 'crypto'
import type { TraceIssue, ExecutionPlan, DuskAction } from './traceTypes'

interface PlanRule {
  match: (issue: TraceIssue) => boolean
  build: (issue: TraceIssue, planId: string) => ExecutionPlan
}

const RULES: PlanRule[] = [
  // ── Gate: privilege escalation (role_assignment) ──────────────────────────
  {
    match: i => i.type === 'gate' && (i as { action_type: string }).action_type === 'role_assignment',
    build: (issue, planId) => ({
      issue_id: issue.id,
      plan_id: planId,
      dusk_action: 'rotate_credentials' as DuskAction,
      fix_type: 'rotate_api_key',
      recommended_fix:
        `Immediately revoke the unauthorized role assignment for ${(issue as { agent_id: string }).agent_id}. Rotate agent credentials and enforce a hard BLOCK on role_assignment actions for this agent.`,
      required_permissions: ['iam_admin', 'agent_workflow_write', 'audit_log_read'],
      required_resources: ['engineering_time', 'security_team_review', 'identity_team'],
      approval_required: true,
      rollback_plan: 'Restore previous role assignment and credentials if rotation causes workflow failure.',
      risk_before_fix: 'critical',
      risk_after_fix: 'low',
      backend_action: 'POST /api/security/fix',
      tavily_enrichment_query: `T1098 account manipulation LLM privilege escalation ${new Date().getFullYear()}`,
      n8n_soar_trigger: true,
      estimated_time: '45 minutes',
    }),
  },

  // ── Gate: firewall rule change ────────────────────────────────────────────
  {
    match: i => i.type === 'gate' && (i as { action_type: string }).action_type === 'firewall_rule_change',
    build: (issue, planId) => ({
      issue_id: issue.id,
      plan_id: planId,
      dusk_action: 'enforce_block' as DuskAction,
      fix_type: 'restrict_tool_and_attach_policy',
      recommended_fix:
        `Add a hard-block policy for ${(issue as { agent_id: string }).agent_id} on firewall_rule_change actions and revert the specific rule change.`,
      required_permissions: ['agent_workflow_write', 'policy_update', 'firewall_admin'],
      required_resources: ['engineering_time', 'test_environment', 'security_team_review'],
      approval_required: true,
      rollback_plan: 'Restore the previous firewall rule and revert agent baseline if disruption occurs.',
      risk_before_fix: 'critical',
      risk_after_fix: 'low',
      backend_action: 'POST /api/security/fix',
      tavily_enrichment_query: `T1562.004 firewall rule change LLM agent threat ${new Date().getFullYear()}`,
      n8n_soar_trigger: true,
      estimated_time: '30 minutes',
    }),
  },

  // ── Gate: route change ────────────────────────────────────────────────────
  {
    match: i => i.type === 'gate' && (i as { action_type: string }).action_type === 'route_change',
    build: (issue, planId) => ({
      issue_id: issue.id,
      plan_id: planId,
      dusk_action: 'add_to_baseline' as DuskAction,
      fix_type: 'restrict_tool_and_attach_policy',
      recommended_fix:
        `Update ${(issue as { agent_id: string }).agent_id} baseline to allow route_change if legitimate, or enforce a block and verify the BGP route change with the network team.`,
      required_permissions: ['agent_workflow_write', 'network_admin'],
      required_resources: ['engineering_time', 'network_team'],
      approval_required: false,
      rollback_plan: 'Revert BGP route change to previous state if disruption occurs.',
      risk_before_fix: 'high',
      risk_after_fix: 'low',
      backend_action: 'POST /api/security/fix',
      tavily_enrichment_query: `T1599 network boundary bridging BGP route manipulation ${new Date().getFullYear()}`,
      n8n_soar_trigger: false,
      estimated_time: '15 minutes',
    }),
  },

  // ── Detection: port sweep (Reconnaissance) ────────────────────────────────
  {
    match: i => i.type === 'detection' && (i as { detection: string }).detection === 'port_sweep',
    build: (issue, planId) => ({
      issue_id: issue.id,
      plan_id: planId,
      dusk_action: 'isolate_agent' as DuskAction,
      fix_type: 'switch_to_readonly_policy',
      recommended_fix:
        `Isolate ${(issue as { source_ip: string }).source_ip} from further outbound connections. Apply DUSK sweep detection in enforce mode for this source.`,
      required_permissions: ['network_admin', 'firewall_write'],
      required_resources: ['engineering_time', 'network_team'],
      approval_required: true,
      rollback_plan: "Re-allow network access if isolation causes legitimate service disruption after investigation.",
      risk_before_fix: 'high',
      risk_after_fix: 'medium',
      backend_action: 'POST /api/security/fix',
      tavily_enrichment_query: `T1046 network service discovery agent reconnaissance ${new Date().getFullYear()}`,
      n8n_soar_trigger: true,
      estimated_time: '20 minutes',
    }),
  },

  // ── Detection: lateral movement ───────────────────────────────────────────
  {
    match: i => i.type === 'detection' && (i as { detection: string }).detection === 'lateral_movement',
    build: (issue, planId) => ({
      issue_id: issue.id,
      plan_id: planId,
      dusk_action: 'isolate_agent' as DuskAction,
      fix_type: 'restrict_tool_and_attach_policy',
      recommended_fix:
        `Isolate ${(issue as { source_ip: string }).source_ip} and review east-west traffic logs. Contain the host before exfiltration begins.`,
      required_permissions: ['network_admin', 'firewall_write', 'siem_access'],
      required_resources: ['engineering_time', 'network_team', 'security_team_review'],
      approval_required: true,
      rollback_plan: "Re-allow connectivity if investigation confirms the host is clean.",
      risk_before_fix: 'high',
      risk_after_fix: 'medium',
      backend_action: 'POST /api/security/fix',
      tavily_enrichment_query: `T1021 lateral movement remote services agent compromise ${new Date().getFullYear()}`,
      n8n_soar_trigger: true,
      estimated_time: '1 hour',
    }),
  },
]

// Fallback rule for any unmatched issue type
const fallbackRule = (issue: TraceIssue, planId: string): ExecutionPlan => ({
  issue_id: issue.id,
  plan_id: planId,
  dusk_action: 'enforce_block',
  fix_type: 'restrict_tool_and_attach_policy',
  recommended_fix: 'Disable external email tool until approval policy is attached.',
  required_permissions: ['agent_workflow_write', 'policy_update'],
  required_resources: ['engineering_time', 'test_environment'],
  approval_required: true,
  rollback_plan: 'Re-enable previous workflow version if fix fails.',
  risk_before_fix: 'high',
  risk_after_fix: 'low',
  backend_action: 'POST /api/security/fix',
  n8n_soar_trigger: false,
  estimated_time: '30 minutes',
})

export function generatePlan(issue: TraceIssue): ExecutionPlan {
  const planId = `plan_${randomUUID().slice(0, 8)}`
  const rule = RULES.find(r => r.match(issue))
  return rule ? rule.build(issue, planId) : fallbackRule(issue, planId)
}
