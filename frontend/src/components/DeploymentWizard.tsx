'use client'

import { useState } from 'react'
import { prepareDeployment, registerDeployment, type DeploymentConfig, type DeploymentPackage } from '@/lib/backendClient'

const DEPLOYMENT_MODES = [
  { value: 'shadow_monitoring', label: 'Shadow monitoring — observe without blocking' },
  { value: 'approval_gate', label: 'Approval gate — require sign-off before each action' },
  { value: 'active_self_healing', label: 'Active self-healing — auto-fix detected issues' },
] as const

const defaultForm: DeploymentConfig = {
  company: '',
  agent_workflow_url: '',
  api_access_type: '',
  database_type: '',
  tool_list: [],
  approval_manager_email: '',
  allowed_actions: [],
  blocked_actions: [],
  test_environment_url: '',
  deployment_mode: 'shadow_monitoring',
}

function TagInput({
  label,
  values,
  onChange,
  placeholder,
}: {
  label: string
  values: string[]
  onChange: (v: string[]) => void
  placeholder: string
}) {
  const [input, setInput] = useState('')

  const add = () => {
    const trimmed = input.trim()
    if (trimmed && !values.includes(trimmed)) {
      onChange([...values, trimmed])
      setInput('')
    }
  }

  return (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1">{label}</label>
      <div className="flex gap-2 mb-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder={placeholder}
          className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
        />
        <button
          type="button"
          onClick={add}
          className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg transition-colors"
        >
          Add
        </button>
      </div>
      {values.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {values.map((v) => (
            <span
              key={v}
              className="inline-flex items-center gap-1 px-2.5 py-1 bg-gray-800 border border-gray-700 rounded-full text-xs text-gray-300"
            >
              {v}
              <button
                type="button"
                onClick={() => onChange(values.filter((x) => x !== v))}
                className="text-gray-500 hover:text-red-400 ml-0.5"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

export default function DeploymentWizard() {
  const [form, setForm] = useState<DeploymentConfig>(defaultForm)
  const [pkg, setPkg] = useState<DeploymentPackage | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [step, setStep] = useState<1 | 2 | 3>(1)

  const set = <K extends keyof DeploymentConfig>(k: K, v: DeploymentConfig[K]) =>
    setForm((f) => ({ ...f, [k]: v }))

  const handleGenerate = async () => {
    if (!form.company) return
    setLoading('generate')
    try {
      const result = await prepareDeployment(form)
      setPkg(result)
      setStep(2)
      setMessage('Demo mode: deployment package generated and ready for backend registration.')
    } finally {
      setLoading(null)
    }
  }

  const handleRegister = async () => {
    if (!pkg) return
    setLoading('register')
    try {
      const result = await registerDeployment(pkg.deployment_id)
      setMessage(result.message)
      setStep(3)
    } finally {
      setLoading(null)
    }
  }

  const inputCls =
    'w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500'
  const labelCls = 'block text-sm font-medium text-gray-300 mb-1'

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-white mb-1">Deployment Wizard</h2>
        <p className="text-gray-400 text-sm">
          Generate a secure deployment package for onboarding a customer into the Trace
          execution layer.
        </p>
      </div>

      {/* Warning */}
      <div className="mb-6 bg-yellow-950/40 border border-yellow-700/50 rounded-xl p-4 flex gap-3">
        <span className="text-yellow-400 text-xl shrink-0">⚠</span>
        <p className="text-yellow-200 text-sm">
          Do not paste production API keys or database credentials into this demo. Production
          deployment should use secure secret management.
        </p>
      </div>

      {/* Steps */}
      <div className="flex gap-2 mb-8">
        {(['Configure', 'Review package', 'Register'] as const).map((label, i) => {
          const stepNum = (i + 1) as 1 | 2 | 3
          const active = step === stepNum
          const done = step > stepNum
          return (
            <div key={label} className="flex items-center gap-2 flex-1">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-bold shrink-0 ${
                  done
                    ? 'bg-green-700 text-white'
                    : active
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-800 text-gray-500'
                }`}
              >
                {done ? '✓' : stepNum}
              </div>
              <span className={`text-sm font-medium ${active ? 'text-white' : 'text-gray-500'}`}>
                {label}
              </span>
              {i < 2 && <div className="flex-1 h-px bg-gray-800 mx-2" />}
            </div>
          )
        })}
      </div>

      {/* Step 1: Form */}
      {step === 1 && (
        <div className="space-y-5 bg-gray-900 border border-gray-800 rounded-xl p-6">
          <div className="grid gap-5 md:grid-cols-2">
            <div>
              <label className={labelCls}>Company name *</label>
              <input
                type="text"
                value={form.company}
                onChange={(e) => set('company', e.target.value)}
                placeholder="Acme AI Ops"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>Approval manager email</label>
              <input
                type="email"
                value={form.approval_manager_email}
                onChange={(e) => set('approval_manager_email', e.target.value)}
                placeholder="manager@example.com"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>Agent workflow URL or JSON path</label>
              <input
                type="text"
                value={form.agent_workflow_url}
                onChange={(e) => set('agent_workflow_url', e.target.value)}
                placeholder="https://example.com/agent-workflow.json"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>Test environment URL</label>
              <input
                type="text"
                value={form.test_environment_url}
                onChange={(e) => set('test_environment_url', e.target.value)}
                placeholder="https://staging.example.com"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>API access type</label>
              <input
                type="text"
                value={form.api_access_type}
                onChange={(e) => set('api_access_type', e.target.value)}
                placeholder="REST / GraphQL / gRPC"
                className={inputCls}
              />
            </div>
            <div>
              <label className={labelCls}>Database type</label>
              <input
                type="text"
                value={form.database_type}
                onChange={(e) => set('database_type', e.target.value)}
                placeholder="PostgreSQL / MongoDB / etc."
                className={inputCls}
              />
            </div>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            <TagInput
              label="Tool list"
              values={form.tool_list}
              onChange={(v) => set('tool_list', v)}
              placeholder="email_tool"
            />
            <TagInput
              label="Allowed actions"
              values={form.allowed_actions}
              onChange={(v) => set('allowed_actions', v)}
              placeholder="crm_read"
            />
            <TagInput
              label="Blocked actions"
              values={form.blocked_actions}
              onChange={(v) => set('blocked_actions', v)}
              placeholder="export_contacts"
            />
          </div>

          <div>
            <label className={labelCls}>Deployment mode</label>
            <div className="space-y-2">
              {DEPLOYMENT_MODES.map((m) => (
                <label
                  key={m.value}
                  className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    form.deployment_mode === m.value
                      ? 'border-blue-600 bg-blue-950/40'
                      : 'border-gray-700 bg-gray-800/50 hover:border-gray-600'
                  }`}
                >
                  <input
                    type="radio"
                    name="deployment_mode"
                    value={m.value}
                    checked={form.deployment_mode === m.value}
                    onChange={() => set('deployment_mode', m.value)}
                    className="mt-0.5 accent-blue-500"
                  />
                  <span className="text-sm text-gray-200">{m.label}</span>
                </label>
              ))}
            </div>
          </div>

          <button
            onClick={handleGenerate}
            disabled={!form.company || loading === 'generate'}
            className="w-full py-3 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors"
          >
            {loading === 'generate' ? 'Generating…' : 'Generate deployment package'}
          </button>
        </div>
      )}

      {/* Step 2: Review */}
      {step === 2 && pkg && (
        <div className="space-y-4">
          {message && (
            <div className="bg-green-950/40 border border-green-700/50 rounded-lg p-3 text-green-300 text-sm">
              {message}
            </div>
          )}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-white">Deployment package</h3>
              <span className="text-xs px-2.5 py-1 bg-yellow-900/60 text-yellow-300 border border-yellow-700 rounded-full">
                {pkg.status.replace(/_/g, ' ')}
              </span>
            </div>
            <pre className="text-sm text-gray-300 bg-gray-950 border border-gray-800 rounded-lg p-4 overflow-x-auto">
              {JSON.stringify(pkg, null, 2)}
            </pre>
          </div>
          <div className="flex gap-3">
            <button
              onClick={() => setStep(1)}
              className="px-5 py-2.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg font-medium transition-colors"
            >
              Edit
            </button>
            <button
              onClick={() => {/* request approval — mock */
                setMessage('Demo mode: manager approval email sent to ' + (pkg.manager_email || 'manager@example.com'))
              }}
              className="px-5 py-2.5 bg-purple-700 hover:bg-purple-600 text-white text-sm rounded-lg font-medium transition-colors"
            >
              Request manager approval
            </button>
            <button
              onClick={handleRegister}
              disabled={loading === 'register'}
              className="flex-1 py-2.5 bg-blue-700 hover:bg-blue-600 disabled:opacity-50 text-white text-sm rounded-lg font-semibold transition-colors"
            >
              {loading === 'register' ? 'Registering…' : 'Register with backend'}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Confirmed */}
      {step === 3 && (
        <div className="bg-green-950/30 border border-green-700/50 rounded-xl p-8 text-center">
          <div className="text-4xl mb-4">✓</div>
          <h3 className="text-xl font-semibold text-green-300 mb-2">Deployment registered</h3>
          <p className="text-green-200 text-sm mb-2">{message}</p>
          <p className="text-gray-400 text-sm">
            The deployment package has been sent to the backend. Trace will begin{' '}
            <span className="text-white">
              {form.deployment_mode.replace(/_/g, ' ')}
            </span>{' '}
            once the backend confirms registration.
          </p>
          <button
            onClick={() => { setStep(1); setForm(defaultForm); setPkg(null); setMessage(null) }}
            className="mt-6 px-6 py-2.5 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded-lg font-medium transition-colors"
          >
            New deployment
          </button>
        </div>
      )}
    </div>
  )
}
