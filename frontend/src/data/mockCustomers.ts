export interface Customer {
  id: string
  company: string
  use_case: string
  security_pain: string
  fit_score: number
  source: string
  suggested_pitch: string
  status: 'Ready to create in Attio' | 'Ready to review' | 'Under review' | 'Created in Attio'
}

export const mockCustomers: Customer[] = [
  {
    id: 'lead_001',
    company: 'Acme AI Ops',
    use_case: 'Customer-facing support agent',
    security_pain: 'Agent can access customer data and send external messages',
    fit_score: 87,
    source: 'Tavily research + Superlinked ICP match',
    suggested_pitch:
      'Secure your AI agent workflows with approval, monitoring and self-healing execution.',
    status: 'Ready to create in Attio',
  },
  {
    id: 'lead_002',
    company: 'FinFlow Automation',
    use_case: 'Finance workflow automation',
    security_pain: 'Agent has API access to sensitive transaction workflows',
    fit_score: 81,
    source: 'Tavily research + Mubit classification',
    suggested_pitch:
      'Add a controlled execution layer before agents can access finance APIs.',
    status: 'Ready to review',
  },
  {
    id: 'lead_003',
    company: 'NovaCRM Labs',
    use_case: 'AI-powered CRM automation',
    security_pain: 'Agent has write access to all contacts without approval policy',
    fit_score: 76,
    source: 'Tavily research + Superlinked ICP match',
    suggested_pitch:
      'Protect your CRM data with an approval gateway before every agent write operation.',
    status: 'Under review',
  },
  {
    id: 'lead_004',
    company: 'HealthBridge AI',
    use_case: 'Healthcare data processing agent',
    security_pain: 'Patient data accessible to agent without access audit trail',
    fit_score: 92,
    source: 'Tavily research + Superlinked ICP match',
    suggested_pitch:
      'Meet compliance requirements with immutable audit logs for every agent action on patient data.',
    status: 'Ready to create in Attio',
  },
  {
    id: 'lead_005',
    company: 'LegalMind Systems',
    use_case: 'Contract review and negotiation agent',
    security_pain: 'Agent can commit to contract terms without human approval',
    fit_score: 79,
    source: 'Tavily research + Mubit classification',
    suggested_pitch:
      'Add an approval gate so no AI agent can commit to legal obligations without a human sign-off.',
    status: 'Ready to review',
  },
]
