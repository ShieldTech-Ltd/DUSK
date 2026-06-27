'use client'

import { useState } from 'react'
import { mockIssues, issueTitle, issueSeverity, type SecurityIssue, type GateIssue, type DetectionIssue } from '@/data/mockIssues'
import { mockExecutionPlans, type ExecutionPlan } from '@/data/mockExecutionPlans'
import { initialAuditTrail, type AuditEvent } from '@/data/mockAuditTrail'
import { executeSecurityFix, getTavilyEnrichment, triggerN8nWorkflow, type TavilyEnrichment, type FixResult } from '@/lib/backendClient'

// ── Styling helpers ────────────────────────────────────────────────────────────

const VERDICT_STYLE: Record<string, string> = {
  'WOULD-BLOCK': 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
  'BLOCK':       'bg-red-900/60 text-red-300 border-red-700',
  'ALLOW':       'bg-green-900/60 text-green-300 border-green-700',
}
const VERDICT_DOT: Record<string, string> = {
  'WOULD-BLOCK': 'bg-yellow-400',
  'BLOCK':       'bg-red-500',
  'ALLOW':       'bg-green-500',
}
const SEVERITY_STYLE: Record<string, string> = {
  critical: 'bg-red-900/60 text-red-300 border-red-700',
  high:     'bg-orange-900/60 text-orange-300 border-orange-700',
  medium:   'bg-yellow-900/60 text-yellow-300 border-yellow-700',
}
const BLAST_STYLE: Record<string, string> = {
  high:   'text-red-400',
  medium: 'text-yellow-400',
  low:    'text-green-400',
}
const RISK_STYLE: Record<string, string> = {
  low:    'bg-green-900/60 text-green-300 border-green-700',
  medium: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
  high:   'bg-red-900/60 text-red-300 border-red-700',
}
const DUSK_ACTION_STYLE: Record<string, string> = {
  enforce_block:    'bg-red-900/40 border-red-700/50 text-red-300',
  rotate_credentials: 'bg-orange-900/40 border-orange-700/50 text-orange-300',
  isolate_agent:    'bg-purple-900/40 border-purple-700/50 text-purple-300',
  add_to_baseline:  'bg-blue-900/40 border-blue-700/50 text-blue-300',
}

const EVENT_ICON: Record<AuditEvent['event_type'], string> = {
  issue_detected:     '🔍',
  tavily_enrichment:  '🌐',
  approval_requested: '📧',
  manager_approved:   '✅',
  manager_rejected:   '❌',
  resource_allocated: '🔧',
  fix_triggered:      '⚡',
  backend_response:   '📡',
  n8n_soar_triggered: '⚙️',
  attio_updated:      '🗃️',
  issue_selected:     '👁️',
}

const RESOURCE_OPTIONS = [
  'engineering_time',
  'security_team_review',
  'network_team',
  'identity_team',
  'firewall_admin',
  'agent_workflow_access',
]

const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

const formatEventType = (t: AuditEvent['event_type']) =>
  t.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

// ── Issue card helpers ─────────────────────────────────────────────────────────

function IssueDot({ issue }: { issue: SecurityIssue }) {
  if (issue.type === 'gate') {
    return <div className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${VERDICT_DOT[issue.verdict] ?? 'bg-gray-500'}`} />
  }
  const conf = issue.confidence
  const color = conf >= 0.9 ? 'bg-red-500' : conf >= 0.7 ? 'bg-orange-500' : 'bg-yellow-500'
  return <div className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${color}`} />
}

function IssueBadge({ issue }: { issue: SecurityIssue }) {
  if (issue.type === 'gate') {
    return (
      <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${VERDICT_STYLE[issue.verdict] ?? ''}`}>
        {issue.verdict}
      </span>
    )
  }
  const sev = issueSeverity(issue)
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${SEVERITY_STYLE[sev] ?? ''}`}>
      {issue.stage}
    </span>
  )
}

// ── Gate detail ───────────────────────────────────────────────────────────────

