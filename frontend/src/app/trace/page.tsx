'use client'

import { useEffect, useState } from 'react'
import CustomerDiscovery from '@/components/CustomerDiscovery'
import DeploymentWizard from '@/components/DeploymentWizard'
import ExecutionCockpit from '@/components/ExecutionCockpit'
import SponsorPanel from '@/components/SponsorPanel'
import { initialAuditTrail, type AuditEvent } from '@/data/mockAuditTrail'

const EXTERNAL_BACKEND = process.env.NEXT_PUBLIC_BACKEND_API_URL ?? ''

// ── Backend connection badge ──────────────────────────────────────────────────

type BackendStatus = 'checking' | 'live' | 'fallback'

function BackendBadge() {
  const [status, setStatus] = useState<BackendStatus>(EXTERNAL_BACKEND ? 'checking' : 'fallback')
  const [detail, setDetail] = useState('')

  useEffect(() => {
    if (!EXTERNAL_BACKEND) return
    fetch(`${EXTERNAL_BACKEND}/api/trace/health`, { signal: AbortSignal.timeout(3000) })
      .then(r => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data: { mode?: string; tavily?: string; n8n?: string }) => {
        setStatus('live')
        const parts = [`mode: ${data.mode ?? 'live'}`]
        if (data.tavily) parts.push(`tavily: ${data.tavily}`)
        if (data.n8n) parts.push(`n8n: ${data.n8n}`)
        setDetail(parts.join(' · '))
      })
      .catch((err: unknown) => {
        setStatus('fallback')
        setDetail(`${EXTERNAL_BACKEND} unreachable — ${err instanceof Error ? err.message : 'error'}`)
      })
  }, [])

  if (status === 'checking')
    return (
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium bg-gray-800 text-gray-400 border-gray-700">
        <span className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-pulse" />
        Connecting…
      </span>
    )
  if (status === 'live')
    return (
      <span title={detail} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium bg-green-900/60 text-green-300 border-green-700 cursor-help">
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
        Live backend connected
      </span>
    )
  return (
    <span
      title={EXTERNAL_BACKEND ? detail : 'No external backend — using local Next.js API with DUSK-schema demo data'}
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium bg-yellow-900/40 text-yellow-400 border-yellow-800 cursor-help"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
      {EXTERNAL_BACKEND ? 'Backend unavailable · mock fallback' : 'Demo mode · DUSK schema aligned'}
    </span>
  )
}

// ── KPI cards ─────────────────────────────────────────────────────────────────

const KPI_CARDS = [
  { label: 'Potential Customers', value: '5', icon: '🏢', color: 'border-blue-800/50 bg-blue-950/20' },
  { label: 'Security Issues', value: '5', icon: '⚠️', color: 'border-red-800/50 bg-red-950/20' },
  { label: 'Approved Fixes', value: '2', icon: '✅', color: 'border-green-800/50 bg-green-950/20' },
  { label: 'Partner Integrations', value: '7', icon: '🔗', color: 'border-purple-800/50 bg-purple-950/20' },
]

function KpiCards() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {KPI_CARDS.map(k => (
        <div key={k.label} className={`rounded-xl border p-4 ${k.color}`}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-2xl">{k.icon}</span>
            <span className="text-3xl font-bold text-white">{k.value}</span>
          </div>
          <p className="text-gray-400 text-xs mt-1">{k.label}</p>
        </div>
      ))}
    </div>
  )
}

// ── Backend Security Engine placeholder ───────────────────────────────────────

