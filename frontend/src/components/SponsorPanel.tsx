'use client'

import { useEffect, useState } from 'react'

interface SponsorRow {
  name: string
  emoji: string
  role: string
  statusKey: string
}

const SPONSORS: SponsorRow[] = [
  { name: 'Attio',         emoji: '🗃️', role: 'Customer and execution system of record',   statusKey: 'attio' },
  { name: 'Tavily',        emoji: '🔍', role: 'Customer discovery and threat enrichment',  statusKey: 'tavily' },
  { name: 'Superlinked',   emoji: '🧠', role: 'ICP similarity matching',                   statusKey: 'superlinked' },
  { name: 'n8n',           emoji: '⚙️', role: 'Approval workflow and SOAR automation',     statusKey: 'n8n' },
  { name: 'Mubit',         emoji: '💡', role: 'Cost-aware model routing',                  statusKey: 'mubit' },
  { name: 'Gemini',        emoji: '✨', role: 'Risk explanation and plan generation',      statusKey: 'gemini' },
  { name: 'Aikido',        emoji: '🛡️', role: 'Repo security scan evidence',              statusKey: 'aikido' },
]

type IntegrationStatuses = Record<string, string>

const FALLBACK: IntegrationStatuses = {
  attio: 'demo_mode',
  tavily: 'demo_mode',
  superlinked: 'demo_mode',
  n8n: 'demo_mode',
  mubit: 'demo_mode',
  gemini: 'demo_mode',
  aikido: 'screenshot_required',
}

function statusBadge(raw: string) {
  if (raw === 'live')
    return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-green-900/60 text-green-300 border border-green-700">Live</span>
  if (raw === 'demo_mode')
    return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-gray-800 text-gray-400 border border-gray-700">Demo</span>
  if (raw === 'screenshot_required' || raw === 'missing_key')
    return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-yellow-900/40 text-yellow-400 border border-yellow-800">{raw === 'screenshot_required' ? 'Screenshot required' : 'Missing key'}</span>
  return <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-gray-800 text-gray-400 border border-gray-700">{raw}</span>
}

const EXTERNAL_BACKEND = process.env.NEXT_PUBLIC_BACKEND_API_URL ?? ''

export default function SponsorPanel() {
  const [statuses, setStatuses] = useState<IntegrationStatuses>(FALLBACK)
  const [source, setSource] = useState<'api' | 'local' | 'fallback'>('fallback')

  useEffect(() => {
    const urls = [
      EXTERNAL_BACKEND ? `${EXTERNAL_BACKEND}/api/trace/integration-status` : null,
      '/api/trace/integration-status',
    ].filter(Boolean) as string[]

    let done = false
    const tryNext = (i: number) => {
      if (i >= urls.length || done) return
      fetch(urls[i], { signal: AbortSignal.timeout(3000) })
        .then(r => (r.ok ? r.json() : Promise.reject()))
        .then((data: IntegrationStatuses) => {
          if (!done) {
            done = true
            setStatuses({ ...FALLBACK, ...data })
            setSource(i === 0 && EXTERNAL_BACKEND ? 'api' : 'local')
          }
        })
        .catch(() => tryNext(i + 1))
    }
    tryNext(0)
  }, [])

  return (
    <div className="border-t border-gray-800 bg-gray-900/20">
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-white">Partner Integration Status</h2>
            <p className="text-gray-500 text-xs mt-0.5">
              Green = live integration active. Demo = payload-ready, key not set.{' '}
              <span className="text-gray-600">
                {source === 'api' ? 'Status from live backend.' : source === 'local' ? 'Status from local API.' : 'Showing defaults.'}
              </span>
            </p>
          </div>
          <div className="flex gap-2 shrink-0">
            <span className="px-2 py-0.5 rounded text-[11px] border bg-green-900/60 text-green-300 border-green-700">Live</span>
            <span className="px-2 py-0.5 rounded text-[11px] border bg-gray-800 text-gray-400 border-gray-700">Demo</span>
          </div>
        </div>

        <div className="rounded-xl border border-gray-800 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-800 bg-gray-900/60">
                <th className="text-left px-4 py-2.5 text-gray-500 text-xs font-medium w-8"></th>
                <th className="text-left px-4 py-2.5 text-gray-500 text-xs font-medium">Partner</th>
                <th className="text-left px-4 py-2.5 text-gray-500 text-xs font-medium">Role in Trace</th>
                <th className="text-right px-4 py-2.5 text-gray-500 text-xs font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {SPONSORS.map((s, i) => (
                <tr
                  key={s.name}
                  className={`border-b border-gray-800/50 last:border-0 ${i % 2 === 0 ? 'bg-gray-900/20' : ''}`}
                >
                  <td className="px-4 py-3 text-base">{s.emoji}</td>
                  <td className="px-4 py-3">
                    <span className="text-white text-sm font-medium">{s.name}</span>
                  </td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{s.role}</td>
                  <td className="px-4 py-3 text-right">{statusBadge(statuses[s.statusKey] ?? 'demo_mode')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
