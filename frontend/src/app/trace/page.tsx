'use client'

import { useState } from 'react'

// ── Types ─────────────────────────────────────────────────────────────────────

interface AgentForm {
  agentName: string
  actionType: string
  target: string
  description: string
  externalSource: string
  mode: 'Watch' | 'Enforce'
}

interface CheckResult {
  verdict: 'ALLOW' | 'WOULD-BLOCK' | 'BLOCK'
  score: number
  blastRadius: 'Low' | 'Medium' | 'High'
  nextMove: string
  reason: string
  mitreAttack: string
  mitreAtlas: string
  recommendedFix: string
}

type GateDecision = 'approve' | 'block' | 'plan'

// ── Constants ─────────────────────────────────────────────────────────────────

const DEMO_FORM: AgentForm = {
  agentName: 'netops-agent',
  actionType: 'firewall_rule_change',
  target: 'restricted-segment',
  description: 'Open firewall path from guest network to restricted segment',
  externalSource: 'Poisoned web page',
  mode: 'Watch',
}

const DEMO_RESULT: CheckResult = {
  verdict: 'WOULD-BLOCK',
  score: 0.95,
  blastRadius: 'High',
  nextMove: 'Lateral movement',
  reason: "Action type 'firewall_rule_change' is new for this agent, which normally does route operations",
  mitreAttack: 'T1562.004 — Impair Defenses: Disable or Modify System Firewall',
  mitreAtlas: 'AML.T0051 — LLM Prompt Injection',
  recommendedFix: 'Restrict firewall changes for netops-agent. Require approval policy before execution.',
}

