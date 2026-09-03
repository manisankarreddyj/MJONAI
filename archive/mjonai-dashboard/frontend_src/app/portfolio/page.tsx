'use client'

import { useState, useEffect } from 'react'
import NavBar from '@/components/NavBar'
import { getPortfolioSummary, getOpenPositions } from '@/lib/api'

export default function PortfolioPage() {
  const [summary, setSummary] = useState<any>(null)
  const [positions, setPositions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const [sum, pos] = await Promise.all([
        getPortfolioSummary(),
        getOpenPositions(),
      ])
      if (sum?.summary) setSummary(sum.summary)
      if (pos?.positions) setPositions(pos.positions)
      setLoading(false)
    }
    load()
    const interval = setInterval(load, 30000)
    return () => clearInterval(interval)
  }, [])

  const capital = summary?.capital || {}
  const pnl = summary?.pnl || {}
  const trades = summary?.trades || {}

  const deployedPct = capital.initial
    ? ((capital.deployed || 0) / capital.initial) * 100
    : 0

  return (
    <div className="min-h-screen bg-arthai-dark">
      <NavBar />
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-white">Portfolio</h1>
          <span className="px-3 py-1.5 bg-blue-900/40 text-blue-400
                         border border-blue-800 rounded-full text-xs font-semibold">
            PAPER TRADING
          </span>
        </div>

        {loading ? (
          <div className="text-center py-20 text-gray-400">Loading portfolio...</div>
        ) : (
          <>
            {/* Capital Overview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              {[
                {
                  label: 'Initial Capital',
                  value: `Rs ${(capital.initial || 100000).toLocaleString('en-IN')}`,
                  color: 'text-white',
                  sub: 'Starting amount'
                },
                {
                  label: 'Available Capital',
                  value: `Rs ${(capital.available || 100000).toLocaleString('en-IN')}`,
                  color: 'text-emerald-400',
                  sub: 'Ready to deploy'
                },
                {
                  label: 'Deployed Capital',
                  value: `Rs ${(capital.deployed || 0).toLocaleString('en-IN')}`,
                  color: 'text-yellow-400',
                  sub: `${deployedPct.toFixed(1)}% of total`
                },
              ].map((item) => (
                <div key={item.label}
                     className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                  <p className="text-gray-400 text-sm mb-2">{item.label}</p>
                  <p className={`text-2xl font-bold ${item.color}`}>{item.value}</p>
                  <p className="text-gray-500 text-xs mt-1">{item.sub}</p>
                </div>
              ))}
            </div>

            {/* Deployment Bar */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
              <div className="flex justify-between items-center mb-2">
                <p className="text-sm text-gray-400">Capital Deployment</p>
                <p className="text-sm font-semibold text-white">
                  {deployedPct.toFixed(1)}% deployed
                </p>
              </div>
              <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, deployedPct)}%` }}
                />
              </div>
              <p className="text-xs text-gray-600 mt-2">
                Rule: Never risk more than 2% per trade
              </p>
            </div>

            {/* P&L Summary */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {[
                {
                  label: 'Total P&L',
                  value: `Rs ${(pnl.total || 0) >= 0 ? '+' : ''}${(pnl.total || 0).toFixed(0)}`,
                  color: (pnl.total || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                },
                {
                  label: 'P&L %',
                  value: `${(pnl.total_percent || 0) >= 0 ? '+' : ''}${(pnl.total_percent || 0).toFixed(2)}%`,
                  color: (pnl.total_percent || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                },
                {
                  label: 'Today P&L',
                  value: `Rs ${(pnl.today || 0) >= 0 ? '+' : ''}${(pnl.today || 0).toFixed(0)}`,
                  color: (pnl.today || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
                },
                {
                  label: 'Unrealized',
                  value: `Rs ${(pnl.unrealized || 0) >= 0 ? '+' : ''}${(pnl.unrealized || 0).toFixed(0)}`,
                  color: (pnl.unrealized || 0) >= 0 ? 'text-blue-400' : 'text-red-400'
                },
              ].map((item) => (
                <div key={item.label}
                     className="bg-gray-900 border border-gray-800 rounded-xl p-4 text-center">
                  <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
                  <div className="text-xs text-gray-500 mt-1">{item.label}</div>
                </div>
              ))}
            </div>

            {/* Trade Statistics */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
              <h2 className="text-base font-semibold text-white mb-4">Trade Statistics</h2>
              <div className="grid grid-cols-3 md:grid-cols-6 gap-4">
                {[
                  { label: 'Open', value: trades.open || 0, color: 'text-blue-400' },
                  { label: 'Total', value: trades.total || 0, color: 'text-white' },
                  { label: 'Wins', value: trades.wins || 0, color: 'text-emerald-400' },
                  { label: 'Losses', value: trades.losses || 0, color: 'text-red-400' },
                  {
                    label: 'Win Rate',
                    value: `${(trades.win_rate || 0).toFixed(1)}%`,
                    color: (trades.win_rate || 0) >= 65 ? 'text-emerald-400' : 'text-yellow-400'
                  },
                  {
                    label: 'Target',
                    value: '65%',
                    color: (trades.win_rate || 0) >= 65 ? 'text-emerald-400' : 'text-gray-500'
                  },
                ].map((item) => (
                  <div key={item.label} className="text-center">
                    <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
                    <div className="text-xs text-gray-500 mt-1">{item.label}</div>
                  </div>
                ))}
              </div>

              {/* Win rate progress */}
              <div className="mt-4">
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-500
                               ${(trades.win_rate || 0) >= 65
                                 ? 'bg-emerald-500'
                                 : 'bg-yellow-500'}`}
                    style={{ width: `${Math.min(100, trades.win_rate || 0)}%` }}
                  />
                </div>
                <p className="text-xs text-gray-600 mt-1.5 text-center">
                  {(trades.win_rate || 0) >= 65
                    ? '✅ Win rate target met! Ready for real money evaluation.'
                    : `Need ${(65 - (trades.win_rate || 0)).toFixed(1)}% more win rate to qualify for real money`}
                </p>
              </div>
            </div>

            {/* Open Positions */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="text-base font-semibold text-white mb-4">
                Open Positions ({positions.length})
              </h2>

              {positions.length > 0 ? (
                <div className="space-y-3">
                  {positions.map((pos, idx) => {
                    const pnlVal = pos.unrealized_pnl || 0
                    const pnlColor = pnlVal >= 0 ? 'text-emerald-400' : 'text-red-400'
                    return (
                      <div key={idx}
                           className="bg-gray-800/50 border border-gray-700
                                    rounded-xl p-4 hover:border-gray-600
                                    transition-colors">
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <span className="font-bold text-white text-lg">
                              {pos.symbol}
                            </span>
                            <span className={`px-2 py-0.5 rounded text-xs font-bold
                                           ${pos.action === 'BUY'
                                             ? 'bg-emerald-900/50 text-emerald-400'
                                             : 'bg-red-900/50 text-red-400'}`}>
                              {pos.action}
                            </span>
                            <span className="text-xs text-gray-500">
                              Qty: {pos.quantity}
                            </span>
                          </div>
                          <div className={`text-lg font-bold ${pnlColor}`}>
                            Rs {pnlVal >= 0 ? '+' : ''}{pnlVal.toFixed(0)}
                          </div>
                        </div>

                        <div className="grid grid-cols-4 gap-3 text-xs">
                          <div>
                            <p className="text-gray-500">Entry</p>
                            <p className="text-white font-semibold">
                              Rs {(pos.entry_price || 0).toFixed(0)}
                            </p>
                          </div>
                          <div>
                            <p className="text-gray-500">Current</p>
                            <p className="text-white font-semibold">
                              Rs {(pos.current_price || pos.entry_price || 0).toFixed(0)}
                            </p>
                          </div>
                          <div>
                            <p className="text-gray-500">Stop Loss</p>
                            <p className="text-red-400 font-semibold">
                              Rs {(pos.stop_loss || 0).toFixed(0)}
                            </p>
                          </div>
                          <div>
                            <p className="text-gray-500">Target</p>
                            <p className="text-emerald-400 font-semibold">
                              Rs {(pos.target_1 || 0).toFixed(0)}
                            </p>
                          </div>
                        </div>

                        <div className="mt-2 flex items-center justify-between text-xs text-gray-500">
                          <span>
                            Deployed: Rs {(pos.capital_deployed || 0).toLocaleString('en-IN')}
                          </span>
                          <span>
                            Opened: {pos.opened_at
                              ? new Date(pos.opened_at).toLocaleString('en-IN', {
                                  month: 'short', day: 'numeric',
                                  hour: '2-digit', minute: '2-digit'
                                })
                              : '--'}
                          </span>
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="text-center py-10">
                  <div className="text-4xl mb-3">📂</div>
                  <p className="text-gray-400">No open positions</p>
                  <p className="text-gray-600 text-sm mt-1">
                    Positions open when signals are approved during market hours
                  </p>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}