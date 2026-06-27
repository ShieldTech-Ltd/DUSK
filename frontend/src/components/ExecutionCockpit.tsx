'use client'

import { useState, useEffect } from 'react'
import { mockIssues, type SecurityIssue, type Severity } from '@/data/mockIssues'
import { mockExecutionPlans, type ExecutionPlan } from '@/data/mockExecutionPlans'
import { initialAuditTrail, type AuditEvent } from '@/data/mockAuditTrail'
import { executeSecurityFix, type FixResult } from '@/lib/backendClient'

const SEVERITY_STYLES: Record<Severity, string> = {
  critical: 'bg-red-900/60 text-red-300 border-red-700',
  high: 'bg-orange-900/60 text-orange-300 border-orange-700',
  medium: 'bg-yellow-900/60 text-yellow-300 border-yellow-700',
  low: 'bg-green-900/60 text-green-300 border-green-700',
}

const SEVERITY_DOT: Record<Severity, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-green-500',
}

const RESOURCE_OPTIONS = [
  'engineering_time',
  'api_access',
  'database_schema_access',
  'agent_workflow_access',
  'customer_test_environment',
]

const formatEventType = (t: AuditEvent['event_type']) =>
  t.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())

const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })

const EVENT_ICON: Record<AuditEvent['event_type'], string> = {
  issue_detected: '🔍',
  approval_requested: '📧',
  manager_approved: '✅',
  manager_rejected: '❌',
  resource_allocated: '🔧',
  fix_triggered: '⚡',
  backend_response: '📡',
  attio_updated: '🗃️',
  n8n_triggered: '⚙️',
  issue_selected: '👁️',
}

