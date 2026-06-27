'use client'

const sponsors = [
  {
    name: 'Attio',
    emoji: '🗃️',
    status: 'demo',
    color: 'blue',
    description: 'System of record for customers, security opportunities, deployment status, approval records and audit trail.',
    uses: ['Company & contact records', 'Security opportunity tracking', 'Deployment readiness status', 'Execution history & follow-up tasks'],
  },
  {
    name: 'Tavily',
    emoji: '🔍',
    status: 'live',
    color: 'teal',
    description: 'Live threat intel enrichment via DUSK backend (enrich_alert). Searches MITRE technique + action_type for 2026 threat actor reports.',
    uses: ['MITRE ATT&CK threat intel fetch', 'Gate verdict enrichment', 'Customer discovery research'],
  },
  {
    name: 'Superlinked',
    emoji: '🧠',
    status: 'demo',
    color: 'purple',
    description: 'Semantic matching of customers against ideal customer profiles and known risk patterns.',
    uses: ['ICP similarity scoring', 'Security incident pattern matching', 'Vector-based risk anomaly detection'],
  },
  {
    name: 'n8n',
    emoji: '⚙️',
    status: 'live',
    color: 'orange',
    description: 'Live SOAR workflow via demo/n8n_workflow.json. DUSK alert → Format Alert → Open SOAR Incident → Acknowledge. POST /webhook/dusk-alert.',
    uses: ['DUSK alert → SOAR incident', 'Verdict + blast_radius dispatch', 'Manager escalation automation', 'Post-fix notifications'],
  },
  {
    name: 'Mubit Minima',
    emoji: '💡',
    status: 'demo',
    color: 'yellow',
    description: 'Cost-aware model selection for customer classification, risk explanation and fix routing.',
    uses: ['Customer ICP classification', 'Fix recommendation routing', 'Risk explanation summaries'],
  },
  {
    name: 'Google Gemini',
    emoji: '✨',
    status: 'demo',
    color: 'green',
    description: 'Risk explanation generation, deployment plan summaries and manager-facing recommendations.',
    uses: ['Risk explanation in plain English', 'Deployment plan generation', 'Manager recommendation drafts'],
  },
  {
    name: 'Aikido',
    emoji: '🛡️',
    status: 'live',
    color: 'red',
    description: 'Repository security scanning and static vulnerability detection. See docs/aikido-security-report.png.',
    uses: ['Repo vulnerability scan', 'Security report evidence', 'Most Secure Build verification'],
  },
]

const COLOR_MAP: Record<string, string> = {
  blue: 'border-blue-800/50 bg-blue-950/20',
  teal: 'border-teal-800/50 bg-teal-950/20',
  purple: 'border-purple-800/50 bg-purple-950/20',
  orange: 'border-orange-800/50 bg-orange-950/20',
  yellow: 'border-yellow-800/50 bg-yellow-950/20',
  green: 'border-green-800/50 bg-green-950/20',
  red: 'border-red-800/50 bg-red-950/20',
}

const BADGE_MAP: Record<string, string> = {
  live: 'bg-green-900/60 text-green-300 border-green-700',
  demo: 'bg-gray-800 text-gray-400 border-gray-700',
}

export default function SponsorPanel() {
  return (
    <div className="border-t border-gray-800 mt-16">
      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-white">Partner Technology Integrations</h2>
            <p className="text-gray-400 text-sm mt-0.5">
              Trace uses multiple hackathon partner technologies. Green badge = live integration.
              Gray = demo-mode payload ready.
            </p>
          </div>
          <div className="flex gap-2 text-xs shrink-0">
            <span className="px-2.5 py-1 rounded-full border bg-green-900/60 text-green-300 border-green-700">
              live
            </span>
            <span className="px-2.5 py-1 rounded-full border bg-gray-800 text-gray-400 border-gray-700">
              demo
            </span>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {sponsors.map((s) => (
            <div
              key={s.name}
              className={`rounded-xl border p-4 ${COLOR_MAP[s.color] ?? 'border-gray-800 bg-gray-900'}`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-lg">{s.emoji}</span>
                  <span className="font-semibold text-white text-sm">{s.name}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full border ${BADGE_MAP[s.status]}`}>
                  {s.status}
                </span>
              </div>
              <p className="text-gray-400 text-xs mb-2 leading-relaxed">{s.description}</p>
              <ul className="space-y-0.5">
                {s.uses.map((u) => (
                  <li key={u} className="text-gray-500 text-xs flex items-start gap-1.5">
                    <span className="shrink-0 mt-px">·</span>
                    {u}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
