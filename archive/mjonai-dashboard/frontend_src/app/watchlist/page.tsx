'use client'

import { useState, useEffect } from 'react'
import NavBar from '@/components/NavBar'
import { getWatchlist, addToWatchlist, removeFromWatchlist } from '@/lib/api'

export default function WatchlistPage() {
  const [watchlist, setWatchlist] = useState<any[]>([])
  const [newSymbol, setNewSymbol] = useState('')
  const [newReason, setNewReason] = useState('')
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  async function load() {
    const data = await getWatchlist()
    if (data?.watchlist) setWatchlist(data.watchlist)
    setLoading(false)
  }

  useEffect(() => {
    load()
    const interval = setInterval(load, 60000)
    return () => clearInterval(interval)
  }, [])

  async function handleAdd() {
    if (!newSymbol.trim()) return
    setAdding(true)
    setMessage(null)

    const result = await addToWatchlist(newSymbol.trim().toUpperCase(), newReason.trim() || undefined)

    if (result?.success) {
      setMessage({ text: `${newSymbol.toUpperCase()} added to watchlist`, type: 'success' })
      setNewSymbol('')
      setNewReason('')
      await load()
    } else {
      setMessage({ text: result?.message || 'Failed to add symbol', type: 'error' })
    }
    setAdding(false)
  }

  async function handleRemove(symbol: string) {
    const result = await removeFromWatchlist(symbol)
    if (result?.success) {
      setMessage({ text: `${symbol} removed`, type: 'success' })
      await load()
    }
  }

  // Auto clear message after 3 seconds
  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [message])

  return (
    <div className="min-h-screen bg-arthai-dark">
      <NavBar />
      <div className="max-w-4xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold text-white mb-6">Watchlist</h1>

        {/* Add Symbol */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 mb-6">
          <h2 className="text-base font-semibold text-white mb-4">
            Add Stock to Watchlist
          </h2>

          <div className="flex flex-col md:flex-row gap-3">
            <input
              type="text"
              value={newSymbol}
              onChange={(e) => setNewSymbol(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              placeholder="Symbol (e.g. RELIANCE)"
              maxLength={20}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg
                       px-4 py-2.5 text-white text-sm placeholder-gray-500
                       focus:outline-none focus:border-blue-600 transition-colors"
            />
            <input
              type="text"
              value={newReason}
              onChange={(e) => setNewReason(e.target.value)}
              placeholder="Reason (optional)"
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg
                       px-4 py-2.5 text-white text-sm placeholder-gray-500
                       focus:outline-none focus:border-blue-600 transition-colors"
            />
            <button
              onClick={handleAdd}
              disabled={adding || !newSymbol.trim()}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm
                       font-medium hover:bg-blue-700 disabled:opacity-50
                       disabled:cursor-not-allowed transition-colors"
            >
              {adding ? 'Adding...' : 'Add'}
            </button>
          </div>

          {/* Message */}
          {message && (
            <div className={`mt-3 px-4 py-2 rounded-lg text-sm
                           ${message.type === 'success'
                             ? 'bg-emerald-900/30 text-emerald-400 border border-emerald-800'
                             : 'bg-red-900/30 text-red-400 border border-red-800'}`}>
              {message.text}
            </div>
          )}

          {/* Common NSE stocks hint */}
          <div className="mt-3 flex flex-wrap gap-2">
            <span className="text-xs text-gray-600">Quick add:</span>
            {['RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'WIPRO'].map((sym) => (
              <button
                key={sym}
                onClick={() => setNewSymbol(sym)}
                className="text-xs px-2 py-1 bg-gray-800 text-gray-400
                         rounded hover:text-white hover:bg-gray-700
                         transition-colors border border-gray-700"
              >
                {sym}
              </button>
            ))}
          </div>
        </div>

        {/* Watchlist */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-white">
              Watching ({watchlist.length} stocks)
            </h2>
            <span className="text-xs text-gray-500">
              ArthAI scans these every 15 min
            </span>
          </div>

          {loading ? (
            <div className="text-center py-10 text-gray-500">
              Loading watchlist...
            </div>
          ) : watchlist.length > 0 ? (
            <div className="space-y-2">
              {watchlist.map((item, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between
                           bg-gray-800/50 border border-gray-700
                           rounded-xl px-4 py-3
                           hover:border-gray-600 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    {/* Symbol */}
                    <span className="font-bold text-white w-28">
                      {item.symbol}
                    </span>

                    {/* Reason */}
                    <span className="text-sm text-gray-400">
                      {item.reason || 'No reason given'}
                    </span>
                  </div>

                  <div className="flex items-center gap-3">
                    {/* Added date */}
                    <span className="text-xs text-gray-600">
                      {item.added_at
                        ? new Date(item.added_at).toLocaleDateString('en-IN', {
                            day: 'numeric',
                            month: 'short'
                          })
                        : '--'}
                    </span>

                    {/* Status badge */}
                    <span className="px-2 py-0.5 rounded text-xs
                                   bg-emerald-900/30 text-emerald-400
                                   border border-emerald-800/50">
                      {item.status || 'active'}
                    </span>

                    {/* Remove button */}
                    <button
                      onClick={() => handleRemove(item.symbol)}
                      className="text-xs px-3 py-1 bg-red-900/30 text-red-400
                               border border-red-800/50 rounded-lg
                               hover:bg-red-900/50 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-16">
              <div className="text-4xl mb-3">👁️</div>
              <p className="text-gray-400 text-lg mb-2">Watchlist is empty</p>
              <p className="text-gray-600 text-sm">
                Add stocks above to monitor them for signals
              </p>
            </div>
          )}
        </div>

        {/* Info box */}
        <div className="mt-4 bg-blue-900/10 border border-blue-900/30
                      rounded-xl p-4">
          <p className="text-blue-400 text-sm font-medium mb-1">
            How Watchlist Works
          </p>
          <p className="text-gray-400 text-xs leading-relaxed">
            ArthAI already scans all Nifty 50 stocks every 15 minutes.
            Your watchlist stocks get priority alerts when signals are generated.
            Signals still go through the full 4-agent AI debate before reaching you.
          </p>
        </div>
      </div>
    </div>
  )
}