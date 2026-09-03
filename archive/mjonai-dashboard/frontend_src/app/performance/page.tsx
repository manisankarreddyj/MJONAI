'use client'

import { useState, useEffect } from 'react'
import NavBar from '@/components/NavBar'
import { getPerformanceSummary, getDailyBreakdown, getPerformanceBySymbol } from '@/lib/api'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell
} from 'recharts'

export default function PerformancePage() {
  const [summary, setSummary] = useState<any>(null)
  const [daily, setDaily] = useState<any[]>([])
  const [bySymbol, setBySymbol] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      const [sum, dailyData, sym] = await Promise.all([
        getPerformanceSummary(),
        getDailyBreakdown(30),
        getPerformanceBySymbol(),
      ])
      if (sum?.summary) setSummary(sum.summary)
      if (dailyData?.daily) setDaily(dailyData.daily.reverse())
      if (sym?.by_symbol) setBySymbol(sym.by_symbol)
      setLoading(false)
    }
    load()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen bg-arthai-dark">
        <NavBar />
        <div className="flex items-center justify-center h-96">
          <div className="text-gray-400">Loading performance data...</div>
        </div>
      </div>
    )
  }

  const s = summary || {}

  return (
    <div className="min-h-screen bg-arthai-dark">
      <NavBar />
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold text-white mb-6">Performance Analytics</h1>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[
            {
              label: 'Total P&L',
              value: `Rs ${s.total_pnl >= 0 ? '+' : ''}${(s.total_pnl || 0).toFixed(0)}`,
              color: (s.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
            },
            {
              label: 'Win Rate',
              value: `${(s.win_rate || 0).toFixed(1)}%`,
              color: (s.win_rate || 0) >= 65 ? 'text-emerald-400' :
                     (s.win_rate || 0) >= 50 ? 'text-yellow-400' : 'text-red-400'
            },
            {
              label: 'Total Trades',
              value: s.total_trades || 0,
              color: 'text-blue-400'
            },
            {
              label: 'Max Drawdown',
              value: `Rs ${(s.max_drawdown || 0).toFixed(0)}`,
              color: 'text-red-400'
            },
          ].map((item) => (
            <div key={item.label}
                 className="bg-gray-900 border border-gray-800 rounded-xl p-5 text-center">
              <div className={`text-2xl font-bold ${item.color}`}>{item.value}</div>
              <div className="text-xs text-gray-500 mt-1">{item.label}</div>
            </div>
          ))}
        </div>

        {/* Target Progress */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm text-gray-400">Win Rate Progress (Target: 65%)</p>
            <span className={`text-sm font-bold 
                           ${s.target_reached ? 'text-emerald-400' : 'text-yellow-400'}`}>
              {s.target_reached ? '✅ Target Reached!' : '🎯 Keep Going'}
            </span>
          </div>
          <div className="h-3 bg-gray-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500
                         ${(s.win_rate || 0) >= 65
                           ? 'bg-emerald-500'
                           : (s.win_rate || 0) >= 50
                           ? 'bg-yellow-500'
                           : 'bg-red-500'}`}
              style={{ width: `${Math.min(100, s.win_rate || 0)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-600 mt-1">
            <span>0%</span>
            <span className="text-yellow-600">65% target</span>
            <span>100%</span>
          </div>
          {!s.target_reached && (
            <p className="text-xs text-gray-500 mt-2 text-center">
              {s.total_trades < 20
                ? `${20 - s.total_trades} more trades needed for statistical significance`
                : `${(65 - (s.win_rate || 0)).toFixed(1)}% more win rate needed for real money`}
            </p>
          )}
        </div>

        {/* Daily P&L Chart */}
        {daily.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
            <h2 className="text-base font-semibold text-white mb-4">Daily P&L</h2>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={daily} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#6b7280', fontSize: 11 }}
                  tickFormatter={(v) => v.slice(5)}
                />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#111827',
                    border: '1px solid #374151',
                    borderRadius: '8px',
                    color: '#f9fafb'
                  }}
                  formatter={(v: any) => [`Rs ${v.toFixed(0)}`, 'P&L']}
                />
                <Bar dataKey="pnl" radius={[4, 4, 0, 0]}>
                  {daily.map((entry, index) => (
                    <Cell
                      key={index}
                      fill={entry.pnl >= 0 ? '#10b981' : '#ef4444'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* By Symbol */}
        {bySymbol.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <h2 className="text-base font-semibold text-white mb-4">
              Performance by Stock
            </h2>
            <div className="space-y-3">
              {bySymbol.map((item) => (
                <div key={item.symbol}
                     className="flex items-center justify-between 
                              bg-gray-800/50 rounded-lg px-4 py-3">
                  <div className="flex items-center gap-4">
                    <span className="font-bold text-white w-24">{item.symbol}</span>
                    <span className="text-xs text-gray-500">
                      {item.trades} trades | {item.win_rate}% WR
                    </span>
                  </div>
                  <div className={`font-bold text-sm 
                                 ${item.total_pnl >= 0
                                   ? 'text-emerald-400'
                                   : 'text-red-400'}`}>
                    Rs {item.total_pnl >= 0 ? '+' : ''}{item.total_pnl.toFixed(0)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}