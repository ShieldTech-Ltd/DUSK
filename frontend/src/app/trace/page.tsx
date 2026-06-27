'use client'

import { useState } from 'react'
import CustomerDiscovery from '@/components/CustomerDiscovery'
import DeploymentWizard from '@/components/DeploymentWizard'
import ExecutionCockpit from '@/components/ExecutionCockpit'
import SponsorPanel from '@/components/SponsorPanel'

const EXTERNAL_BACKEND = process.env.NEXT_PUBLIC_BACKEND_API_URL ?? ''

function BackendBadge() {
  if (EXTERNAL_BACKEND) {
    return (
      <span
        title={`All API calls proxied to ${EXTERNAL_BACKEND}`}
        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium bg-green-900/60 text-green-300 border-green-700"
      >
        <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
        Live backend connected
      </span>
    )
  }
  return (
    <span
      title="NEXT_PUBLIC_BACKEND_API_URL not set — using local Next.js API routes with DUSK-schema demo data. Set the env var to proxy to a real backend."
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-medium bg-yellow-900/40 text-yellow-400 border-yellow-800 cursor-help"
    >
      <span className="w-1.5 h-1.5 rounded-full bg-yellow-400" />
      Demo mode · DUSK schema aligned
    </span>
  )
}

type Tab = 'discovery' | 'deployment' | 'cockpit'

const TABS: { id: Tab; label: string; icon: string; description: string }[] = [
  {
    id: 'discovery',
    label: 'Customer Discovery',
    icon: '🔍',
    description: 'Find and qualify potential customers automatically',
  },
  {
    id: 'deployment',
    label: 'Deployment Wizard',
    icon: '🚀',
    description: 'Safely onboard customer agent workflows',
  },
  {
    id: 'cockpit',
    label: 'Execution Cockpit',
    icon: '⚡',
    description: 'Approve, resource and execute security fixes',
  },
]

export default function TracePage() {
  const [activeTab, setActiveTab] = useState<Tab>('discovery')

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-blue-700 rounded-xl flex items-center justify-center shrink-0 shadow-lg shadow-blue-900/40">
                <span className="text-white font-bold text-base">T</span>
              </div>
              <div>
                <h1 className="text-xl font-bold text-white leading-tight">Trace Execution Layer</h1>
                <p className="text-gray-400 text-xs hidden sm:block">
                  AI Agent Security Execution and Deployment Layer · Built at {'{Tech: Europe}'} London 2026
                </p>
              </div>
            </div>
            <div className="shrink-0">
              <BackendBadge />
            </div>
          </div>
        </div>
      </header>

      {/* Hero */}
      <div className="bg-gray-900/40 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <p className="text-gray-300 text-base max-w-2xl leading-relaxed mb-4">
            Find customers, onboard agent workflows and execute approved security fixes with a
            complete audit trail.
          </p>
          <div className="bg-blue-950/50 border border-blue-800/50 rounded-xl p-4 max-w-2xl">
            <p className="text-blue-200 text-sm leading-relaxed">
              <span className="font-semibold text-blue-100">What is Trace?</span> Trace sits between
              AI agent security detection and real business execution. It turns detected security
              issues into approved, resourced and auditable fixes — giving managers control and
              giving customers confidence.
            </p>
          </div>

          {/* Quick flow diagram */}
          <div className="mt-6 flex flex-wrap items-center gap-2 text-xs text-gray-500">
            {[
              'Tavily discovers customers',
              'Superlinked scores fit',
              'Deployment wizard onboards',
              'Backend detects issues',
              'Manager approves fix',
              'Backend executes',
              'Attio records audit',
            ].map((step, i, arr) => (
              <span key={step} className="flex items-center gap-2">
                <span className="px-2.5 py-1 bg-gray-800 border border-gray-700 rounded-lg text-gray-300">
                  {step}
                </span>
                {i < arr.length - 1 && <span className="text-gray-700">→</span>}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-800 bg-gray-900/30">
        <div className="max-w-7xl mx-auto px-6">
          <nav className="flex gap-0.5">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`group flex items-center gap-2 px-5 py-4 text-sm font-medium border-b-2 transition-all ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-200 hover:border-gray-700'
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </nav>
        </div>
      </div>

      {/* Tab description bar */}
      <div className="bg-gray-900/20 border-b border-gray-800/50">
        <div className="max-w-7xl mx-auto px-6 py-2">
          <p className="text-gray-500 text-xs">
            {TABS.find((t) => t.id === activeTab)?.description}
          </p>
        </div>
      </div>

      {/* Tab Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {activeTab === 'discovery' && <CustomerDiscovery />}
        {activeTab === 'deployment' && <DeploymentWizard />}
        {activeTab === 'cockpit' && <ExecutionCockpit />}
      </main>

      {/* Sponsor Integration Panel */}
      <SponsorPanel />

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