export default function ExecutionCockpit() {
  const [issues] = useState<SecurityIssue[]>(mockIssues)
  const [selectedIssue, setSelectedIssue] = useState<SecurityIssue | null>(null)
  const [plan, setPlan] = useState<ExecutionPlan | null>(null)
  const [approvalState, setApprovalState] = useState<
    'pending' | 'approved' | 'rejected' | 'info_requested'
  >('pending')
  const [allocatedResources, setAllocatedResources] = useState<string[]>([])
  const [fixResult, setFixResult] = useState<FixResult | null>(null)
  const [executing, setExecuting] = useState(false)
  const [auditTrail, setAuditTrail] = useState<AuditEvent[]>(initialAuditTrail)
  const [managerEmail, setManagerEmail] = useState('manager@example.com')

  const addAuditEvent = (event: Omit<AuditEvent, 'id' | 'timestamp'>) => {
    const newEvent: AuditEvent = {
      ...event,
      id: `audit_live_${Date.now()}`,
      timestamp: new Date().toISOString(),
    }
    setAuditTrail((prev) => [newEvent, ...prev])
  }

  const selectIssue = (issue: SecurityIssue) => {
    setSelectedIssue(issue)
    setPlan(mockExecutionPlans[issue.id] ?? null)
    setApprovalState('pending')
    setAllocatedResources([])
    setFixResult(null)
    addAuditEvent({
      event_type: 'issue_selected',
      description: `Issue selected for review: ${issue.title}`,
      actor: 'manager',
      issue_id: issue.id,
    })
  }

  const requestApproval = () => {
    addAuditEvent({
      event_type: 'approval_requested',
      description: `Manager approval requested for ${selectedIssue?.title}`,
      actor: 'system',
      issue_id: selectedIssue?.id,
      metadata: { manager: managerEmail },
    })
  }

  const handleApproval = (decision: 'approved' | 'rejected' | 'info_requested') => {
    setApprovalState(decision)
    const descriptions: Record<typeof decision, string> = {
      approved: `Manager approved fix for: ${selectedIssue?.title}`,
      rejected: `Manager rejected fix for: ${selectedIssue?.title}`,
      info_requested: `More information requested for: ${selectedIssue?.title}`,
    }
    const eventTypes: Record<typeof decision, AuditEvent['event_type']> = {
      approved: 'manager_approved',
      rejected: 'manager_rejected',
      info_requested: 'approval_requested',
    }
    addAuditEvent({
      event_type: eventTypes[decision],
      description: descriptions[decision],
      actor: managerEmail,
      issue_id: selectedIssue?.id,
    })
  }

  const toggleResource = (resource: string) => {
    if (allocatedResources.includes(resource)) {
      setAllocatedResources((r) => r.filter((x) => x !== resource))
    } else {
      const next = [...allocatedResources, resource]
      setAllocatedResources(next)
      addAuditEvent({
        event_type: 'resource_allocated',
        description: `Resource allocated: ${resource}`,
        actor: managerEmail,
        issue_id: selectedIssue?.id,
        metadata: { resource },
      })
    }
  }

  const handleExecuteFix = async () => {
    if (!selectedIssue || !plan) return
    setExecuting(true)
    addAuditEvent({
      event_type: 'fix_triggered',
      description: `Backend fix triggered for: ${selectedIssue.title}`,
      actor: managerEmail,
      issue_id: selectedIssue.id,
      metadata: { backend_action: plan.backend_action },
    })
    try {
      const result = await executeSecurityFix({
        issue_id: selectedIssue.id,
        approved_by: managerEmail,
        resources: allocatedResources,
        action_plan: plan.recommended_fix,
      })
      setFixResult(result)
      addAuditEvent({
        event_type: 'backend_response',
        description: `Backend responded: ${result.status} — ${result.message}`,
        actor: 'system',
        issue_id: selectedIssue.id,
        metadata: { execution_id: result.execution_id, status: result.status },
      })
      addAuditEvent({
        event_type: 'attio_updated',
        description: `Attio customer record updated for ${selectedIssue.customer}`,
        actor: 'system',
        issue_id: selectedIssue.id,
      })
      addAuditEvent({
        event_type: 'n8n_triggered',
        description: 'n8n post-fix notification workflow triggered',
        actor: 'system',
        issue_id: selectedIssue.id,
      })
    } finally {
      setExecuting(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white mb-1">Execution Cockpit</h2>
        <p className="text-gray-400 text-sm">
          Review security issues detected by the backend, approve fixes, allocate resources and
          trigger execution.
        </p>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Issue Inbox */}
        <div className="xl:col-span-1">
          <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Issue Inbox
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
                  <div className={`w-2.5 h-2.5 rounded-full mt-1 shrink-0 ${SEVERITY_DOT[issue.severity]}`} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white leading-tight mb-1">
                      {issue.title}
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      <span className={`text-xs px-2 py-0.5 rounded-full border ${SEVERITY_STYLES[issue.severity]}`}>
                        {issue.severity}
                      </span>
                      <span className="text-xs text-gray-500">{issue.customer}</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Detail Panel */}
        <div className="xl:col-span-2 space-y-4">
          {!selectedIssue ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center">
              <p className="text-gray-500 text-sm">Select an issue from the inbox to begin</p>
            </div>
          ) : (
            <>
              {/* Issue Detail */}
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <div className="flex items-start justify-between gap-4 mb-4">
                  <div>
                    <h3 className="font-semibold text-white mb-1">{selectedIssue.title}</h3>
                    <p className="text-gray-400 text-sm">
                      {selectedIssue.customer} · {selectedIssue.affected_system}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 text-xs px-2.5 py-1 rounded-full border font-medium ${SEVERITY_STYLES[selectedIssue.severity]}`}
                  >
                    {selectedIssue.severity}
                  </span>
                </div>
                <div className="bg-red-950/30 border border-red-900/40 rounded-lg p-3 mb-3">
                  <p className="text-red-300 text-xs font-medium mb-0.5">Evidence</p>
                  <p className="text-red-200 text-sm">{selectedIssue.evidence}</p>
                </div>
                <p className="text-gray-500 text-xs">Source: {selectedIssue.source}</p>
              </div>

              {/* Execution Plan */}
              {plan && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <h4 className="font-semibold text-white mb-3">Execution Plan</h4>
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-gray-400 mb-1">Recommended fix</p>
                      <p className="text-sm text-gray-200">{plan.recommended_fix}</p>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-xs text-gray-400 mb-1">Required permissions</p>
                        <div className="flex flex-wrap gap-1">
                          {plan.required_permissions.map((p) => (
                            <span key={p} className="text-xs px-2 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-300">
                              {p}
                            </span>
                          ))}
                        </div>
                      </div>
                      <div>
                        <p className="text-xs text-gray-400 mb-1">Risk after fix</p>
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                          plan.risk_after_fix === 'low'
                            ? 'bg-green-900/60 text-green-300 border-green-700'
                            : plan.risk_after_fix === 'medium'
                            ? 'bg-yellow-900/60 text-yellow-300 border-yellow-700'
                            : 'bg-red-900/60 text-red-300 border-red-700'
                        }`}>
                          {plan.risk_after_fix}
                        </span>
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-gray-400 mb-1">Rollback plan</p>
                      <p className="text-sm text-gray-400 italic">{plan.rollback_plan}</p>
                    </div>
                    <div className="flex items-center gap-2 text-xs text-gray-500">
                      <span>Backend action: <code className="text-blue-400">{plan.backend_action}</code></span>
                      <span>·</span>
                      <span>Est. time: {plan.estimated_time}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Manager Approval */}
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

                {/* Resources */}
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

                {/* Approval buttons */}
                {approvalState === 'pending' ? (
                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={requestApproval}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg font-medium transition-colors"
                    >
                      Request approval
                    </button>
                    <button
                      onClick={() => handleApproval('approved')}
                      className="px-4 py-2 bg-green-700 hover:bg-green-600 text-white text-sm rounded-lg font-medium transition-colors"
                    >
                      Approve fix
                    </button>
                    <button
                      onClick={() => handleApproval('rejected')}
                      className="px-4 py-2 bg-red-800 hover:bg-red-700 text-white text-sm rounded-lg font-medium transition-colors"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleApproval('info_requested')}
                      className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg font-medium transition-colors"
                    >
                      Request more info
                    </button>
                  </div>
                ) : (
                  <div className={`flex items-center gap-3 p-3 rounded-lg border ${
                    approvalState === 'approved'
                      ? 'bg-green-950/40 border-green-700/50'
                      : approvalState === 'rejected'
                      ? 'bg-red-950/40 border-red-700/50'
                      : 'bg-yellow-950/40 border-yellow-700/50'
                  }`}>
                    <span>
                      {approvalState === 'approved' ? '✅' : approvalState === 'rejected' ? '❌' : '💬'}
                    </span>
                    <p className={`text-sm font-medium ${
                      approvalState === 'approved'
                        ? 'text-green-300'
                        : approvalState === 'rejected'
                        ? 'text-red-300'
                        : 'text-yellow-300'
                    }`}>
                      {approvalState === 'approved'
                        ? 'Manager approved. Resources allocated. Ready to execute backend fix.'
                        : approvalState === 'rejected'
                        ? 'Manager rejected the fix. No action taken.'
                        : 'More information requested. Awaiting response.'}
                    </p>
                    {approvalState !== 'approved' && (
                      <button
                        onClick={() => setApprovalState('pending')}
                        className="ml-auto text-xs text-gray-400 hover:text-white"
                      >
                        Reset
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Execute Fix */}
              {approvalState === 'approved' && !fixResult && (
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <h4 className="font-semibold text-white mb-3">Execute Fix</h4>
                  <p className="text-sm text-gray-400 mb-4">
                    Calls{' '}
                    <code className="text-blue-400">POST /api/security/fix</code> with the approved
                    plan and allocated resources.
                  </p>
                  <button
                    onClick={handleExecuteFix}
                    disabled={executing}
                    className="w-full py-3 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-white font-semibold rounded-lg transition-colors flex items-center justify-center gap-2"
                  >
                    {executing ? (
                      <>
                        <span className="animate-spin">⚙</span> Executing…
                      </>
                    ) : (
                      'Execute backend fix'
                    )}
                  </button>
                </div>
              )}

              {/* Fix Result */}
              {fixResult && (
                <div className={`rounded-xl border p-5 ${
                  fixResult.status === 'fixed'
                    ? 'bg-green-950/30 border-green-700/50'
                    : fixResult.status === 'failed'
                    ? 'bg-red-950/30 border-red-700/50'
                    : 'bg-yellow-950/30 border-yellow-700/50'
                }`}>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xl">
                      {fixResult.status === 'fixed' ? '✅' : fixResult.status === 'failed' ? '❌' : '⏳'}
                    </span>
                    <h4 className="font-semibold text-white">
                      Execution {fixResult.status} — {fixResult.execution_id}
                    </h4>
                  </div>
                  <p className="text-sm text-gray-300 mb-3">{fixResult.message}</p>
                  <div className="space-y-1">
                    {fixResult.logs.map((log, i) => (
                      <div key={i} className="flex items-center gap-2 text-sm text-gray-400">
                        <span className="text-green-500 shrink-0">→</span>
                        {log}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Audit Trail */}
      <div className="mt-8">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
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
                    <span className="text-xs font-medium text-gray-300">
                      {formatEventType(event.event_type)}
                    </span>
                    {event.issue_id && (
                      <span className="text-xs text-blue-400">{event.issue_id}</span>
                    )}
                    <span className="text-xs text-gray-600 ml-auto shrink-0">
                      {formatTime(event.timestamp)}
                    </span>
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