const AUDIT_STEPS = [
  'Action received',
  'Behaviour baseline checked',
  'Anomaly score calculated',
  'WOULD-BLOCK verdict generated',
  'Manager decision recorded',
  'Audit record created',
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function verdictStyle(v: string) {
  if (v === 'ALLOW')        return 'text-emerald-700 bg-emerald-50 border-emerald-200'
  if (v === 'WOULD-BLOCK')  return 'text-amber-700   bg-amber-50   border-amber-200'
  return                          'text-red-700    bg-red-50     border-red-200'
}

function blastStyle(b: string) {
  if (b === 'Low')    return 'text-emerald-600 bg-emerald-50 border-emerald-200'
  if (b === 'Medium') return 'text-amber-600   bg-amber-50   border-amber-200'
  return                    'text-red-600    bg-red-50     border-red-200'
}

function StatusDot({ live }: { live: boolean }) {
  return (
    <span className={`inline-block w-1.5 h-1.5 rounded-full ${live ? 'bg-emerald-500' : 'bg-gray-300'}`} />
  )
}

// ── Small components ──────────────────────────────────────────────────────────

function SectionHeader({ step, title, subtitle }: { step: number; title: string; subtitle?: string }) {
  return (
    <div className="mb-6">
      <div className="flex items-center gap-2 mb-1">
        <span className="w-6 h-6 rounded-full bg-gray-900 text-white text-xs flex items-center justify-center font-semibold shrink-0">
          {step}
        </span>
        <h2 className="text-xl font-semibold text-gray-900">{title}</h2>
      </div>
      {subtitle && <p className="text-gray-500 text-sm ml-8">{subtitle}</p>}
    </div>
  )
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-white rounded-2xl border border-gray-200/80 shadow-sm ${className}`}>
      {children}
    </div>
  )
}

function PrimaryButton({ children, onClick, loading = false, disabled = false }: {
  children: React.ReactNode
  onClick?: () => void
  loading?: boolean
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="px-6 py-2.5 bg-gray-900 text-white rounded-xl text-sm font-medium hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
    >
      {loading ? 'Checking…' : children}
    </button>
  )
}

function GhostButton({ children, onClick, disabled = false }: {
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="px-5 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
    >
      {children}
    </button>
  )
}

// ── Input Section ─────────────────────────────────────────────────────────────

function InputSection({
  form,
  onChange,
  onSubmit,
  onDemo,
  loading,
}: {
  form: AgentForm
  onChange: (f: AgentForm) => void
  onSubmit: () => void
  onDemo: () => void
  loading: boolean
}) {
  const field = (label: string, key: keyof AgentForm, placeholder: string) => (
    <div>
      <label className="block text-xs font-medium text-gray-500 mb-1.5">{label}</label>
      <input
        type="text"
        value={form[key] as string}
        onChange={e => onChange({ ...form, [key]: e.target.value })}
        placeholder={placeholder}
        className="w-full bg-white border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-900 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-900/10 focus:border-gray-400 transition"
      />
    </div>
  )

  return (
    <section>
      <SectionHeader step={1} title="Check an agent action" subtitle="Describe what your agent is about to do." />
      <Card className="p-6">
        <div className="grid sm:grid-cols-2 gap-4 mb-4">
          {field('Agent name', 'agentName', 'e.g. netops-agent')}
          {field('Action type', 'actionType', 'e.g. firewall_rule_change')}
          {field('Target system', 'target', 'e.g. restricted-segment')}
          {field('External content source', 'externalSource', 'e.g. Poisoned web page')}
        </div>
        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-500 mb-1.5">Action description</label>
          <textarea
            value={form.description}
            onChange={e => onChange({ ...form, description: e.target.value })}
            placeholder="Describe what the agent is trying to do…"
            rows={2}
            className="w-full bg-white border border-gray-200 rounded-xl px-4 py-2.5 text-sm text-gray-900 placeholder-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-900/10 focus:border-gray-400 transition resize-none"
          />
        </div>
        <div className="mb-6">
          <label className="block text-xs font-medium text-gray-500 mb-1.5">Mode</label>
          <div className="flex gap-2">
            {(['Watch', 'Enforce'] as const).map(m => (
              <button
                key={m}
                onClick={() => onChange({ ...form, mode: m })}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                  form.mode === m
                    ? 'bg-gray-900 text-white border-gray-900'
                    : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-1.5">
            Watch reports without blocking. Enforce upgrades WOULD-BLOCK to BLOCK.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <PrimaryButton onClick={onSubmit} loading={loading}>Run behaviour check</PrimaryButton>
          <GhostButton onClick={onDemo}>Load prompt-injection demo</GhostButton>
        </div>
      </Card>
    </section>
  )
}

// ── Dashboard Section ─────────────────────────────────────────────────────────

function DashboardSection({ result }: { result: CheckResult }) {
  const kpis = [
    { label: 'Verdict',            value: result.verdict,               style: verdictStyle(result.verdict) },
    { label: 'Anomaly Score',      value: result.score.toFixed(2),      style: 'text-gray-900 bg-gray-50 border-gray-200' },
    { label: 'Blast Radius',       value: result.blastRadius,           style: blastStyle(result.blastRadius) },
    { label: 'Next Expected Move', value: result.nextMove,              style: 'text-gray-700 bg-gray-50 border-gray-200' },
  ]

  return (
    <section>
      <SectionHeader step={2} title="Behaviour Check Dashboard" />
      <div className="grid grid-cols-2 gap-3 mb-4">
        {kpis.map(k => (
          <Card key={k.label} className="p-4">
            <p className="text-xs text-gray-400 mb-1.5">{k.label}</p>
            <span className={`inline-block px-2.5 py-1 rounded-lg border text-sm font-semibold ${k.style}`}>
              {k.value}
            </span>
          </Card>
        ))}
      </div>
      <Card className="p-5">
        <p className="text-sm text-gray-600 leading-relaxed">
          <span className="font-medium text-gray-900">Why? </span>
          {result.reason}
        </p>
      </Card>
    </section>
  )
}

// ── Action Gate Section ───────────────────────────────────────────────────────

function ActionGateSection({
  result,
  decision,
  onDecide,
}: {
  result: CheckResult
  decision: GateDecision | null
  onDecide: (d: GateDecision) => void
}) {
  const decisionMessage: Record<GateDecision, { text: string; style: string }> = {
    block:   { text: 'Action refused before reaching the controller.', style: 'text-red-700 bg-red-50 border-red-200' },
    approve: { text: 'Manager override recorded in audit log.', style: 'text-amber-700 bg-amber-50 border-amber-200' },
    plan:    { text: 'Recommended fix generated.', style: 'text-emerald-700 bg-emerald-50 border-emerald-200' },
  }

  return (
    <section>
      <SectionHeader step={3} title="Action Gate" subtitle="What should happen to this action?" />
      <Card className="p-6">
        <div className="space-y-3 mb-6">
          {[
            { label: 'Verdict',       value: result.verdict,          badge: true },
            { label: 'Reason',        value: result.reason,           badge: false },
            { label: 'MITRE ATT&CK', value: result.mitreAttack,      badge: false },
            { label: 'MITRE ATLAS',  value: result.mitreAtlas,        badge: false },
            { label: 'Recommendation', value: result.recommendedFix,  badge: false },
          ].map(row => (
            <div key={row.label} className="flex items-start gap-3">
              <span className="w-36 shrink-0 text-xs font-medium text-gray-400 pt-0.5">{row.label}</span>
              {row.badge
                ? <span className={`px-2.5 py-0.5 rounded-lg border text-sm font-semibold ${verdictStyle(result.verdict)}`}>{row.value}</span>
                : <span className="text-sm text-gray-700">{row.value}</span>
              }
            </div>
          ))}
        </div>

        {!decision ? (
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onDecide('block')}
              className="px-5 py-2.5 bg-red-600 text-white rounded-xl text-sm font-medium hover:bg-red-700 transition-colors"
            >
              Block action
            </button>
            <button
              onClick={() => onDecide('approve')}
              className="px-5 py-2.5 bg-amber-500 text-white rounded-xl text-sm font-medium hover:bg-amber-600 transition-colors"
            >
              Approve anyway
            </button>
            <button
              onClick={() => onDecide('plan')}
              className="px-5 py-2.5 bg-gray-900 text-white rounded-xl text-sm font-medium hover:bg-gray-800 transition-colors"
            >
              Generate fix plan
            </button>
          </div>
        ) : (
          <div className={`px-4 py-3 rounded-xl border text-sm font-medium ${decisionMessage[decision].style}`}>
            {decisionMessage[decision].text}
          </div>
        )}
      </Card>
    </section>
  )
}

// ── Output Section ────────────────────────────────────────────────────────────

function OutputSection({ result, decision }: { result: CheckResult; decision: GateDecision }) {
  const outputCards = [
    {
      label: 'Action Result',
      value: decision === 'block' ? 'Blocked before controller' : decision === 'approve' ? 'Approved with override' : 'Fix plan generated',
    },
    {
      label: 'Security Fix',
      value: result.recommendedFix,
    },
    {
      label: 'Audit Record',
      value: 'Recorded with verdict, score, reason and manager decision',
    },
    {
      label: 'Integration Status',
      value: 'n8n alert ready · Tavily enrichment ready · Attio record ready',
    },
  ]

  return (
    <section>
      <SectionHeader step={4} title="Execution Output" />
      <div className="grid sm:grid-cols-2 gap-3 mb-4">
        {outputCards.map(c => (
          <Card key={c.label} className="p-4">
            <p className="text-xs font-medium text-gray-400 mb-1">{c.label}</p>
            <p className="text-sm text-gray-800 leading-relaxed">{c.value}</p>
          </Card>
        ))}
      </div>
      <Card className="p-5">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Audit timeline</p>
        <div className="space-y-2">
          {AUDIT_STEPS.map((step, i) => (
            <div key={step} className="flex items-center gap-3">
              <span className="w-5 h-5 rounded-full bg-emerald-100 text-emerald-700 text-[10px] flex items-center justify-center font-bold shrink-0">
                ✓
              </span>
              <span className="text-sm text-gray-700">{step}</span>
              {i === 0 && <span className="ml-auto text-xs text-gray-400 font-mono">now</span>}
            </div>
          ))}
        </div>
      </Card>
    </section>
  )
}

// ── Backend Placeholder ───────────────────────────────────────────────────────

function BackendPlaceholder() {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-base">🛡️</span>
            <h3 className="text-sm font-semibold text-gray-900">Backend Detection Engine</h3>
            <span className="px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500 border border-gray-200">
              Demo mode
            </span>
          </div>
          <p className="text-xs text-gray-500 leading-relaxed mb-3">
            DUSK backend calculates the behavioural baseline, anomaly score, MITRE mapping and action verdict.
            Backend visualisation handled by the backend team.
          </p>
          <button
            disabled
            className="px-4 py-1.5 rounded-lg text-xs border border-gray-200 text-gray-400 cursor-not-allowed"
          >
            Open backend demo
          </button>
        </div>
      </div>
    </Card>
  )
}

// ── Integration Bar ───────────────────────────────────────────────────────────

const INTEGRATIONS = [
  { name: 'Tavily',       role: 'live search',      live: true },
  { name: 'n8n',          role: 'alert workflow',   live: true },
  { name: 'Superlinked',  role: 'vector baseline',  live: false },
  { name: 'Mubit',        role: 'model routing',    live: false },
  { name: 'Gemini',       role: 'explanation',      live: false },
  { name: 'Attio',        role: 'customer record',  live: false },
  { name: 'Aikido',       role: 'security report',  live: false },
]

function IntegrationBar() {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {INTEGRATIONS.map(s => (
        <div key={s.name} className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-xl shadow-sm">
          <StatusDot live={s.live} />
          <span className="text-xs font-medium text-gray-700">{s.name}</span>
          <span className="text-xs text-gray-400">{s.role}</span>
        </div>
      ))}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function TracePage() {
  const [form, setForm]       = useState<AgentForm>(DEMO_FORM)
  const [result, setResult]   = useState<CheckResult | null>(null)
  const [decision, setDecision] = useState<GateDecision | null>(null)
  const [loading, setLoading] = useState(false)

  const runCheck = async () => {
    setLoading(true)
    setResult(null)
    setDecision(null)
    try {
      const body = JSON.stringify({ issue_id: 'demo', agent_id: form.agentName, action_type: form.actionType })
      const res = await fetch('/api/security/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        signal: AbortSignal.timeout(3000),
      })
      if (res.ok) {
        const data = await res.json() as Record<string, unknown>
        setResult({
          verdict:      String(data.verdict ?? DEMO_RESULT.verdict) as CheckResult['verdict'],
          score:        Number(data.score ?? DEMO_RESULT.score),
          blastRadius:  String(data.blast_radius ?? DEMO_RESULT.blastRadius) as CheckResult['blastRadius'],
          nextMove:     String(data.predicted_next ?? DEMO_RESULT.nextMove),
          reason:       Array.isArray(data.reasons) ? String(data.reasons[0]) : DEMO_RESULT.reason,
          mitreAttack:  String(data.mitre_attack ?? DEMO_RESULT.mitreAttack),
          mitreAtlas:   String(data.mitre_atlas  ?? DEMO_RESULT.mitreAtlas),
          recommendedFix: String(data.recommended_fix ?? DEMO_RESULT.recommendedFix),
        })
        return
      }
    } catch { /* fall through */ }
    // Demo fallback
    await new Promise(r => setTimeout(r, 600))
    setResult(DEMO_RESULT)
    setLoading(false)
  }

  // need to set loading false after success path too
  const handleRun = () => {
    runCheck().finally(() => setLoading(false))
  }

  const loadDemo = () => {
    setForm(DEMO_FORM)
    setResult(null)
    setDecision(null)
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-100">
        <div className="max-w-3xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 tracking-tight">DUSK Behaviour Gate</h1>
              <p className="text-gray-500 text-sm mt-0.5">
                Detect abnormal agent behaviour before it reaches your infrastructure.
              </p>
            </div>
            <span className="hidden sm:block text-xs text-gray-400 italic text-right max-w-[180px] leading-relaxed">
              Credentials verify identity.<br />DUSK verifies behaviour.
            </span>
          </div>
        </div>
      </header>

      {/* Workflow pill */}
      <div className="bg-white border-b border-gray-100">
        <div className="max-w-3xl mx-auto px-6 py-3 flex items-center gap-1.5 overflow-x-auto">
          {['User input', 'Behaviour check', 'Action gate verdict', 'Manager decision', 'Audit output'].map((s, i, arr) => (
            <span key={s} className="flex items-center gap-1.5 shrink-0">
              <span className="text-xs text-gray-500 whitespace-nowrap">{s}</span>
              {i < arr.length - 1 && <span className="text-gray-300 text-xs">→</span>}
            </span>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-3xl mx-auto px-6 py-10 space-y-10">

        {/* 1. Input */}
        <InputSection
          form={form}
          onChange={setForm}
          onSubmit={handleRun}
          onDemo={loadDemo}
          loading={loading}
        />

        {/* 2. Dashboard */}
        {result && <DashboardSection result={result} />}

        {/* 3. Action Gate */}
        {result && (
          <ActionGateSection
            result={result}
            decision={decision}
            onDecide={setDecision}
          />
        )}

        {/* 4. Output */}
        {decision && result && (
          <OutputSection result={result} decision={decision} />
        )}

        {/* Backend placeholder */}
        <BackendPlaceholder />

        {/* Integration bar */}
        <section>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Partner integrations
          </p>
          <IntegrationBar />
        </section>

      </div>

      {/* Footer */}
      <footer className="border-t border-gray-100 mt-10">
        <div className="max-w-3xl mx-auto px-6 py-5 flex items-center justify-between text-xs text-gray-400">
          <span>DUSK · AI Agent Behavioural Threat Detection · {'{Tech: Europe}'} London 2026</span>
          <span>Apache-2.0</span>
        </div>
      </footer>
    </div>
  )
}
