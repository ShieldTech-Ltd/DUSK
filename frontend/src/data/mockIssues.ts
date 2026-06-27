export type Severity = 'critical' | 'high' | 'medium' | 'low'
export type IssueStatus = 'open' | 'in_review' | 'approved' | 'fixed' | 'closed'

export interface SecurityIssue {
  id: string
  title: string
  severity: Severity
  affected_system: string
  customer: string
  source: string
  status: IssueStatus
  evidence: string
}

export const mockIssues: SecurityIssue[] = [
  {
    id: 'issue_001',
    title: 'Prompt injection risk in customer support agent',
    severity: 'critical',
    affected_system: 'agent_workflow',
    customer: 'Acme Ltd',
    source: 'Backend scan + Tavily external content check',
    status: 'open',
    evidence: 'External content attempted to override agent policy',
  },
  {
    id: 'issue_002',
    title: 'Over-permissive API key',
    severity: 'high',
    affected_system: 'api',
    customer: 'FinFlow Automation',
    source: 'Aikido-style security scan',
    status: 'open',
    evidence: 'Agent workflow can access write operations not required for its task',
  },
  {
    id: 'issue_003',
    title: 'Database write permission exposed to agent',
    severity: 'high',
    affected_system: 'database',
    customer: 'NovaCRM Labs',
    source: 'Backend permission check',
    status: 'open',
    evidence: 'Agent has write access without approval policy',
  },
  {
    id: 'issue_004',
    title: 'Agent exfiltrating contact list to external URL',
    severity: 'critical',
    affected_system: 'agent_workflow',
    customer: 'Acme Ltd',
    source: 'Superlinked anomaly detection',
    status: 'open',
    evidence:
      'Vector similarity matched known data exfiltration pattern with 0.96 confidence',
  },
  {
    id: 'issue_005',
    title: 'Agent sending unapproved external emails',
    severity: 'medium',
    affected_system: 'email_tool',
    customer: 'LegalMind Systems',
    source: 'n8n workflow monitor',
    status: 'in_review',
    evidence: 'Email tool invoked 47 times outside allowed business hours window',
  },
]
