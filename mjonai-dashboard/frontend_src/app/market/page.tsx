'use client'

import { useState, useEffect } from 'react'
import NavBar from '@/components/NavBar'
import { getMarketMood, getMoodHistory, getVixData, getGlobalMarkets, getMarketRegime } from '@/lib/api'

// Add to api.ts
// export const getMarketRegime = () => fetchAPI('/api/market-mood/regime')

export default function MarketPage() {
  const [mood, setMood] = useState<any>(null)
  const [history, setHistory] = useState<any[]>([])
  const [vix, setVix] = useState<any>(null)
  const [global, setGlobal] = useState<any>(null)
  const [regime, setRegime] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const [m, h, v, g, r] = await Promise.all([
        getMarketMood(),
        getMoodHistory(7),
        getVixData(),
        getGlobalMarkets(),
        fetch('http://localhost:8000/api/market-mood/regime', {
          headers: { 'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '' }
        }).then(r => r.json()).catch(() => null),
      ])

      if (m?.mood) setMood(m.mood)
      if (h?.history) setHistory(h.history)
      if (v) setVix(v)
      if (g?.markets) setGlobal(g.markets)
      if (r?.regime) setRegime(r.regime)
      setLoading(false)
    }
    load()
    const interval = setInterval(load, 60000)
    return () => clearInterval(interval)
  }, [])

  const moodColor = (m: string) => {
    if (!m) return 'text-gray-400'
    const upper = m.toUpperCase()
    if (upper.includes('BULL') || upper.includes('STRONG')) return 'text-emerald-400'
    if (upper.includes('BEAR') || upper.includes('PANIC')) return 'text-red-400'
    if (upper.includes('CAUTION') || upper.includes('VOLATILE')) return 'text-yellow-400'
    return 'text-blue-400'
  }

  const vixLevel = vix?.vix || 0

  return (
    <div className="min-h-screen bg-arthai-dark">
      <NavBar />
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold text-white mb-6">Market Intelligence</h1>

        {loading ? (
          <div className="text-center py-20 text-gray-400">
            Loading market data...
          </div>
        ) : (
          <>
            {/* Main Mood Card */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 mb-6">
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                <div className="text-center">
                  <p className="text-gray-400 text-sm mb-2">Market Mood</p>
                  <p className={`text-3xl font-bold ${moodColor(mood?.mood)}`}>
                    {mood?.mood || 'NEUTRAL'}
                  </p>
                  <p className="text-gray-500 text-xs mt-1">
                    Score: {mood?.score?.toFixed(1) || '--'}/10
                  </p>
                </div>

                <div className="text-center">
                  <p className="text-gray-400 text-sm mb-2">Market Regime</p>
                  <p className="text-2xl font-bold text-blue-400">
                    {regime?.current || mood?.regime || 'UNKNOWN'}
                  </p>
                  <p className="text-gray-500 text-xs mt-1">Current phase</p>
                </div>

                <div className="text-center">
                  <p className="text-gray-400 text-sm mb-2">India VIX</p>
                  <p className={`text-3xl font-bold
                               ${vixLevel > 25 ? 'text-red-400' :
                                 vixLevel > 20 ? 'text-yellow-400' :
                                 vixLevel > 15 ? 'text-blue-400' :
                                 'text-emerald-400'}`}>
                    {vixLevel > 0 ? vixLevel.toFixed(1) : '--'}
                  </p>
                  <p className="text-gray-500 text-xs mt-1">
                    {vix?.interpretation?.split(' - ')[0] || 'Fear gauge'}
                  </p>
                </div>

                <div className="text-center">
                  <p className="text-gray-400 text-sm mb-2">Signal Today</p>
                  <p className="text-2xl font-bold text-purple-400">
                    {mood?.mood?.includes('BULL') ? 'BULLISH BIAS' :
                     mood?.mood?.includes('BEAR') ? 'BEARISH BIAS' :
                     'NEUTRAL'}
                  </p>
                  <p className="text-gray-500 text-xs mt-1">Trading direction</p>
                </div>
              </div>

              {mood?.reason && (
                <div className="mt-4 pt-4 border-t border-gray-800">
                  <p className="text-gray-400 text-sm">{mood.reason}</p>
                </div>
              )}
            </div>

            {/* VIX Gauge */}
            {vixLevel > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
                <h2 className="text-base font-semibold text-white mb-4">
                  VIX Fear & Greed Gauge
                </h2>
                <div className="relative h-4 bg-gray-800 rounded-full overflow-hidden mb-2">
                  {/* Color zones */}
                  <div className="absolute inset-0 flex">
                    <div className="flex-1 bg-emerald-900/40" />
                    <div className="flex-1 bg-blue-900/40" />
                    <div className="flex-1 bg-yellow-900/40" />
                    <div className="flex-1 bg-red-900/40" />
                  </div>
                  {/* VIX pointer */}
                  <div
                    className="absolute top-0 h-full w-1 bg-white rounded-full"
                    style={{
                      left: `${Math.min(95, (vixLevel / 40) * 100)}%`
                    }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-600">
                  <span>Low Fear (8)</span>
                  <span>Normal (15)</span>
                  <span>High Fear (25)</span>
                  <span>Extreme (40+)</span>
                </div>
                <p className="text-sm text-gray-400 mt-3">
                  {vix?.interpretation || 'VIX interpretation loading...'}
                </p>
              </div>
            )}

            {/* Mood History */}
            {history.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
                <h2 className="text-base font-semibold text-white mb-4">
                  7-Day Mood History
                </h2>
                <div className="space-y-2">
                  {history.slice(0, 7).map((item, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between
                               bg-gray-800/50 rounded-lg px-4 py-2.5"
                    >
                      <div className="flex items-center gap-4">
                        <span className="text-xs text-gray-500 w-20">
                          {item.date || item.created_at?.slice(0, 10) || '--'}
                        </span>
                        <span className={`text-sm font-semibold ${moodColor(item.mood)}`}>
                          {item.mood || 'NEUTRAL'}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs text-gray-500">
                        {item.vix && <span>VIX: {Number(item.vix).toFixed(1)}</span>}
                        {item.score !== undefined && (
                          <span>Score: {Number(item.score).toFixed(1)}</span>
                        )}
                        <span>{item.regime || '--'}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Global Markets */}
            {global && Object.keys(global).length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <h2 className="text-base font-semibold text-white mb-4">
                  Global Markets
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {Object.entries(global).map(([key, val]: [string, any]) => {
                    if (typeof val !== 'object' || !val) return null
                    const change = val.change_pct || val.change || 0
                    return (
                      <div
                        key={key}
                        className="bg-gray-800/50 rounded-lg px-4 py-3 text-center"
                      >
                        <p className="text-xs text-gray-500 mb-1 capitalize">
                          {key.replace(/_/g, ' ')}
                        </p>
                        <p className="text-sm font-bold text-white">
                          {val.price || val.value || '--'}
                        </p>
                        <p className={`text-xs font-semibold mt-0.5
                                     ${Number(change) >= 0
                                       ? 'text-emerald-400'
                                       : 'text-red-400'}`}>
                          {Number(change) >= 0 ? '+' : ''}{Number(change).toFixed(2)}%
                        </p>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* No global data fallback */}
            {(!global || Object.keys(global || {}).length === 0) && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                <h2 className="text-base font-semibold text-white mb-3">
                  Global Markets
                </h2>
                <p className="text-gray-500 text-sm text-center py-4">
                  Global market data refreshes every 30 minutes.
                  Check back during market hours.
                </p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}