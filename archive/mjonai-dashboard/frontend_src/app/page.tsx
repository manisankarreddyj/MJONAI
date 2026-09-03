'use client'

import { useState, useEffect } from 'react'
import NavBar from '@/components/NavBar'
import StatCard from '@/components/StatCard'
import SignalCard from '@/components/SignalCard'
import {
  getSystemStatus,
  getSignalStats,
  getPortfolioSummary,
  getMarketMood,
  getTodaySignals,
  getTradeStats,
  getPsychologyState,
  getTodayLesson,
  getVixData,
} from '@/lib/api'

export default function Dashboard() {
  const [systemStatus, setSystemStatus] = useState<any>(null)
  const [signalStats, setSignalStats] = useState<any>(null)
  const [portfolio, setPortfolio] = useState<any>(null)
  const [marketMood, setMarketMood] = useState<any>(null)
  const [todaySignals, setTodaySignals] = useState<any[]>([])
  const [tradeStats, setTradeStats] = useState<any>(null)
  const [psychState, setPsychState] = useState<any>(null)
  const [lesson, setLesson] = useState<any>(null)
  const [vix, setVix] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date())

  async function loadData() {
    const [sys, sigStats, port, mood, sigs, trades, psych, les, vixData] =
      await Promise.all([
        getSystemStatus(),
        getSignalStats(),
        getPortfolioSummary(),
        getMarketMood(),
        getTodaySignals(),
        getTradeStats(),
        getPsychologyState(),
        getTodayLesson(),
        getVixData(),
      ])

    if (sys?.status) setSystemStatus(sys.status)
    if (sigStats) setSignalStats(sigStats)
    if (port?.summary) setPortfolio(port.summary)
    if (mood?.mood) setMarketMood(mood.mood)
    if (sigs?.signals) setTodaySignals(sigs.signals)
    if (trades?.stats) setTradeStats(trades.stats)
    if (psych?.state) setPsychState(psych.state)
    if (les?.lesson) setLesson(les.lesson)
    if (vixData?.vix !== undefined) setVix(vixData)
    
    setLastUpdate(new Date())
    setLoading(false)
  }

  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [])

  const moodColor = (mood: string) => {
    if (!mood) return 'text-gray-400'
    const m = mood.toUpperCase()
    if (m.includes('BULL') || m.includes('STRONG')) return 'text-emerald-400'
    if (m.includes('BEAR') || m.includes('PANIC')) return 'text-red-400'
    if (m.includes('CAUTION') || m.includes('VOLATILE')) return 'text-yellow-400'
    return 'text-blue-400'
  }

  const pnl = portfolio?.pnl?.total || 0
  const pnlPercent = portfolio?.pnl?.total_percent || 0

  if (loading) {
    return (
      <div className="min-h-screen bg-arthai-dark">
        <NavBar />
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent 
                          rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-400">Loading ArthAI Dashboard...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-arthai-dark">
      <NavBar />

      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">ArthAI Dashboard</h1>
            <p className="text-gray-400 text-sm mt-0.5">
              Finding meaning in market chaos
            </p>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-2 justify-end">
              <div className={`w-2 h-2 rounded-full animate-pulse 
                             ${systemStatus?.market_hours 
                               ? 'bg-emerald-400' 
                               : 'bg-gray-500'}`}
              />
              <span className="text-sm text-gray-400">
                {systemStatus?.market_hours ? 'Market Open' : 'Market Closed'}
              </span>
            </div>
            <p className="text-xs text-gray-600 mt-1">
              Updated {lastUpdate.toLocaleTimeString('en-IN')}
            </p>
          </div>
        </div>

        {/* Market Mood Banner */}
        {marketMood && (
          <div className="mb-6 bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div className="flex items-center gap-3">
                <span className="text-2xl">🌡️</span>
                <div>
                  <p className="text-xs text-gray-500">Market Mood</p>
                  <p className={`text-xl font-bold ${moodColor(marketMood.mood)}`}>
                    {marketMood.mood || 'NEUTRAL'}
                  </p>
                </div>
              </div>
              
              <div className="flex items-center gap-6 flex-wrap">
                <div className="text-center">
                  <p className="text-xs text-gray-500">Regime</p>
                  <p className="text-sm font-semibold text-white">
                    {marketMood.regime || '--'}
                  </p>
                </div>
                {vix?.vix && (
                  <div className="text-center">
                    <p className="text-xs text-gray-500">VIX</p>
                    <p className={`text-sm font-semibold 
                                 ${vix.vix > 25 ? 'text-red-400' :
                                   vix.vix > 15 ? 'text-yellow-400' :
                                   'text-emerald-400'}`}>
                      {vix.vix.toFixed(1)}
                    </p>
                  </div>
                )}
                <div className="text-center">
                  <p className="text-xs text-gray-500">Score</p>
                  <p className="text-sm font-semibold text-white">
                    {marketMood.score?.toFixed(1) || '--'}/10
                  </p>
                </div>
              </div>
              
              {marketMood.reason && (
                <p className="text-xs text-gray-400 w-full">
                  {marketMood.reason}
                </p>
              )}
            </div>
          </div>
        )}

        {/* Key Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard
            title="Total P&L"
            value={`Rs ${pnl >= 0 ? '+' : ''}${pnl.toFixed(0)}`}
            subtitle={`${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}% return`}
            color={pnl >= 0 ? 'green' : 'red'}
            trend={pnl >= 0 ? 'up' : 'down'}
            icon="💰"
          />
          <StatCard
            title="Win Rate"
            value={`${tradeStats?.win_rate?.toFixed(1) || '0'}%`}
            subtitle={`Target: 65% | ${tradeStats?.wins || 0}W / ${tradeStats?.losses || 0}L`}
            color={
              (tradeStats?.win_rate || 0) >= 65 ? 'green' :
              (tradeStats?.win_rate || 0) >= 50 ? 'yellow' : 'red'
            }
            icon="🎯"
          />
          <StatCard
            title="Signals Today"
            value={`${systemStatus?.signals_today || 0}/4`}
            subtitle={`${systemStatus?.remaining_signals || 4} remaining`}
            color="blue"
            icon="📡"
          />
          <StatCard
            title="Open Positions"
            value={systemStatus?.open_positions || 0}
            subtitle={`Rs ${portfolio?.capital?.deployed?.toFixed(0) || 0} deployed`}
            color="purple"
            icon="📂"
          />
        </div>

        {/* Capital Overview */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <p className="text-gray-400 text-sm mb-3">Capital Status</p>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">Initial</span>
                <span className="text-sm font-semibold text-white">
                  Rs {(portfolio?.capital?.initial || 100000).toLocaleString('en-IN')}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">Deployed</span>
                <span className="text-sm font-semibold text-yellow-400">
                  Rs {(portfolio?.capital?.deployed || 0).toLocaleString('en-IN')}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-500">Available</span>
                <span className="text-sm font-semibold text-emerald-400">
                  Rs {(portfolio?.capital?.available || 100000).toLocaleString('en-IN')}
                </span>
              </div>
              
              {/* Progress bar */}
              <div className="mt-2">
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-600 rounded-full transition-all"
                    style={{
                      width: `${Math.min(
                        100,
                        ((portfolio?.capital?.deployed || 0) /
                         (portfolio?.capital?.initial || 100000)) * 100
                      )}%`
                    }}
                  />
                </div>
                <p className="text-xs text-gray-600 mt-1">
                  {(((portfolio?.capital?.deployed || 0) /
                     (portfolio?.capital?.initial || 100000)) * 100).toFixed(1)}% deployed
                </p>
              </div>
            </div>
          </div>

          {/* Psychology State */}
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <p className="text-gray-400 text-sm mb-3">Psychology Guard</p>
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full 
                               ${psychState?.can_trade !== false
                                 ? 'bg-emerald-400'
                                 : 'bg-red-400'}`}
                />
                <span className="text-sm text-white">
                  {psychState?.can_trade !== false ? 'Can Trade' : 'Trading Blocked'}
                </span>
              </div>
              
              <div className="flex items-center gap-2">
                <div className={`w-3 h-3 rounded-full 
                               ${!psychState?.in_cooldown
                                 ? 'bg-emerald-400'
                                 : 'bg-yellow-400'}`}
                />
                <span className="text-sm text-white">
                  {psychState?.in_cooldown ? 'In Cooldown' : 'No Cooldown'}
                </span>
              </div>
              
              <div className="text-xs text-gray-500 space-y-1 mt-3 
                            bg-gray-800/50 rounded-lg p-3">
                <div className="flex justify-between">
                  <span>Signals today:</span>
                  <span className="text-white">{psychState?.signals_today || 0}/4</span>
                </div>
                <div className="flex justify-between">
                  <span>Losses today:</span>
                  <span className={
                    (psychState?.losses_today || 0) >= 2
                      ? 'text-red-400'
                      : 'text-white'
                  }>
                    {psychState?.losses_today || 0}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Today's Lesson */}
          {lesson && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <p className="text-gray-400 text-sm mb-2">Today's Lesson 📚</p>
              <p className="text-blue-400 font-semibold text-sm mb-2">
                {lesson.topic}
              </p>
              <p className="text-gray-400 text-xs leading-relaxed mb-3">
                {lesson.lesson_content?.slice(0, 150)}
                {lesson.lesson_content?.length > 150 ? '...' : ''}
              </p>
              {lesson.key_takeaway && (
                <div className="bg-yellow-900/20 border border-yellow-800/30 
                              rounded-lg p-2">
                  <p className="text-yellow-400 text-xs">
                    💡 {lesson.key_takeaway}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Today's Signals */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">
              Today's Signals
              <span className="ml-2 text-sm text-gray-500">
                ({todaySignals.length}/4 maximum)
              </span>
            </h2>
            <a
              href="/signals"
              className="text-sm text-blue-400 hover:text-blue-300 transition-colors"
            >
              View All →
            </a>
          </div>
          
          {todaySignals.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {todaySignals.slice(0, 4).map((signal, index) => (
                <SignalCard key={signal.id || index} signal={signal} />
              ))}
            </div>
          ) : (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
              <div className="text-4xl mb-3">🔍</div>
              <p className="text-gray-400 text-lg mb-2">No signals yet today</p>
              <p className="text-gray-600 text-sm">
                ArthAI scans every 15 minutes during market hours (9:15 AM - 3:15 PM)
              </p>
            </div>
          )}
        </div>

        {/* Signal Stats Bar */}
        {signalStats && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <p className="text-gray-400 text-sm mb-4">All-Time Signal Statistics</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <p className="text-2xl font-bold text-white">
                  {signalStats.total_signals || 0}
                </p>
                <p className="text-xs text-gray-500">Total Signals</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-emerald-400">
                  {signalStats.avg_confidence?.toFixed(0) || 0}%
                </p>
                <p className="text-xs text-gray-500">Avg Confidence</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-400">
                  {signalStats.strong_signals || 0}
                </p>
                <p className="text-xs text-gray-500">Strong Signals</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-yellow-400">
                  {signalStats.buy_signals || 0}/{signalStats.sell_signals || 0}
                </p>
                <p className="text-xs text-gray-500">Buy/Sell Split</p>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 text-center text-gray-700 text-xs">
          <p>ArthAI v1.0 | Paper Trading Mode | Capital Protected</p>
          <p className="mt-1">
            "When in doubt, stay out" | "Capital protection over profit always"
          </p>
        </div>
      </div>
    </div>
  )
}