function BackendEngineCard() {
  const [connected, setConnected] = useState<boolean | null>(null)

  useEffect(() => {
    if (!EXTERNAL_BACKEND) { setConnected(false); return }
    fetch(`${EXTERNAL_BACKEND}/api/trace/health`, { signal: AbortSignal.timeout(3000) })
      .then(r => setConnected(r.ok))
      .catch(() => setConnected(false))
  }, [])

  const badge =
    connected === null
      ? <span className="px-2 py-0.5 rounded text-xs bg-gray-800 text-gray-400 border border-gray-700">Checking…</span>
      : connected
      ? <span className="px-2 py-0.5 rounded text-xs bg-green-900/60 text-green-300 border border-green-700">Connected</span>
      : <span className="px-2 py-0.5 rounded text-xs bg-yellow-900/40 text-yellow-400 border border-yellow-800">Demo mode</span>

  return (
    <div className="rounded-xl border border-gray-700 bg-gray-900/60 p-5">
      <div className="flex items-start justify-between gap-4 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xl">🛡️</span>
          <h3 className="font-semibold text-white text-sm">Backend Security Engine</h3>
        </div>
        {badge}
      </div>
      <p className="text-gray-400 text-xs leading-relaxed mb-4">
        The backend engine detects agent, API and database risks, then returns issues, plans and
        execution logs to this frontend.
      </p>
      <div className="grid grid-cols-2 gap-2 text-xs mb-4">
        {[
          ['Gate verdicts', 'ActionGate.evaluate()'],
          ['Network alerts', 'AlertResponder._persist()'],
          ['Tavily enrichment', 'enrich_alert()'],
          ['SOAR trigger', 'n8n webhook'],
        ].map(([label, src]) => (
          <div key={label} className="bg-gray-800/60 rounded-lg p-2.5">
            <div className="text-white font-medium mb-0.5">{label}</div>
            <div className="text-gray-500 font-mono text-[10px]">{src}</div>
          </div>
        ))}
      </div>
      <button
        disabled
        className="w-full px-3 py-2 rounded-lg text-xs bg-gray-800 border border-gray-700 text-gray-500 cursor-not-allowed"
      >
        Open backend dashboard — handled by backend team
      </button>
    </div>
  )
}

// ── Audit Trail panel ─────────────────────────────────────────────────────────

const EVENT_ICON: Record<string, string> = {
  issue_detected: '🔍',
  tavily_enrichment: '🌐',
  approval_requested: '📧',
  manager_approved: '✅',
  manager_rejected: '❌',
  resource_allocated: '🔧',
  fix_triggered: '⚡',
  fix_executed: '⚡',
  backend_response: '📡',
  n8n_soar_triggered: '⚙️',
  attio_updated: '🗃️',
  issue_selected: '👁️',
  issue_detected_backend: '🔍',
}

