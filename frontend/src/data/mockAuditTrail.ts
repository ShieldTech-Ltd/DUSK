export interface AuditEvent {
  id: string
  timestamp: string
  event_type:
    | 'issue_detected'
    | 'tavily_enrichment'
    | 'approval_requested'
    | 'manager_approved'
    | 'manager_rejected'
    | 'resource_allocated'
    | 'fix_triggered'
    | 'backend_response'
    | 'n8n_soar_triggered'
    | 'attio_updated'
    | 'issue_selected'
  description: string
  actor: string
  issue_id?: string
  metadata?: Record<string, string>
}

const now = Date.now()

export const initialAuditTrail: AuditEvent[] = [
  {
    id: 'audit_001',
    timestamp: new Date(now - 7200000).toISOString(),
    event_type: 'issue_detected',
    description:
      'DUSK gate WOULD-BLOCK: sales-agent-v2 attempted firewall_rule_change on prod-firewall-rule-42 (score 0.85, blast_radius high)',
    actor: 'dusk_gate',
    issue_id: 'issue_001',
    metadata: { verdict: 'WOULD-BLOCK', score: '0.85', mitre: 'T1562.004', blast_radius: 'high' },
  },
  {
    id: 'audit_002',
    timestamp: new Date(now - 6900000).toISOString(),
    event_type: 'tavily_enrichment',
    description:
      'Tavily threat intel fetched for T1562.004 — 3 threat actor reports found, sources logged',
    actor: 'tavily_enrichment',
    issue_id: 'issue_001',
    metadata: { query: 'T1562.004 firewall rule change LLM agent threat 2026', results_count: '3' },
  },
  {
    id: 'audit_003',
    timestamp: new Date(now - 5400000).toISOString(),
    event_type: 'issue_detected',
    description:
      'DUSK gate BLOCK: finance-bot-01 attempted role_assignment to admin-role/owner (score 0.95, blast_radius high)',
    actor: 'dusk_gate',
    issue_id: 'issue_002',
    metadata: { verdict: 'BLOCK', score: '0.95', mitre: 'T1098', blast_radius: 'high' },
  },
  {
    id: 'audit_004',
    timestamp: new Date(now - 5100000).toISOString(),
    event_type: 'n8n_soar_triggered',
    description:
      'n8n SOAR workflow triggered for issue_002 — DUSK alert sent to SOAR incident tracker',
    actor: 'n8n_webhook',
    issue_id: 'issue_002',
    metadata: { workflow: 'DUSK Alert to SOAR', status: 'acknowledged' },
  },
  {
    id: 'audit_005',
    timestamp: new Date(now - 3600000).toISOString(),
    event_type: 'issue_detected',
    description:
      'DUSK detection port_sweep from 10.2.4.17 — 23 destinations in 8 s (confidence 0.94, stage Reconnaissance)',
    actor: 'dusk_detector',
    issue_id: 'issue_003',
    metadata: { mitre: 'T1046', stage: 'Reconnaissance', confidence: '0.94' },
  },
  {
    id: 'audit_006',
    timestamp: new Date(now - 1800000).toISOString(),
    event_type: 'approval_requested',
    description: 'Manager approval requested for issue_001 remediation',
    actor: 'system',
    issue_id: 'issue_001',
    metadata: { manager: 'manager@example.com' },
  },
]
