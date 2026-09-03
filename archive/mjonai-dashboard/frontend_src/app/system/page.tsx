'use client'

import { useState, useEffect } from 'react'
import NavBar from '@/components/NavBar'
import { getSystemStatus, getPsychologyState, getCapitalInfo, getSystemLogs } from '@/lib/api'

// Add to api.ts:
// export const getSystemLogs = (limit = 20) => fetchAPI(`/api/system/logs?limit=${limit}`)

export default function SystemPage() {
  const [status, setStatus]   = useState<any>(null)
  const [psych, setPsych]     = useState<any>(null)
  const [capital, setCapital] = useState<any>(null)
  const [logs, setLogs]       = useState<any[]>([])
  const [lastChecked, setLastChecked] = useState<string>('')

  useEffect(() => {
    // Set time only on client to prevent hydration mismatch
    setLastChecked(new Date().toLocaleString('en-IN'))

    async function load() {
      const [sys, ps, cap] = await Promise.all([
        getSystemStatus(),
        getPsychologyState(),
        getCapitalInfo(),
      ])
      if (sys?.status)    setStatus(sys.status)
      if (ps?.state)      setPsych(ps.state)
      if (cap?.capital)   setCapital(cap.capital)
      setLastChecked(new Date().toLocaleString('en-IN'))
    }

    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  const s = status  || {}
  const p = psych   || {}
  const c = capital || {}

  return (
    <div className="min-h-screen bg-arthai-dark">
      <NavBar />
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold text-white mb-6">System Status</h1>

        {/* System Health */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
          {Object.entries(s.components || {}).map(([name, statusVal]) => (
            <div key={name}
                 className="bg-gray-900 border border-gray-800 rounded-xl p-4
                            flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full
                               ${statusVal === 'connected' || statusVal === 'configured'
                                 ? 'bg-emerald-400'
                                 : 'bg-red-400'}`}
              />
              <div>
                <p className="text-sm font-medium text-white capitalize">{name}</p>
                <p className="text-xs text-gray-500 capitalize">{String(statusVal)}</p>
              </div>
            </div>
          ))}

          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4
                          flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full
                             ${s.market_hours
                               ? 'bg-emerald-400 animate-pulse'
                               : 'bg-gray-600'}`}
            />
            <div>
              <p className="text-sm font-medium text-white">Market</p>
              <p className="text-xs text-gray-500">
                {s.market_hours ? 'Open' : 'Closed'}
              </p>
            </div>
          </div>
        </div>

        {/* Capital Rules */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <h2 className="text-base font-semibold text-white mb-4">
            Capital Protection Rules
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {[
              { rule: 'Max Risk Per Trade',    value: '2%',  safe: true },
              { rule: 'Max Daily Loss',        value: '3%',  safe: true },
              { rule: 'Max Signals Per Day',   value: '4',   safe: true },
              { rule: 'Min Confidence',        value: '65%', safe: true },
              { rule: 'Min Risk:Reward',       value: '1:2', safe: true },
              { rule: 'Min Agent Agreement',   value: '3/4', safe: true },
            ].map((item) => (
              <div key={item.rule}
                   className="flex items-center justify-between
                              bg-gray-800/50 rounded-lg px-4 py-2.5">
                <span className="text-sm text-gray-300">{item.rule}</span>
                <span className={`text-sm font-bold
                                  ${item.safe ? 'text-emerald-400' : 'text-red-400'}`}>
                  ✅ {item.value}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Psychology State */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <h2 className="text-base font-semibold text-white mb-4">
            Psychology Guard (9 Active Checks)
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <div className="bg-gray-800/50 rounded-lg p-3 text-center">
              <div className={`text-xl font-bold
                               ${p.can_trade !== false
                                 ? 'text-emerald-400'
                                 : 'text-red-400'}`}>
                {p.can_trade !== false ? '✅' : '🚫'}
              </div>
              <div className="text-xs text-gray-500 mt-1">Can Trade</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-3 text-center">
              <div className={`text-xl font-bold
                               ${!p.in_cooldown
                                 ? 'text-emerald-400'
                                 : 'text-yellow-400'}`}>
                {!p.in_cooldown ? '✅' : '⏳'}
              </div>
              <div className="text-xs text-gray-500 mt-1">No Cooldown</div>
            </div>
            <div className="bg-gray-800/50 rounded-lg p-3 text-center">
              <div className="text-xl font-bold text-blue-400">
                {p.signals_today || 0}/{p.max_signals || 4}
              </div>
              <div className="text-xs text-gray-500 mt-1">Signals Used</div>
            </div>
          </div>
        </div>

        {/* Version Info */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div>
              <p className="text-white font-semibold">
                ArthAI v{s.version || '1.0.0'}
              </p>
              <p className="text-gray-500 text-sm">Paper Trading Mode Active</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-gray-600">Last checked</p>
              {/* FIXED: client-only render prevents hydration mismatch */}
              <p className="text-xs text-gray-500">
                {lastChecked || '—'}
              </p>
            </div>
          </div>
          <div className="mt-3 text-center text-xs text-gray-700">
            "When in doubt, stay out" | "Capital protection over profit always"
          </div>
        </div>

      </div>
    </div>
  )
}