function fmtTime(ts: string | number) {
  const d = typeof ts === 'number' ? new Date(ts * 1000) : new Date(ts)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function AuditTrailPanel() {
  const [events, setEvents] = useState<AuditEvent[]>(initialAuditTrail)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const url = EXTERNAL_BACKEND
      ? `${EXTERNAL_BACKEND}/api/security/audit`
      : '/api/security/audit'
    setLoading(true)
    fetch(url)
      .then(r => (r.ok ? r.json() : Promise.reject()))
      .then((data: AuditEvent[]) => {
        if (Array.isArray(data) && data.length > 0) setEvents(data)
      })
      .catch(() => {/* keep mock */})
      .finally(() => setLoading(false))
  }, [])

  const displayed = events.slice(0, 8)

  return (
    <div className="border-t border-gray-800 bg-gray-900/20">
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-base font-semibold text-white">Audit Trail</h2>
            <p className="text-gray-500 text-xs mt-0.5">
              Every action is recorded with a timestamp and actor.{' '}
              {loading ? 'Loading…' : `Showing last ${displayed.length} events.`}
            </p>
          </div>
          <span className="text-xs text-gray-600">
            {EXTERNAL_BACKEND ? 'Live from backend' : 'Demo data'}
          </span>
        </div>

        <div className="space-y-1">
          {displayed.map((e, i) => (
            <div key={e.id ?? i} className="flex items-start gap-3 py-2 border-b border-gray-800/50 last:border-0">
              <span className="text-sm shrink-0 mt-0.5">{EVENT_ICON[e.event_type] ?? '📋'}</span>
              <div className="flex-1 min-w-0">
                <p className="text-gray-300 text-xs leading-relaxed truncate">{e.description}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-gray-600 text-[10px]">{fmtTime(e.timestamp)}</span>
                  <span className="text-gray-700 text-[10px]">·</span>
                  <span className="text-gray-600 text-[10px]">{e.actor}</span>
                  {e.issue_id && (
                    <>
                      <span className="text-gray-700 text-[10px]">·</span>
                      <span className="text-gray-700 text-[10px] font-mono">{e.issue_id}</span>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

type Tab = 'discovery' | 'deployment' | 'cockpit'

const TABS: { id: Tab; label: string; icon: string; step: number; description: string }[] = [
  { id: 'discovery', label: 'Customer Discovery', icon: '🔍', step: 1, description: 'Find and qualify potential customers using AI research' },
  { id: 'deployment', label: 'Deployment Wizard',  icon: '🚀', step: 2, description: "Safely onboard a customer's agent workflow with DUSK" },
  { id: 'cockpit',   label: 'Execution Cockpit',  icon: '⚡', step: 3, description: 'Approve, resource and execute DUSK security fixes' },
]

const WORKFLOW_STEPS = ['Discover', 'Onboard', 'Approve', 'Execute', 'Audit']

export default function TracePage() {
  const [activeTab, setActiveTab] = useState<Tab>('discovery')

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-blue-700 rounded-xl flex items-center justify-center shrink-0 shadow-lg shadow-blue-900/40">
              <span className="text-white font-bold text-base">T</span>
            </div>
            <div>
              <h1 className="text-xl font-bold text-white leading-tight">Trace Execution Layer</h1>
              <p className="text-gray-400 text-xs hidden sm:block">
                AI Agent Security · Built at {'{Tech: Europe}'} London 2026
              </p>
            </div>
          </div>
          <BackendBadge />
        </div>
      </header>

      {/* Hero */}
      <div className="bg-gray-900/50 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <p className="text-gray-200 text-lg font-medium max-w-2xl leading-snug mb-1">
            Find customers, prepare onboarding, and execute approved AI agent security fixes
            with a full audit trail.
          </p>
          <p className="text-gray-400 text-sm max-w-2xl mb-6">
            A manager-friendly cockpit for AI agent security onboarding, approval and self-healing execution.
            Trace turns backend security findings into approved, resourced and auditable actions.
          </p>

          {/* Workflow bar */}
          <div className="flex flex-wrap items-center gap-1.5">
            {WORKFLOW_STEPS.map((step, i) => (
              <span key={step} className="flex items-center gap-1.5">
                <span className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-xs text-gray-200 font-medium">
                  <span className="w-4 h-4 rounded-full bg-blue-600 text-white text-[10px] flex items-center justify-center font-bold shrink-0">
                    {i + 1}
                  </span>
                  {step}
                </span>
                {i < WORKFLOW_STEPS.length - 1 && <span className="text-gray-600 text-xs">→</span>}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* KPI cards */}
      <div className="max-w-7xl mx-auto px-6 py-6">
        <KpiCards />
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-800 bg-gray-900/30">
        <div className="max-w-7xl mx-auto px-6">
          <nav className="flex gap-0.5">
            {TABS.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`group flex items-center gap-2 px-5 py-4 text-sm font-medium border-b-2 transition-all ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-200 hover:border-gray-700'
                }`}
              >
                <span className="w-5 h-5 rounded-full bg-gray-800 text-gray-400 text-[10px] flex items-center justify-center font-bold shrink-0 group-hover:bg-gray-700 transition-colors">
                  {tab.step}
                </span>
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Tab description */}
      <div className="bg-gray-900/20 border-b border-gray-800/50">
        <div className="max-w-7xl mx-auto px-6 py-2">
          <p className="text-gray-500 text-xs">
            {TABS.find(t => t.id === activeTab)?.description}
          </p>
        </div>
      </div>

      {/* Tab content + Backend Engine sidebar */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex gap-6 items-start">
          <div className="flex-1 min-w-0">
            {activeTab === 'discovery'  && <CustomerDiscovery />}
            {activeTab === 'deployment' && <DeploymentWizard />}
            {activeTab === 'cockpit'    && <ExecutionCockpit />}
          </div>
          <div className="w-72 shrink-0 hidden xl:block">
            <BackendEngineCard />
          </div>
        </div>
      </div>

      {/* Backend engine card for smaller screens */}
      <div className="xl:hidden max-w-7xl mx-auto px-6 pb-8">
        <BackendEngineCard />
      </div>

      {/* Integration Status */}
      <SponsorPanel />

      {/* Audit Trail */}
      <AuditTrailPanel />

      {/* Footer */}
      <div className="border-t border-gray-800 bg-gray-900/30">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between text-xs text-gray-600">
          <span>Trace — AI Agent Security Execution Layer · {'{Tech: Europe}'} London AI Hackathon 2026</span>
          <span>MIT License</span>
        </div>
      </div>
    </div>
  )
}
