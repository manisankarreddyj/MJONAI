'use client'

import { useState, useEffect, useCallback } from 'react'
import NavBar from '@/components/NavBar'
import { getOpenTrades, getClosedTrades, getTradeStats, closePaperTrade } from '@/lib/api'

export default function PaperTradingPage() {
  const [openTrades, setOpenTrades] = useState<any[]>([])
  const [closedTrades, setClosedTrades] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [tab, setTab] = useState('open')
  const [loading, setLoading] = useState(true)
  const [closingSymbol, setClosingSymbol] = useState<string | null>(null)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)

  const load = useCallback(async () => {
    const [open, closed, st] = await Promise.all([
      getOpenTrades(),
      getClosedTrades(30),
      getTradeStats(),
    ])
    if (open?.trades) setOpenTrades(open.trades)
    if (closed?.trades) setClosedTrades(closed.trades)
    if (st?.stats) setStats(st.stats)
    setLoading(false)
  }, [])

  useEffect(() => {
    load()
    const interval = setInterval(load, 15000)
    return () => clearInterval(interval)
  }, [load])

  // Toast auto-dismiss
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 4000)
      return () => clearTimeout(t)
    }
  }, [toast])

  const handleExitTrade = async (symbol: string) => {
    if (closingSymbol) return // prevent double-click
    setClosingSymbol(symbol)

    try {
      const result = await closePaperTrade(symbol, 'MANUAL_UI_EXIT')

      if (result?.success) {
        setToast({ message: `✅ ${symbol} position closed successfully`, type: 'success' })
        // Immediately refresh data
        await load()
      } else {
        setToast({ message: `❌ Failed: ${result?.message || 'Unknown error'}`, type: 'error' })
      }
    } catch (err) {
      setToast({ message: `❌ Network error closing ${symbol}`, type: 'error' })
    } finally {
      setClosingSymbol(null)
    }
  }

  const s = stats || {}

  return (
    <div className="min-h-screen bg-arthai-dark">
      <NavBar />
      <div className="max-w-7xl mx-auto px-4 py-6">

        {/* Toast Notification */}
        {toast && (
          <div className={`fixed top-4 right-4 z-50 px-5 py-3 rounded-xl shadow-2xl border text-sm font-medium
                          transition-all duration-300 animate-slide-in
                          ${toast.type === 'success'
                            ? 'bg-emerald-900/90 border-emerald-600 text-emerald-200'
                            : 'bg-red-900/90 border-red-600 text-red-200'}`}>
            {toast.message}
          </div>
        )}

        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-white">Paper Trading</h1>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
            <span className="text-xs text-gray-400">
              Live • Updates every 15s
            </span>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          {[
            { label: 'Open', value: s.open_trades || 0, color: 'text-blue-400' },
            { label: 'Wins', value: s.wins || 0, color: 'text-emerald-400' },
            { label: 'Losses', value: s.losses || 0, color: 'text-red-400' },
            {
              label: 'Win Rate',
              value: `${(s.win_rate || 0).toFixed(1)}%`,
              color: (s.win_rate || 0) >= 65 ? 'text-emerald-400' : 'text-yellow-400'
            },
            {
              label: 'Total P&L',
              value: `₹${(s.total_pnl || 0) >= 0 ? '+' : ''}${(s.total_pnl || 0).toFixed(0)}`,
              color: (s.total_pnl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'
            },
          ].map((item) => (
            <div key={item.label}
                 className="bg-gray-900/80 border border-gray-800 rounded-xl p-4 text-center
                            backdrop-blur-sm hover:border-gray-700 transition-colors">
              <div className={`text-xl font-bold ${item.color}`}>{item.value}</div>
              <div className="text-xs text-gray-500 mt-1">{item.label}</div>
            </div>
          ))}
        </div>

        {/* Real Money Readiness */}
        <div className={`rounded-xl p-4 mb-6 border
                       ${s.ready_for_real_money
                         ? 'bg-emerald-900/20 border-emerald-700'
                         : 'bg-gray-900 border-gray-800'}`}>
          <div className="flex items-center gap-3">
            <span className="text-2xl">
              {s.ready_for_real_money ? '🎉' : '🎯'}
            </span>
            <div>
              <p className={`font-semibold ${s.ready_for_real_money ? 'text-emerald-400' : 'text-white'}`}>
                {s.ready_for_real_money
                  ? 'Ready for Real Money! (But continue paper trading for safety)'
                  : 'Keep paper trading — Building toward 65% win rate'}
              </p>
              <p className="text-gray-400 text-xs mt-0.5">
                {s.closed_trades || 0} trades completed |
                Need: 20+ trades AND 65%+ win rate
              </p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          {[
            { id: 'open', label: `Open (${openTrades.length})` },
            { id: 'closed', label: `Closed (${closedTrades.length})` },
          ].map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200
                         ${tab === t.id
                           ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                           : 'bg-gray-900 border border-gray-800 text-gray-400 hover:text-white hover:border-gray-600'}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Trade Lists */}
        {loading ? (
          <div className="text-center py-20 text-gray-400">
            <div className="inline-block w-6 h-6 border-2 border-gray-600 border-t-blue-400 rounded-full animate-spin mb-3" />
            <p>Loading trades...</p>
          </div>
        ) : tab === 'open' ? (
          openTrades.length > 0 ? (
            <div className="space-y-3">
              {openTrades.map((trade, idx) => {
                const pnlVal = trade.unrealized_pnl || 0
                const isClosing = closingSymbol === trade.symbol
                return (
                  <div key={idx}
                       className="bg-gray-900 border border-gray-800 rounded-xl p-4
                                hover:border-blue-800 transition-all duration-200 group">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-3">
                        <span className="font-bold text-white text-lg">{trade.symbol}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-bold
                                       ${trade.action === 'BUY'
                                         ? 'bg-emerald-900/50 text-emerald-400'
                                         : 'bg-red-900/50 text-red-400'}`}>
                          {trade.action}
                        </span>
                        <span className="px-2 py-0.5 rounded text-xs
                                       bg-gray-800 text-gray-400">
                          Qty: {trade.quantity}
                        </span>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className={`font-bold text-lg ${pnlVal >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          ₹{pnlVal >= 0 ? '+' : ''}{pnlVal.toFixed(0)}
                        </div>
                        {/* ──── EXIT POSITION BUTTON ──── */}
                        <button
                          id={`exit-trade-${trade.symbol}`}
                          onClick={() => handleExitTrade(trade.symbol)}
                          disabled={isClosing}
                          className={`px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider
                                     transition-all duration-200 border
                                     ${isClosing
                                       ? 'bg-gray-800 border-gray-700 text-gray-500 cursor-wait'
                                       : 'bg-red-900/30 border-red-700/50 text-red-400 hover:bg-red-800/60 hover:border-red-500 hover:text-red-300 hover:shadow-lg hover:shadow-red-900/30 active:scale-95'}`}
                        >
                          {isClosing ? (
                            <span className="flex items-center gap-2">
                              <span className="inline-block w-3 h-3 border-2 border-gray-600 border-t-red-400 rounded-full animate-spin" />
                              Closing...
                            </span>
                          ) : (
                            '✕ Exit Position'
                          )}
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-4 gap-3 text-xs text-gray-400">
                      <div>
                        <p className="text-gray-500">Entry</p>
                        <p className="text-white font-medium">₹{(trade.entry_price || 0).toFixed(0)}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Stop Loss</p>
                        <p className="text-red-400 font-medium">₹{(trade.stop_loss || 0).toFixed(0)}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Target 1</p>
                        <p className="text-emerald-400 font-medium">₹{(trade.target_1 || 0).toFixed(0)}</p>
                      </div>
                      <div>
                        <p className="text-gray-500">Deployed</p>
                        <p className="text-white font-medium">₹{(trade.capital_deployed || 0).toFixed(0)}</p>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-16 text-gray-500">
              <div className="text-4xl mb-3">📄</div>
              <p>No open paper trades</p>
              <p className="text-sm mt-1">
                Trades open automatically when signals are approved
              </p>
            </div>
          )
        ) : (
          closedTrades.length > 0 ? (
            <div className="space-y-2">
              {closedTrades.map((trade, idx) => {
                const pnlVal = trade.realized_pnl || 0
                const isWin = trade.result === 'WIN'
                const isLoss = trade.result === 'LOSS'
                return (
                  <div key={idx}
                       className={`bg-gray-900 border rounded-xl p-4 transition-colors duration-200
                                  ${isWin ? 'border-emerald-900/50 hover:border-emerald-800' :
                                    isLoss ? 'border-red-900/50 hover:border-red-800' :
                                    'border-gray-800 hover:border-gray-700'}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="font-bold text-white">{trade.symbol}</span>
                        <span className={`px-2 py-0.5 rounded text-xs font-bold
                                       ${isWin ? 'bg-emerald-900/50 text-emerald-400' :
                                         isLoss ? 'bg-red-900/50 text-red-400' :
                                         'bg-gray-800 text-gray-400'}`}>
                          {trade.result || 'CLOSED'}
                        </span>
                        <span className="text-xs text-gray-500">
                          {trade.action} | Qty: {trade.quantity}
                        </span>
                        {trade.exit_reason === 'MANUAL_UI_EXIT' && (
                          <span className="px-2 py-0.5 rounded text-xs bg-yellow-900/40 text-yellow-400 border border-yellow-800/30">
                            Manual Exit
                          </span>
                        )}
                      </div>
                      <div className={`font-bold
                                     ${pnlVal >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        ₹{pnlVal >= 0 ? '+' : ''}{pnlVal.toFixed(0)}
                      </div>
                    </div>

                    <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                      <span>Entry: ₹{(trade.entry_price || 0).toFixed(0)}</span>
                      {trade.exit_price && (
                        <span>Exit: ₹{(trade.exit_price || 0).toFixed(0)}</span>
                      )}
                      {trade.exit_reason && (
                        <span className="text-gray-600">{trade.exit_reason}</span>
                      )}
                      {trade.closed_at && (
                        <span className="ml-auto">
                          {new Date(trade.closed_at).toLocaleDateString('en-IN')}
                        </span>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-16 text-gray-500">
              <div className="text-4xl mb-3">📊</div>
              <p>No closed trades yet</p>
              <p className="text-sm mt-1">Closed trades will appear here</p>
            </div>
          )
        )}
      </div>
    </div>
  )
}