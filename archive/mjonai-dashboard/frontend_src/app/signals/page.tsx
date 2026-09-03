'use client'

import { useState, useEffect } from 'react'
import NavBar from '@/components/NavBar'
import SignalCard from '@/components/SignalCard'
import { getSignals, getSignalStats, getSignalRejections } from '@/lib/api'

export default function SignalsPage() {
  const [signals, setSignals] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [rejections, setRejections] = useState<any[]>([])
  const [filter, setFilter] = useState('all')
  const [tab, setTab] = useState('signals')
  const [loading, setLoading] = useState(true)

  async function loadData() {
    const [sigs, sigStats, rej] = await Promise.all([
      getSignals(50),
      getSignalStats(),
      getSignalRejections(20),
    ])

    if (sigs?.signals) setSignals(sigs.signals)
    if (sigStats) setStats(sigStats)
    if (rej?.rejections) setRejections(rej.rejections)
    setLoading(false)
  }

  useEffect(() => {
    loadData()
  }, [])

  const filteredSignals = signals.filter(s => {
    if (filter === 'all') return true
    if (filter === 'BUY') return s.action === 'BUY'
    if (filter === 'SELL') return s.action === 'SELL'
    if (filter === 'strong') return s.consensus === 'STRONG_CONSENSUS'
    return true
  })

  return (
    <div className="min-h-screen bg-arthai-dark">
      <NavBar />
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold text-white mb-6">
          Signal History
        </h1>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { label: 'Total', value: stats.total_signals, color: 'text-white' },
              { label: 'Avg Confidence', value: `${stats.avg_confidence?.toFixed(0)}%`, color: 'text-blue-400' },
              { label: 'Today', value: stats.today_signals, color: 'text-yellow-400' },
              { label: 'Strong', value: stats.strong_signals, color: 'text-emerald-400' },
            ].map((item) => (
              <div key={item.label} 
                   className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                <div className={`text-2xl font-bold ${item.color}`}>{item.value}</div>
                <div className="text-xs text-gray-500 mt-1">{item.label}</div>
              </div>
            ))}
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          {['signals', 'rejections'].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-medium capitalize
                         transition-colors
                         ${tab === t
                           ? 'bg-blue-600 text-white'
                           : 'bg-gray-900 text-gray-400 hover:text-white border border-gray-800'
                         }`}
            >
              {t} {t === 'signals' ? `(${signals.length})` : `(${rejections.length})`}
            </button>
          ))}
        </div>

        {tab === 'signals' && (
          <>
            {/* Filter */}
            <div className="flex gap-2 mb-4 flex-wrap">
              {['all', 'BUY', 'SELL', 'strong'].map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium
                             transition-colors
                             ${filter === f
                               ? 'bg-blue-600/30 text-blue-400 border border-blue-600'
                               : 'bg-gray-900 text-gray-400 border border-gray-800 hover:text-white'
                             }`}
                >
                  {f.toUpperCase()}
                </button>
              ))}
            </div>

            {loading ? (
              <div className="text-center py-20 text-gray-500">Loading signals...</div>
            ) : filteredSignals.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {filteredSignals.map((signal, idx) => (
                  <SignalCard key={signal.id || idx} signal={signal} />
                ))}
              </div>
            ) : (
              <div className="text-center py-20 text-gray-500">
                No signals found
              </div>
            )}
          </>
        )}

        {tab === 'rejections' && (
          <div className="space-y-3">
            {rejections.map((rej, idx) => (
              <div key={idx}
                   className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-bold text-white">{rej.symbol}</span>
                  <span className="text-xs text-gray-500">
                    {rej.created_at
                      ? new Date(rej.created_at).toLocaleString('en-IN')
                      : '--'}
                  </span>
                </div>
                <div className="text-xs text-red-400 mb-1">
                  Stage: {rej.stage} | Confidence: {rej.confidence?.toFixed(0)}%
                </div>
                <div className="text-xs text-gray-400">
                  {rej.rejection_reason}
                </div>
              </div>
            ))}
            {rejections.length === 0 && (
              <div className="text-center py-10 text-gray-500">
                No rejections recorded yet
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}