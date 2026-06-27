'use client'

import { useState } from 'react'
import { mockCustomers, type Customer } from '@/data/mockCustomers'
import { createAttioOpportunity, triggerN8nWorkflow } from '@/lib/backendClient'

const fitColor = (score: number) => {
  if (score >= 85) return 'text-green-400'
  if (score >= 75) return 'text-yellow-400'
  return 'text-orange-400'
}

const statusBadge = (status: Customer['status']) => {
  const map: Record<Customer['status'], string> = {
    'Ready to create in Attio': 'bg-blue-900/60 text-blue-300 border border-blue-700',
    'Ready to review': 'bg-yellow-900/60 text-yellow-300 border border-yellow-700',
    'Under review': 'bg-purple-900/60 text-purple-300 border border-purple-700',
    'Created in Attio': 'bg-green-900/60 text-green-300 border border-green-700',
  }
  return map[status] ?? 'bg-gray-800 text-gray-400'
}

interface ActionState {
  loading: string | null
  messages: Record<string, string>
  statuses: Record<string, Customer['status']>
}

export default function CustomerDiscovery() {
  const [customers] = useState<Customer[]>(mockCustomers)
  const [actionState, setActionState] = useState<ActionState>({
    loading: null,
    messages: {},
    statuses: {},
  })
  const [pitches, setPitches] = useState<Record<string, boolean>>({})

  const runAction = async (
    key: string,
    fn: () => Promise<{ message: string }>,
    newStatus?: Customer['status']
  ) => {
    setActionState((s) => ({ ...s, loading: key }))
    try {
      const result = await fn()
      setActionState((s) => ({
        ...s,
        loading: null,
        messages: { ...s.messages, [key]: result.message },
        statuses: newStatus ? { ...s.statuses, [key.split('_')[1]]: newStatus } : s.statuses,
      }))
    } catch {
      setActionState((s) => ({
        ...s,
        loading: null,
        messages: { ...s.messages, [key]: 'Error — please try again.' },
      }))
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white mb-1">Customer Discovery</h2>
        <p className="text-gray-400 text-sm mb-1">
          Companies that deploy AI agents without a behavioural security layer are DUSK&apos;s
          target customers. Every agent that can modify infrastructure, access a database, or send
          external messages is an unmonitored control-plane risk.
        </p>
        <p className="text-gray-500 text-xs">
          Powered by <span className="text-teal-400">Tavily</span> (live research) ·{' '}
          <span className="text-purple-400">Superlinked</span> (ICP similarity scoring) ·{' '}
          <span className="text-yellow-400">Mubit</span> (model routing) ·{' '}
          <span className="text-blue-400">Attio</span> (CRM record) ·{' '}
          <span className="text-orange-400">n8n</span> (follow-up automation)
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {customers.map((c) => {
          const status = actionState.statuses[c.id] ?? c.status
          const attioKey = `attio_${c.id}`
          const n8nKey = `n8n_${c.id}`
          const pitchShown = pitches[c.id]

          return (
            <div
              key={c.id}
              className="bg-gray-900 border border-gray-800 rounded-xl p-5 flex flex-col gap-3 hover:border-gray-700 transition-colors"
            >
              {/* Header */}
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="font-semibold text-white text-base">{c.company}</h3>
                  <p className="text-gray-400 text-xs mt-0.5">{c.use_case}</p>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-2xl font-bold ${fitColor(c.fit_score)}`}>
                    {c.fit_score}
                  </div>
                  <div className="text-gray-500 text-xs">fit score</div>
                </div>
              </div>

              {/* Security pain */}
              <div className="bg-red-950/30 border border-red-900/40 rounded-lg p-3">
                <p className="text-red-300 text-xs font-medium mb-0.5">Security pain</p>
                <p className="text-red-200 text-sm">{c.security_pain}</p>
              </div>

              {/* Source */}
              <p className="text-gray-500 text-xs">
                <span className="text-gray-400">Source:</span> {c.source}
              </p>

              {/* Status badge */}
              <span className={`self-start text-xs px-2.5 py-1 rounded-full font-medium ${statusBadge(status)}`}>
                {status}
              </span>

              {/* Suggested pitch */}
              {pitchShown && (
                <div className="bg-blue-950/40 border border-blue-800/40 rounded-lg p-3">
                  <p className="text-blue-300 text-xs font-medium mb-1">Suggested pitch</p>
                  <p className="text-blue-100 text-sm italic">&ldquo;{c.suggested_pitch}&rdquo;</p>
                </div>
              )}

              {/* Action feedback */}
              {actionState.messages[attioKey] && (
                <p className="text-green-400 text-xs bg-green-950/30 border border-green-900/40 rounded p-2">
                  {actionState.messages[attioKey]}
                </p>
              )}
              {actionState.messages[n8nKey] && (
                <p className="text-purple-400 text-xs bg-purple-950/30 border border-purple-900/40 rounded p-2">
                  {actionState.messages[n8nKey]}
                </p>
              )}

              {/* Actions */}
              <div className="flex flex-wrap gap-2 mt-auto pt-1">
                <button
                  onClick={() =>
                    runAction(
                      attioKey,
                      () => createAttioOpportunity(c.id),
                      'Created in Attio'
                    )
                  }
                  disabled={actionState.loading === attioKey || status === 'Created in Attio'}
                  className="flex-1 min-w-[120px] px-3 py-1.5 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-xs rounded-lg font-medium transition-colors"
                >
                  {actionState.loading === attioKey ? 'Creating…' : 'Create in Attio'}
                </button>
                <button
                  onClick={() => setPitches((p) => ({ ...p, [c.id]: !p[c.id] }))}
                  className="flex-1 min-w-[100px] px-3 py-1.5 bg-gray-700 hover:bg-gray-600 text-white text-xs rounded-lg font-medium transition-colors"
                >
                  {pitchShown ? 'Hide pitch' : 'Generate pitch'}
                </button>
                <button
                  onClick={() =>
                    runAction(n8nKey, () =>
                      triggerN8nWorkflow({ customer_id: c.id, workflow: 'follow_up' })
                    )
                  }
                  disabled={actionState.loading === n8nKey}
                  className="flex-1 min-w-[120px] px-3 py-1.5 bg-purple-700 hover:bg-purple-600 disabled:opacity-50 text-white text-xs rounded-lg font-medium transition-colors"
                >
                  {actionState.loading === n8nKey ? 'Triggering…' : 'Trigger n8n follow-up'}
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
