/**
 * Mock DUSK gate verdicts and network detection alerts.
 *
 * Schema matches the real DUSK backend:
 *   - GateVerdict: verdict (ALLOW | WOULD-BLOCK | BLOCK), score, agent_id,
 *     action_type, target, reasons, mitre_attack, mitre_atlas, blast_radius,
 *     predicted_next
 *   - DetectionAlert: detection, source (IP), mitre, stage, confidence,
 *     reason, prediction
 */

export type Verdict = 'ALLOW' | 'WOULD-BLOCK' | 'BLOCK'
export type BlastRadius = 'low' | 'medium' | 'high'
export type KillChainStage = 'Reconnaissance' | 'LateralMovement' | 'Exfiltration'
export type IssueStatus = 'open' | 'in_review' | 'approved' | 'fixed'

/** Gate verdict — an agent action the DUSK gate refused or flagged */
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

/** Network detection alert — a packet-level threat fired by a DUSK detector */
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

export type SecurityIssue = GateIssue | DetectionIssue

/** Title for display */
export function issueTitle(issue: SecurityIssue): string {
  if (issue.type === 'gate')
    return `${issue.verdict}: ${issue.action_type} by ${issue.agent_id}`
  return `${issue.detection} from ${issue.source_ip}`
}

/** Severity-equivalent label for display */
export function issueSeverity(issue: SecurityIssue): string {
  if (issue.type === 'gate') {
    if (issue.verdict === 'BLOCK' || issue.blast_radius === 'high') return 'critical'
    if (issue.verdict === 'WOULD-BLOCK' || issue.blast_radius === 'medium') return 'high'
    return 'medium'
  }
  if (issue.confidence >= 0.9) return 'critical'
  if (issue.confidence >= 0.7) return 'high'
  return 'medium'
}

const now = new Date().toISOString()

export const mockIssues: SecurityIssue[] = [
  {
    id: 'issue_001',
    type: 'gate',
    verdict: 'WOULD-BLOCK',
    agent_id: 'sales-agent-v2',
    action_type: 'firewall_rule_change',
    target: 'prod-firewall-rule-42',
    score: 0.85,
    reasons: [
      "action type 'firewall_rule_change' is new for this agent, which normally does ['crm_read', 'send_email']",
      "newly introduces sensitive or privileged terms ['0.0.0.0/0']",
    ],
    mitre_attack: 'T1562.004 Impair Defenses: Disable or Modify System Firewall',
    mitre_atlas: 'AML.T0051 LLM Prompt Injection',
    blast_radius: 'high',
    predicted_next:
      'expect lateral movement into the newly reachable segment; watch for east-west connections from this agent',
    customer: 'Acme Ltd',
    timestamp: now,
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
      "action type 'role_assignment' is new for this agent, which normally does ['transaction_read']",
      "newly introduces sensitive or privileged terms ['owner', 'admin']",
    ],
    mitre_attack: 'T1098 Account Manipulation',
    mitre_atlas: 'AML.T0051 LLM Prompt Injection',
    blast_radius: 'high',
    predicted_next:
      'expect privilege use; watch for actions that the newly granted role permits but this agent never took before',
    customer: 'FinFlow Automation',
    timestamp: now,
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
      '10.2.4.17 contacted 23 unique destinations in 8 s (threshold 15), inter-packet std 0.002 s (machine-regular)',
    prediction:
      'After Reconnaissance, expect LateralMovement next. Watch for: east-west connections into segments this host has never talked to.',
    customer: 'NovaCRM Labs',
    timestamp: now,
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
      'expect traffic redirection or interception; watch for new flows toward the changed next hop',
    customer: 'NovaCRM Labs',
    timestamp: now,
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
      '192.168.10.44 made first-time connections to 8 previously unreachable segments within 2 min of a firewall rule change',
    prediction:
      'After LateralMovement, expect Exfiltration next. Watch for: large or sustained outbound flows toward external destinations.',
    customer: 'HealthBridge AI',
    timestamp: now,
    status: 'open',
  },
]