function GateDetail({ issue }: { issue: GateIssue }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-4 text-sm">
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Agent</p>
          <code className="text-blue-300">{issue.agent_id}</code>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Action</p>
          <code className="text-yellow-300">{issue.action_type}</code>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Target</p>
          <code className="text-gray-300">{issue.target}</code>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Score</p>
          <span className="text-white font-bold">{(issue.score * 100).toFixed(0)}%</span>
          <div className="w-20 h-1.5 bg-gray-800 rounded-full mt-1">
            <div
              className={`h-1.5 rounded-full ${issue.score >= 0.8 ? 'bg-red-500' : issue.score >= 0.6 ? 'bg-yellow-500' : 'bg-green-500'}`}
              style={{ width: `${issue.score * 100}%` }}
            />
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Blast radius</p>
          <span className={`font-semibold ${BLAST_STYLE[issue.blast_radius]}`}>{issue.blast_radius}</span>
        </div>
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-1">MITRE ATT&CK</p>
        <code className="text-xs text-purple-300 bg-purple-950/30 px-2 py-1 rounded">{issue.mitre_attack}</code>
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-1">MITRE ATLAS</p>
        <code className="text-xs text-pink-300 bg-pink-950/30 px-2 py-1 rounded">{issue.mitre_atlas}</code>
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-1">Reasons (DUSK analyser)</p>
        <ul className="space-y-1">
          {issue.reasons.map((r, i) => (
            <li key={i} className="text-sm text-red-200 bg-red-950/30 border border-red-900/40 rounded px-3 py-1.5">
              {r}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-1">Predicted next</p>
        <p className="text-sm text-orange-200 bg-orange-950/30 border border-orange-900/40 rounded px-3 py-1.5">
          {issue.predicted_next}
        </p>
      </div>
    </div>
  )
}

// ── Detection detail ──────────────────────────────────────────────────────────

function DetectionDetail({ issue }: { issue: DetectionIssue }) {
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-4 text-sm">
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Source IP</p>
          <code className="text-red-300">{issue.source_ip}</code>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Detection</p>
          <code className="text-yellow-300">{issue.detection}</code>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Kill-chain stage</p>
          <span className="text-orange-300 font-medium">{issue.stage}</span>
        </div>
        <div>
          <p className="text-xs text-gray-500 mb-0.5">Confidence</p>
          <span className="text-white font-bold">{(issue.confidence * 100).toFixed(0)}%</span>
          <div className="w-20 h-1.5 bg-gray-800 rounded-full mt-1">
            <div
              className="h-1.5 rounded-full bg-red-500"
              style={{ width: `${issue.confidence * 100}%` }}
            />
          </div>
        </div>
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-1">MITRE ATT&CK</p>
        <code className="text-xs text-purple-300 bg-purple-950/30 px-2 py-1 rounded">{issue.mitre}</code>
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-1">Evidence</p>
        <p className="text-sm text-red-200 bg-red-950/30 border border-red-900/40 rounded px-3 py-1.5">{issue.reason}</p>
      </div>
      <div>
        <p className="text-xs text-gray-500 mb-1">Kill-chain prediction</p>
        <p className="text-sm text-orange-200 bg-orange-950/30 border border-orange-900/40 rounded px-3 py-1.5">{issue.prediction}</p>
      </div>
    </div>
  )
}

// ── Tavily enrichment panel ───────────────────────────────────────────────────

function TavilyPanel({
  issueId,
  issue,
}: {
  issueId: string
  issue: SecurityIssue
}) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<TavilyEnrichment | null>(null)
  const [error, setError] = useState<string | null>(null)

  const agentId = issue.type === 'gate' ? issue.agent_id : issue.source_ip
  const actionType = issue.type === 'gate' ? issue.action_type : issue.detection
  const mitreId = issue.type === 'gate' ? issue.mitre_attack.split(' ')[0] : issue.mitre.split(' ')[0]

  const fetch = async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getTavilyEnrichment(agentId, actionType, mitreId)
      setData(result)
    } catch {
      setError('Tavily enrichment failed. Check TAVILY_API_KEY.')
    } finally {
      setLoading(false)
    }
  }

  if (!data && !loading) {
    return (
      <button
        onClick={fetch}
        className="w-full text-left px-3 py-2 bg-teal-950/30 border border-teal-800/50 rounded-lg text-teal-300 text-xs hover:bg-teal-950/50 transition-colors flex items-center gap-2"
      >
        🌐 Fetch Tavily threat intel for <code className="text-teal-200">{mitreId}</code>
      </button>
    )
  }

  if (loading) return <p className="text-teal-400 text-xs animate-pulse">Searching Tavily for {mitreId}…</p>
  if (error) return <p className="text-red-400 text-xs">{error}</p>

  return (
    <div className="bg-teal-950/30 border border-teal-800/50 rounded-lg p-3 space-y-2">
      <p className="text-teal-300 text-xs font-medium">🌐 Tavily threat intel — <code className="text-teal-200">{data!.query}</code></p>
      {data!.results.map((r, i) => (
        <div key={i} className="bg-gray-900/60 rounded p-2">
          <p className="text-xs text-gray-300 font-medium mb-0.5">{r.title}</p>
          <p className="text-xs text-gray-400 line-clamp-2">{r.content}</p>
          <a href={r.url} target="_blank" rel="noopener noreferrer" className="text-xs text-teal-400 hover:underline truncate block mt-0.5">{r.url}</a>
        </div>
      ))}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function ExecutionCockpit() {
  const [issues] = useState<SecurityIssue[]>(mockIssues)
  const [selectedIssue, setSelectedIssue] = useState<SecurityIssue | null>(null)
  const [plan, setPlan] = useState<ExecutionPlan | null>(null)
  const [approvalState, setApprovalState] = useState<'pending' | 'approved' | 'rejected' | 'info_requested'>('pending')
  const [allocatedResources, setAllocatedResources] = useState<string[]>([])
  const [fixResult, setFixResult] = useState<FixResult | null>(null)
  const [executing, setExecuting] = useState(false)
  const [auditTrail, setAuditTrail] = useState<AuditEvent[]>(initialAuditTrail)
  const [managerEmail, setManagerEmail] = useState('manager@example.com')

  const addAuditEvent = (event: Omit<AuditEvent, 'id' | 'timestamp'>) => {
    setAuditTrail((prev) => [
      { ...event, id: `audit_live_${Date.now()}`, timestamp: new Date().toISOString() },
      ...prev,
    ])
  }

  const selectIssue = (issue: SecurityIssue) => {
    setSelectedIssue(issue)
    setPlan(mockExecutionPlans[issue.id] ?? null)
    setApprovalState('pending')
    setAllocatedResources([])
    setFixResult(null)
    addAuditEvent({
      event_type: 'issue_selected',
      description: `Issue selected for review: ${issueTitle(issue)}`,
      actor: 'manager',
      issue_id: issue.id,
    })
  }

  const handleApproval = (decision: 'approved' | 'rejected' | 'info_requested') => {
    setApprovalState(decision)
    const eventTypes: Record<typeof decision, AuditEvent['event_type']> = {
      approved: 'manager_approved',
      rejected: 'manager_rejected',
      info_requested: 'approval_requested',
    }
    addAuditEvent({
      event_type: eventTypes[decision],
      description: `Manager ${decision.replace('_', ' ')} for: ${issueTitle(selectedIssue!)}`,
      actor: managerEmail,
      issue_id: selectedIssue?.id,
    })
  }

  const toggleResource = (resource: string) => {
    setAllocatedResources((prev) => {
      const next = prev.includes(resource) ? prev.filter((x) => x !== resource) : [...prev, resource]
      if (!prev.includes(resource)) {
        addAuditEvent({
          event_type: 'resource_allocated',
          description: `Resource allocated: ${resource}`,
          actor: managerEmail,
          issue_id: selectedIssue?.id,
          metadata: { resource },
        })
      }
      return next
    })
  }

  const handleExecuteFix = async () => {
    if (!selectedIssue || !plan) return
    setExecuting(true)

    addAuditEvent({
      event_type: 'fix_triggered',
      description: `DUSK fix triggered: ${plan.dusk_action} for ${issueTitle(selectedIssue)}`,
      actor: managerEmail,
      issue_id: selectedIssue.id,
      metadata: { dusk_action: plan.dusk_action, backend_action: plan.backend_action },
    })

    try {
      const result = await executeSecurityFix({
        issue_id: selectedIssue.id,
        approved_by: managerEmail,
        resources: allocatedResources,
        action_plan: plan.recommended_fix,
        dusk_action: plan.dusk_action,
      })
      setFixResult(result)

      addAuditEvent({
        event_type: 'backend_response',
        description: `DUSK backend: ${result.status} — ${result.message}`,
        actor: 'dusk_gate',
        issue_id: selectedIssue.id,
        metadata: { execution_id: result.execution_id, status: result.status },
      })

      if (plan.n8n_soar_trigger) {
        const n8nPayload =
          selectedIssue.type === 'gate'
            ? {
                verdict: selectedIssue.verdict,
                analysis: {
                  agent_id: selectedIssue.agent_id,
                  score: selectedIssue.score,
                  mitre_attack: selectedIssue.mitre_attack,
                  blast_radius: selectedIssue.blast_radius,
                },
              }
            : {
                verdict: `DETECTION:${selectedIssue.stage}`,
                analysis: {
                  agent_id: selectedIssue.source_ip,
                  score: selectedIssue.confidence,
                  mitre_attack: selectedIssue.mitre,
                  blast_radius: selectedIssue.confidence >= 0.9 ? 'high' : 'medium',
                },
              }

        await triggerN8nWorkflow(n8nPayload)
        addAuditEvent({
          event_type: 'n8n_soar_triggered',
          description: 'n8n SOAR workflow triggered — DUSK alert dispatched to incident tracker',
          actor: 'n8n_webhook',
          issue_id: selectedIssue.id,
        })
      }

      addAuditEvent({
        event_type: 'attio_updated',
        description: `Attio security record updated for customer: ${selectedIssue.customer}`,
        actor: 'system',
        issue_id: selectedIssue.id,
      })
    } finally {
      setExecuting(false)
    }
  }

  const executionStep = (() => {
    if (!selectedIssue) return 1
    if (!plan) return 2
    if (!fixResult) return 3
    return 4
  })()

  const STEPS = [
    { n: 1, label: 'Select issue' },
    { n: 2, label: 'Review plan' },
    { n: 3, label: 'Approve' },
    { n: 4, label: 'Execute & audit' },
  ]

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white mb-1">Execution Cockpit</h2>
        <p className="text-gray-400 text-sm mb-4">
          A detected security issue becomes an approved backend fix in four guided steps.
        </p>

        {/* Step indicator */}
        <div className="flex items-center gap-0 mb-6">
          {STEPS.map((s, i) => (
            <span key={s.n} className="flex items-center">
              <span
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  executionStep === s.n
                    ? 'bg-blue-600 text-white'
                    : executionStep > s.n
                    ? 'bg-green-900/60 text-green-300 border border-green-800'
                    : 'bg-gray-800 text-gray-500 border border-gray-700'
                }`}
              >
                <span className={`w-4 h-4 rounded-full text-[10px] flex items-center justify-center font-bold shrink-0 ${
                  executionStep > s.n ? 'bg-green-500 text-white' : executionStep === s.n ? 'bg-blue-400 text-blue-900' : 'bg-gray-700 text-gray-400'
                }`}>
                  {executionStep > s.n ? '✓' : s.n}
                </span>
                {s.label}
              </span>
              {i < STEPS.length - 1 && (
                <span className={`mx-1 text-xs ${executionStep > s.n ? 'text-green-700' : 'text-gray-700'}`}>→</span>
              )}
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Issue inbox */}
        <div className="xl:col-span-1">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            DUSK Alert Inbox
          </h3>
          <div className="space-y-2">
            {issues.map((issue) => (
              <button
                key={issue.id}
                onClick={() => selectIssue(issue)}
                className={`w-full text-left p-4 rounded-xl border transition-all ${
                  selectedIssue?.id === issue.id
                    ? 'border-blue-600 bg-blue-950/40'
                    : 'border-gray-800 bg-gray-900 hover:border-gray-700'
                }`}
              >
                <div className="flex items-start gap-3">
                  <IssueDot issue={issue} />
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-white leading-tight mb-1.5">
                      {issueTitle(issue)}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      <IssueBadge issue={issue} />
                      <span className="text-xs text-gray-500">{issue.customer}</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail panel */}
        <div className="xl:col-span-2 space-y-4">
          {!selectedIssue ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center">
              <p className="text-gray-500 text-sm">Select a DUSK alert to begin</p>
            </div>
          ) : (
            <>
              {/* Issue header */}
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div>
                    <h3 className="font-semibold text-white mb-1">{issueTitle(selectedIssue)}</h3>
                    <p className="text-gray-400 text-sm">
                      {selectedIssue.customer} · type: {selectedIssue.type}
                    </p>
                  </div>
                  <IssueBadge issue={selectedIssue} />
                </div>
                {selectedIssue.type === 'gate'
                  ? <GateDetail issue={selectedIssue} />
                  : <DetectionDetail issue={selectedIssue} />
                }
              </div>

              {/* Tavily enrichment */}
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
                  Tavily Threat Intelligence
                </h4>
                <TavilyPanel key={selectedIssue.id} issueId={selectedIssue.id} issue={selectedIssue} />
              </div>

              {/* Execution plan */}
              {plan && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <h4 className="font-semibold text-white mb-3">Execution Plan</h4>
                  <div className="space-y-3">
                    {/* DUSK action badge */}
                    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm font-medium ${DUSK_ACTION_STYLE[plan.dusk_action] ?? 'bg-gray-800 border-gray-700 text-gray-300'}`}>
                      <span>DUSK action:</span>
                      <code>{plan.dusk_action.replace(/_/g, ' ')}</code>
                    </div>

                    <div>
                      <p className="text-xs text-gray-400 mb-1">Recommended fix</p>
                      <p className="text-sm text-gray-200 leading-relaxed">{plan.recommended_fix}</p>
                    </div>

                    {plan.tavily_enrichment_query && (
                      <div>
                        <p className="text-xs text-gray-400 mb-1">Tavily query</p>
                        <code className="text-xs text-teal-300 bg-teal-950/30 px-2 py-1 rounded block">{plan.tavily_enrichment_query}</code>
                      </div>
                    )}

                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-xs text-gray-400 mb-1">Required permissions</p>
                        <div className="flex flex-wrap gap-1">
                          {plan.required_permissions.map((p) => (
                            <span key={p} className="text-xs px-2 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-300">{p}</span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400 mb-1">Risk after fix</p>
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${RISK_STYLE[plan.risk_after_fix]}`}>
                          {plan.risk_after_fix}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 text-xs text-gray-500 flex-wrap">
                      <span>Backend: <code className="text-blue-400">{plan.backend_action}</code></span>
                      <span>Est: {plan.estimated_time}</span>
                      {plan.n8n_soar_trigger && (
                        <span className="text-orange-400">⚙ n8n SOAR trigger enabled</span>
                      )}
                    </div>

                    <div>
                      <p className="text-xs text-gray-400 mb-1">Rollback plan</p>
                      <p className="text-sm text-gray-400 italic">{plan.rollback_plan}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Manager approval */}
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <h4 className="font-semibold text-white mb-3">Manager Approval</h4>
                <div className="mb-4">
                  <label className="block text-xs text-gray-400 mb-1">Manager email</label>
                  <input
                    type="email"
                    value={managerEmail}
                    onChange={(e) => setManagerEmail(e.target.value)}
                    className="w-full max-w-xs bg-gray-800 border border-gray-700 rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div className="mb-4">
                  <p className="text-xs text-gray-400 mb-2">Allocate resources</p>
                  <div className="flex flex-wrap gap-2">
                    {RESOURCE_OPTIONS.map((r) => (
                      <button
                        key={r}
                        onClick={() => toggleResource(r)}
                        className={`text-xs px-3 py-1.5 rounded-lg border font-medium transition-colors ${
                          allocatedResources.includes(r)
                            ? 'bg-blue-700 border-blue-600 text-white'
                            : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-500'
                        }`}
                      >
                        {r.replace(/_/g, ' ')}
                      </button>
                    ))}
                  </div>
                </div>

                {approvalState === 'pending' ? (
                  <div className="flex flex-wrap gap-2">
                    <button onClick={() => handleApproval('approved')} className="px-4 py-2 bg-green-700 hover:bg-green-600 text-white text-sm rounded-lg font-medium transition-colors">
                      Approve fix
                    </button>
                    <button onClick={() => handleApproval('rejected')} className="px-4 py-2 bg-red-800 hover:bg-red-700 text-white text-sm rounded-lg font-medium transition-colors">
                      Reject
                    </button>
                    <button onClick={() => handleApproval('info_requested')} className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg font-medium transition-colors">
                      Request more info
                    </button>
                  </div>
                ) : (
                  <div className={`flex items-center gap-3 p-3 rounded-lg border ${
                    approvalState === 'approved' ? 'bg-green-950/40 border-green-700/50' :
                    approvalState === 'rejected' ? 'bg-red-950/40 border-red-700/50' :
                    'bg-yellow-950/40 border-yellow-700/50'
                  }`}>
                    <span>{approvalState === 'approved' ? '✅' : approvalState === 'rejected' ? '❌' : '💬'}</span>
                    <p className={`text-sm font-medium ${
                      approvalState === 'approved' ? 'text-green-300' :
                      approvalState === 'rejected' ? 'text-red-300' : 'text-yellow-300'
                    }`}>
                      {approvalState === 'approved'
                        ? 'Manager approved. Resources allocated. Ready to execute DUSK fix.'
                        : approvalState === 'rejected'
                        ? 'Fix rejected. No DUSK action taken.'
                        : 'More information requested. Awaiting response.'}
                    </p>
                    {approvalState !== 'approved' && (
                      <button onClick={() => setApprovalState('pending')} className="ml-auto text-xs text-gray-400 hover:text-white">Reset</button>
                    )}
                  </div>
                )}
              </div>

              {/* Execute fix */}
              {approvalState === 'approved' && !fixResult && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <h4 className="font-semibold text-white mb-2">Execute DUSK Fix</h4>
                  <p className="text-sm text-gray-400 mb-4">
                    Calls <code className="text-blue-400">POST /api/security/fix</code> with
                    DUSK action <code className="text-red-400">{plan?.dusk_action}</code>.
                    {plan?.n8n_soar_trigger && (
                      <span className="text-orange-400"> n8n SOAR will also be triggered.</span>
                    )}
                  </p>
                  <button
                    onClick={handleExecuteFix}
                    disabled={executing}
                    className="w-full py-3 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    {executing ? <><span className="animate-spin">⚙</span> Executing…</> : 'Execute backend fix'}
                  </button>
                </div>
              )}

              {/* Fix result */}
              {fixResult && (
                <div className={`rounded-xl border p-5 ${
                  fixResult.status === 'fixed' ? 'bg-green-950/30 border-green-700/50' :
                  fixResult.status === 'failed' ? 'bg-red-950/30 border-red-700/50' :
                  'bg-yellow-950/30 border-yellow-700/50'
                }`}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xl">{fixResult.status === 'fixed' ? '✅' : fixResult.status === 'failed' ? '❌' : '⏳'}</span>
                    <h4 className="font-semibold text-white">{fixResult.status} — <code className="text-gray-400 text-sm">{fixResult.execution_id}</code></h4>
                  </div>
                  <p className="text-sm text-gray-300 mb-3">{fixResult.message}</p>
                  <div className="space-y-1">
                    {fixResult.logs.map((log, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm text-gray-400">
                        <span className="text-green-500 shrink-0">→</span>{log}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Audit trail */}
      <div className="mt-8">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
          Audit Trail
        </h3>
        <div className="bg-gray-900 border border-gray-800 rounded-xl divide-y divide-gray-800 max-h-80 overflow-y-auto scrollbar-thin">
          {auditTrail.length === 0 ? (
            <p className="text-gray-500 text-sm p-4 text-center">No events yet</p>
          ) : (
            auditTrail.map((event) => (
              <div key={event.id} className="flex items-start gap-3 px-4 py-3">
                <span className="text-lg shrink-0">{EVENT_ICON[event.event_type] ?? '📋'}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium text-gray-300">{formatEventType(event.event_type)}</span>
                    {event.issue_id && <span className="text-xs text-blue-400">{event.issue_id}</span>}
                    {event.metadata?.verdict && (
                      <span className={`text-xs px-1.5 py-0.5 rounded border ${VERDICT_STYLE[event.metadata.verdict] ?? 'bg-gray-800 border-gray-700 text-gray-400'}`}>
                        {event.metadata.verdict}
                      </span>
                    )}
                    <span className="text-xs text-gray-600 ml-auto shrink-0">{formatTime(event.timestamp)}</span>
                  </div>
                  <p className="text-sm text-gray-400 mt-0.5">{event.description}</p>
                  <p className="text-xs text-gray-600 mt-0.5">actor: {event.actor}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
