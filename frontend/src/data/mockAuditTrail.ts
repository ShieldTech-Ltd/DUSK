export interface AuditEvent {
  id: string
  timestamp: string
  event_type:
    | 'issue_detected'
    | 'approval_requested'
    | 'manager_approved'
    | 'manager_rejected'
    | 'resource_allocated'
    | 'fix_triggered'
    | 'backend_response'
    | 'attio_updated'
    | 'n8n_triggered'
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
    description: 'Prompt injection risk detected in Acme Ltd customer support agent',
    actor: 'backend_scanner',
    issue_id: 'issue_001',
    metadata: { severity: 'critical', source: 'backend_scan' },
  },
  {
    id: 'audit_002',
    timestamp: new Date(now - 5400000).toISOString(),
    event_type: 'issue_detected',
    description: 'Over-permissive API key detected in FinFlow Automation workflow',
    actor: 'aikido_scanner',
    issue_id: 'issue_002',
    metadata: { severity: 'high', source: 'aikido_scan' },
  },
  {
    id: 'audit_003',
    timestamp: new Date(now - 3600000).toISOString(),
    event_type: 'issue_detected',
    description: 'Database write permission exposed to NovaCRM Labs agent',
    actor: 'backend_scanner',
    issue_id: 'issue_003',
    metadata: { severity: 'high', source: 'permission_check' },
  },
  {
    id: 'audit_004',
    timestamp: new Date(now - 1800000).toISOString(),
    event_type: 'approval_requested',
    description: 'Manager approval requested for issue_001 remediation',
    actor: 'system',
    issue_id: 'issue_001',
    metadata: { manager: 'manager@example.com' },
  },
]
