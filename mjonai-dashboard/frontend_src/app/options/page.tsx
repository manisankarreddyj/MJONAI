'use client'

import { useState, useEffect, useCallback } from 'react'
import NavBar from '@/components/NavBar'

// ─────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────

interface Greeks {
  delta: number
  gamma: number
  theta: number
  vega : number
}

interface OptionSide extends Greeks {
  oi        : number
  oi_change : number
  volume    : number
  iv        : number
  ltp       : number
  oi_buildup: 'BUILDUP' | 'UNWIND' | 'UNCHANGED' | 'UNKNOWN'
}

interface Strike {
  strike    : number
  moneyness : 'ITM' | 'ATM' | 'NEAR_ATM' | 'OTM'
  ce        : OptionSide
  pe        : OptionSide
  pcr_strike: number
}

interface ChainSummary {
  pcr               : number
  pcr_signal        : string
  max_pain          : number
  total_call_oi     : number
  total_put_oi      : number
  total_call_vol    : number
  total_put_vol     : number
  call_wall         : number
  put_wall          : number
  iv_rank           : number
  iv_percentile     : number
  expected_move     : number
  expected_move_up  : number
  expected_move_down: number
}

interface Alert {
  type   : string
  level  : 'BULLISH' | 'BEARISH' | 'WARNING' | 'INFO'
  message: string
}

interface ChainData {
  symbol           : string
  underlying_price : number
  atm_strike       : number
  atm_iv           : number
  expiry_dates     : string[]
  selected_expiry  : string
  dte              : number
  strikes          : Strike[]
  summary          : ChainSummary
  iv_rank          : number
  iv_percentile    : number
  iv_environment   : string
  iv_strategy_hint : string
  expected_move    : number
  expected_move_pct: number
  alerts           : Alert[]
  source           : string
  timestamp        : string
}

// ─────────────────────────────────────────────────────────────────
// Config
// ─────────────────────────────────────────────────────────────────

const API_BASE = 'http://localhost:8000/api/v1/options'
const API_KEY  = process.env.NEXT_PUBLIC_API_KEY || 'arthai-local-key'
const SYMBOLS  = ['NIFTY', 'BANKNIFTY', 'FINNIFTY', 'MIDCPNIFTY']
const HEADERS  = { 'Content-Type': 'application/json', 'X-API-Key': API_KEY }

// ─────────────────────────────────────────────────────────────────
// Formatters
// ─────────────────────────────────────────────────────────────────

const fmt = {
  num  : (n: number) => (n ?? 0).toLocaleString('en-IN'),
  oi   : (n: number) =>
    n >= 1_000_000 ? `${(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000   ? `${(n / 1_000).toFixed(0)}K`
    : String(n ?? 0),
  pct  : (n: number) => `${(n ?? 0).toFixed(1)}%`,
  dec2 : (n: number) => (n ?? 0).toFixed(2),
  dec4 : (n: number) => (n ?? 0).toFixed(4),
  price: (n: number) =>
    (n ?? 0).toLocaleString('en-IN', { minimumFractionDigits: 2 }),
}

// ─────────────────────────────────────────────────────────────────
// Small reusable components
// ─────────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  color = 'text-white',
}: {
  label : string
  value : string
  sub?  : string
  color?: string
}) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-3 min-w-[130px]">
      <p className="text-gray-500 text-xs uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-lg font-bold ${color}`}>{value}</p>
      {sub && <p className="text-gray-600 text-xs mt-0.5">{sub}</p>}
    </div>
  )
}

function IVRankBar({ rank }: { rank: number }) {
  const color =
    rank >= 70 ? 'bg-red-500'    :
    rank >= 40 ? 'bg-yellow-500' :
    'bg-green-500'

  const label =
    rank >= 70 ? 'HIGH — Sell Premium'  :
    rank >= 40 ? 'NORMAL — Balanced'    :
    rank > 0   ? 'LOW — Buy Premium'    :
    'Calculating...'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-3 min-w-[160px]">
      <div className="flex justify-between items-center mb-1.5">
        <span className="text-gray-500 text-xs uppercase tracking-wide">IV Rank</span>
        <span className="text-white font-bold">{fmt.pct(rank)}</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-1.5 mb-1">
        <div
          className={`h-1.5 rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${Math.min(Math.max(rank, 0), 100)}%` }}
        />
      </div>
      <p className="text-gray-500 text-xs">{label}</p>
    </div>
  )
}

function PCRBadge({ pcr, signal }: { pcr: number; signal: string }) {
  const color =
    signal.includes('BULL') ? 'text-green-400' :
    signal.includes('BEAR') ? 'text-red-400'   :
    'text-yellow-400'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-3 min-w-[110px]">
      <p className="text-gray-500 text-xs uppercase tracking-wide mb-1">PCR</p>
      <p className={`text-lg font-bold ${color}`}>{fmt.dec2(pcr)}</p>
      <p className={`text-xs mt-0.5 ${color}`}>{signal.replace(/_/g, ' ')}</p>
    </div>
  )
}

function AlertBanner({ alert }: { alert: Alert }) {
  const styles: Record<string, string> = {
    BULLISH: 'bg-green-900/30 border-green-700/50 text-green-300',
    BEARISH: 'bg-red-900/30 border-red-700/50 text-red-300',
    WARNING: 'bg-yellow-900/30 border-yellow-700/50 text-yellow-300',
    INFO   : 'bg-blue-900/30 border-blue-700/50 text-blue-300',
  }
  const icons: Record<string, string> = {
    BULLISH: '▲', BEARISH: '▼', WARNING: '⚠', INFO: 'ℹ',
  }
  return (
    <div className={`border rounded-lg px-3 py-2 text-sm flex gap-2 items-start
                     ${styles[alert.level] ?? styles.INFO}`}>
      <span className="shrink-0 font-bold mt-0.5">{icons[alert.level] ?? 'ℹ'}</span>
      <span>{alert.message}</span>
    </div>
  )
}

function OIBuildup({ value }: { value: string }) {
  if (value === 'BUILDUP')   return <span className="text-green-400 text-xs font-medium">▲ Build</span>
  if (value === 'UNWIND')    return <span className="text-red-400 text-xs font-medium">▼ Unwind</span>
  if (value === 'UNCHANGED') return <span className="text-gray-600 text-xs">—</span>
  return <span className="text-gray-700 text-xs">?</span>
}

function OIBar({ oi, maxOI, color = 'bg-blue-500' }: {
  oi   : number
  maxOI: number
  color?: string
}) {
  const pct = maxOI > 0 ? Math.min((oi / maxOI) * 100, 100) : 0
  return (
    <div className="w-full bg-gray-800 rounded-full h-1.5">
      <div
        className={`h-1.5 rounded-full transition-all duration-300 ${color}`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────
// Strike row
// ─────────────────────────────────────────────────────────────────

function StrikeRow({
  row,
  maxCallOI,
  maxPutOI,
  maxPain,
  underlyingPrice,
  showGreeks,
}: {
  row            : Strike
  maxCallOI      : number
  maxPutOI       : number
  maxPain        : number
  underlyingPrice: number
  showGreeks     : boolean
}) {
  const isATM     = row.moneyness === 'ATM' || row.moneyness === 'NEAR_ATM'
  const isMaxPain = row.strike === maxPain

  // For calls: ITM when strike < underlying
  // For puts : ITM when strike > underlying
  const ceITM = row.strike < underlyingPrice
  const peITM = row.strike > underlyingPrice

  const rowBg =
    isATM     ? 'bg-yellow-900/10 border-yellow-800/30' :
    isMaxPain ? 'bg-purple-900/10 border-purple-800/30' :
    'border-gray-800/50'

  const ceTxt = ceITM ? 'text-green-300' : 'text-gray-400'
  const peTxt = peITM ? 'text-green-300' : 'text-gray-400'

  return (
    <tr className={`border-b ${rowBg} hover:bg-gray-800/40 transition-colors`}>

      {/* ── CE side (left, reading right-to-left toward strike) ── */}
      <td className={`px-2 py-1.5 text-right ${ceTxt}`}>
        <OIBuildup value={row.ce.oi_buildup} />
      </td>
      <td className={`px-2 py-1.5 text-right text-xs ${ceTxt}`}>
        {fmt.oi(row.ce.oi_change)}
      </td>
      <td className={`px-2 py-1.5 text-right text-xs ${ceTxt}`}>
        {fmt.oi(row.ce.volume)}
      </td>
      <td className="px-2 py-1.5 text-right min-w-[90px]">
        <div className="flex flex-col gap-0.5 items-end">
          <span className={`text-xs font-medium ${ceTxt}`}>
            {fmt.oi(row.ce.oi)}
          </span>
          <OIBar oi={row.ce.oi} maxOI={maxCallOI} color="bg-red-500" />
        </div>
      </td>
      <td className={`px-2 py-1.5 text-right text-xs ${ceTxt}`}>
        {fmt.pct(row.ce.iv)}
      </td>
      {showGreeks && (
        <>
          <td className={`px-2 py-1.5 text-right text-xs ${ceTxt}`}>
            {fmt.dec2(row.ce.delta)}
          </td>
          <td className={`px-2 py-1.5 text-right text-xs ${ceTxt}`}>
            {fmt.dec4(row.ce.gamma)}
          </td>
          <td className={`px-2 py-1.5 text-right text-xs ${ceTxt}`}>
            {fmt.dec2(row.ce.theta)}
          </td>
        </>
      )}
      <td className={`px-2 py-1.5 text-right text-xs font-medium border-r border-gray-700 ${ceTxt}`}>
        {fmt.price(row.ce.ltp)}
      </td>

      {/* ── Strike center ── */}
      <td className="px-3 py-1.5 text-center border-r border-gray-700 bg-gray-900/60">
        <div className="flex flex-col items-center gap-0.5">
          <span className={`text-sm font-bold ${
            isATM     ? 'text-yellow-400' :
            isMaxPain ? 'text-purple-400' :
            'text-white'
          }`}>
            {fmt.num(row.strike)}
          </span>
          {isATM && (
            <span className="text-yellow-500 text-[9px] font-semibold tracking-wide">
              ATM
            </span>
          )}
          {isMaxPain && !isATM && (
            <span className="text-purple-400 text-[9px] font-semibold tracking-wide">
              MAX PAIN
            </span>
          )}
        </div>
      </td>

      {/* ── PE side (right) ── */}
      <td className={`px-2 py-1.5 text-left text-xs font-medium ${peTxt}`}>
        {fmt.price(row.pe.ltp)}
      </td>
      {showGreeks && (
        <>
          <td className={`px-2 py-1.5 text-left text-xs ${peTxt}`}>
            {fmt.dec2(row.pe.delta)}
          </td>
          <td className={`px-2 py-1.5 text-left text-xs ${peTxt}`}>
            {fmt.dec4(row.pe.gamma)}
          </td>
          <td className={`px-2 py-1.5 text-left text-xs ${peTxt}`}>
            {fmt.dec2(row.pe.theta)}
          </td>
        </>
      )}
      <td className={`px-2 py-1.5 text-left text-xs ${peTxt}`}>
        {fmt.pct(row.pe.iv)}
      </td>
      <td className="px-2 py-1.5 text-left min-w-[90px]">
        <div className="flex flex-col gap-0.5">
          <span className={`text-xs font-medium ${peTxt}`}>
            {fmt.oi(row.pe.oi)}
          </span>
          <OIBar oi={row.pe.oi} maxOI={maxPutOI} color="bg-green-500" />
        </div>
      </td>
      <td className={`px-2 py-1.5 text-left text-xs ${peTxt}`}>
        {fmt.oi(row.pe.volume)}
      </td>
      <td className={`px-2 py-1.5 text-left text-xs ${peTxt}`}>
        {fmt.oi(row.pe.oi_change)}
      </td>
      <td className={`px-2 py-1.5 text-left ${peTxt}`}>
        <OIBuildup value={row.pe.oi_buildup} />
      </td>
    </tr>
  )
}

// ─────────────────────────────────────────────────────────────────
// Main page
// ─────────────────────────────────────────────────────────────────

export default function OptionsPage() {
  const [symbol,      setSymbol]      = useState('NIFTY')
  const [expiryIndex, setExpiryIndex] = useState(0)
  const [chain,       setChain]       = useState<ChainData | null>(null)
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [showGreeks,  setShowGreeks]  = useState(true)

  // ── Fetch ──────────────────────────────────────────────────────
  const fetchChain = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `${API_BASE}/chain?symbol=${symbol}&expiry_index=${expiryIndex}`,
        { headers: HEADERS }
      )
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const json = await res.json()
      if (!json.success) throw new Error(json.error || 'Unknown error')
      setChain(json.data)
      setLastRefresh(new Date().toLocaleTimeString('en-IN'))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load options chain')
    } finally {
      setLoading(false)
    }
  }, [symbol, expiryIndex])

  // ── Load on mount and symbol/expiry change ─────────────────────
  useEffect(() => { fetchChain() }, [fetchChain])

  // ── Auto refresh every 60s ─────────────────────────────────────
  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(fetchChain, 60_000)
    return () => clearInterval(id)
  }, [autoRefresh, fetchChain])

  // ── Derived ────────────────────────────────────────────────────
  const maxCallOI    = chain ? Math.max(...chain.strikes.map(s => s.ce.oi), 1) : 1
  const maxPutOI     = chain ? Math.max(...chain.strikes.map(s => s.pe.oi), 1) : 1
  const summary      = chain?.summary
  const maxPain      = summary?.max_pain ?? 0
  const underlying   = chain?.underlying_price ?? 0

  // ─────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-arthai-dark text-white">
      <NavBar />

      {/* ── Page header ── */}
      <div className="max-w-screen-2xl mx-auto px-4 pt-5 pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">

          {/* Title + symbol tabs */}
          <div className="flex items-center gap-4 flex-wrap">
            <div>
              <h1 className="text-xl font-bold text-white">Options Chain</h1>
              <p className="text-gray-500 text-xs mt-0.5">
                Live CE/PE data · IV Rank · Max Pain · Greeks
              </p>
            </div>
            <div className="flex gap-1">
              {SYMBOLS.map(s => (
                <button
                  key={s}
                  onClick={() => { setSymbol(s); setExpiryIndex(0) }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold
                              transition-colors ${
                    symbol === s
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          {/* Underlying price + controls */}
          <div className="flex items-center gap-3 flex-wrap">
            {chain && (
              <div className="flex items-center gap-2">
                <span className="text-gray-400 text-sm">{symbol}</span>
                <span className="text-white text-2xl font-bold">
                  {fmt.price(chain.underlying_price)}
                </span>
                <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                  chain.source === 'NSE_LIVE'
                    ? 'bg-green-900/60 text-green-400 border border-green-700/40'
                    : 'bg-yellow-900/60 text-yellow-400 border border-yellow-700/40'
                }`}>
                  {chain.source === 'NSE_LIVE' ? '● LIVE' : '◌ EST'}
                </span>
              </div>
            )}

            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowGreeks(v => !v)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  showGreeks
                    ? 'bg-purple-700/80 text-white border border-purple-600/40'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                Greeks {showGreeks ? 'ON' : 'OFF'}
              </button>
              <button
                onClick={() => setAutoRefresh(v => !v)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  autoRefresh
                    ? 'bg-green-700/80 text-white border border-green-600/40'
                    : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                }`}
              >
                {autoRefresh ? '⟳ Auto ON' : '⟳ Auto OFF'}
              </button>
              <button
                onClick={fetchChain}
                disabled={loading}
                className="px-3 py-1.5 rounded-lg text-xs font-medium
                           bg-blue-700 hover:bg-blue-600 disabled:opacity-50
                           transition-colors text-white"
              >
                {loading ? 'Loading...' : 'Refresh'}
              </button>
              {lastRefresh && (
                <span className="text-gray-600 text-xs">
                  {lastRefresh}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Main content ── */}
      <div className="max-w-screen-2xl mx-auto px-4 pb-8 space-y-4">

        {/* Error */}
        {error && (
          <div className="bg-red-900/30 border border-red-700/50 rounded-xl
                          px-4 py-3 text-red-300 text-sm">
            {error}
          </div>
        )}

        {/* Loading */}
        {loading && !chain && (
          <div className="flex items-center justify-center py-24">
            <div className="text-center">
              <div className="w-10 h-10 border-4 border-blue-500
                              border-t-transparent rounded-full animate-spin
                              mx-auto mb-3" />
              <p className="text-gray-400 text-sm">Fetching options chain...</p>
              <p className="text-gray-600 text-xs mt-1">
                Connecting to NSE...
              </p>
            </div>
          </div>
        )}

        {chain && (
          <>
            {/* ── Summary stat cards ── */}
            <div className="flex flex-wrap gap-3">
              <PCRBadge
                pcr    = {summary?.pcr ?? 1}
                signal = {summary?.pcr_signal ?? 'NEUTRAL'}
              />
              <StatCard
                label = "Max Pain"
                value = {fmt.num(maxPain)}
                sub   = {
                  maxPain > 0
                    ? `${((underlying - maxPain) / maxPain * 100).toFixed(1)}% from spot`
                    : undefined
                }
                color = "text-purple-400"
              />
              <IVRankBar rank={chain.iv_rank} />
              <StatCard
                label = "IV Percentile"
                value = {fmt.pct(chain.iv_percentile)}
                sub   = "52-week"
                color = {chain.iv_percentile >= 70 ? 'text-red-400' : 'text-blue-400'}
              />
              <StatCard
                label = "Expected Move"
                value = {`± ${fmt.num(chain.expected_move)}`}
                sub   = {`${fmt.pct(chain.expected_move_pct)} | ${chain.dte} DTE`}
                color = "text-cyan-400"
              />
              <StatCard
                label = "ATM IV"
                value = {fmt.pct(chain.atm_iv)}
                sub   = {chain.iv_environment.replace(/_/g, ' ')}
                color = "text-orange-400"
              />
              <StatCard
                label = "Call OI"
                value = {fmt.oi(summary?.total_call_oi ?? 0)}
                color = "text-red-400"
              />
              <StatCard
                label = "Put OI"
                value = {fmt.oi(summary?.total_put_oi ?? 0)}
                color = "text-green-400"
              />
            </div>

            {/* ── Expected move range bar ── */}
            {chain.expected_move > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
                <p className="text-gray-500 text-xs mb-2 uppercase tracking-wide">
                  Expected Move Range (1 SD — 68% probability)
                </p>
                <div className="flex items-center justify-between gap-4">
                  <div className="text-left">
                    <p className="text-red-400 font-bold text-sm">
                      ▼ {fmt.num(summary?.expected_move_down ?? 0)}
                    </p>
                    <p className="text-gray-600 text-xs">Lower bound</p>
                  </div>
                  <div className="flex-1 relative h-3 bg-gray-800 rounded-full overflow-hidden">
                    <div className="absolute inset-y-0 left-[15%] right-[15%]
                                    bg-cyan-500/20 border-x border-cyan-600/40" />
                    {/* Current price marker */}
                    {summary?.expected_move_down && summary?.expected_move_up && (
                      <div
                        className="absolute top-1/2 -translate-y-1/2
                                   w-1.5 h-5 bg-white rounded-full shadow-lg"
                        style={{
                          left: `${Math.min(Math.max(
                            ((underlying - summary.expected_move_down) /
                             (summary.expected_move_up - summary.expected_move_down)) * 70 + 15,
                            5
                          ), 95)}%`,
                        }}
                      />
                    )}
                  </div>
                  <div className="text-right">
                    <p className="text-green-400 font-bold text-sm">
                      ▲ {fmt.num(summary?.expected_move_up ?? 0)}
                    </p>
                    <p className="text-gray-600 text-xs">Upper bound</p>
                  </div>
                </div>
              </div>
            )}

            {/* ── IV strategy hint ── */}
            {chain.iv_strategy_hint && (
              <div className="bg-blue-900/20 border border-blue-700/40 rounded-xl
                              px-4 py-2.5 text-sm text-blue-300">
                <span className="font-semibold text-blue-400">Strategy Hint: </span>
                {chain.iv_strategy_hint}
              </div>
            )}

            {/* ── Alerts ── */}
            {chain.alerts.length > 0 && (
              <div className="space-y-2">
                {chain.alerts.map((alert, i) => (
                  <AlertBanner key={i} alert={alert} />
                ))}
              </div>
            )}

            {/* ── Expiry switcher ── */}
            {chain.expiry_dates.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-gray-500 text-xs uppercase tracking-wide">
                  Expiry:
                </span>
                {chain.expiry_dates.map((exp, i) => (
                  <button
                    key={exp}
                    onClick={() => setExpiryIndex(i)}
                    className={`px-3 py-1 rounded-lg text-xs font-medium
                                transition-colors ${
                      i === expiryIndex
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-white'
                    }`}
                  >
                    {exp}
                    {i === 0 && (
                      <span className="ml-1 text-yellow-400 font-bold">W</span>
                    )}
                  </button>
                ))}
                <span className="text-gray-600 text-xs">
                  {chain.dte} days to expiry
                </span>
              </div>
            )}

            {/* ── Key levels ── */}
            <div className="flex flex-wrap gap-3 text-sm">
              {(summary?.call_wall ?? 0) > 0 && (
                <div className="bg-red-900/20 border border-red-700/40
                                rounded-lg px-3 py-1.5">
                  <span className="text-gray-500 text-xs">Resistance (Call Wall): </span>
                  <span className="text-red-400 font-bold">
                    {fmt.num(summary!.call_wall)}
                  </span>
                </div>
              )}
              {(summary?.put_wall ?? 0) > 0 && (
                <div className="bg-green-900/20 border border-green-700/40
                                rounded-lg px-3 py-1.5">
                  <span className="text-gray-500 text-xs">Support (Put Wall): </span>
                  <span className="text-green-400 font-bold">
                    {fmt.num(summary!.put_wall)}
                  </span>
                </div>
              )}
              {maxPain > 0 && (
                <div className="bg-purple-900/20 border border-purple-700/40
                                rounded-lg px-3 py-1.5">
                  <span className="text-gray-500 text-xs">Max Pain: </span>
                  <span className="text-purple-400 font-bold">
                    {fmt.num(maxPain)}
                  </span>
                </div>
              )}
            </div>

            {/* ── Options chain table ── */}
            {chain.strikes.length === 0 ? (
              <div className="bg-gray-900 border border-gray-800 rounded-xl
                              p-10 text-center">
                <p className="text-gray-400 text-lg mb-2">
                  No options data available
                </p>
                <p className="text-gray-600 text-sm">
                  {chain.source === 'NSE_LIVE'
                    ? 'NSE returned empty chain — market may be closed'
                    : 'NSE unavailable and yfinance returned no strikes'}
                </p>
              </div>
            ) : (
              <div className="bg-gray-900 border border-gray-800 rounded-xl
                              overflow-x-auto">
                <table className="w-full text-xs border-collapse">
                  <thead>

                    {/* Section headers */}
                    <tr className="border-b border-gray-700">
                      <th
                        colSpan={showGreeks ? 9 : 6}
                        className="py-2 text-center text-red-400 font-semibold
                                   bg-red-900/10 border-r border-gray-700"
                      >
                        CALLS (CE)
                      </th>
                      <th className="py-2 text-center text-white font-bold
                                     bg-gray-800 border-r border-gray-700 px-3">
                        STRIKE
                      </th>
                      <th
                        colSpan={showGreeks ? 9 : 6}
                        className="py-2 text-center text-green-400 font-semibold
                                   bg-green-900/10"
                      >
                        PUTS (PE)
                      </th>
                    </tr>

                    {/* Column headers */}
                    <tr className="border-b border-gray-700 bg-gray-800/60
                                   text-gray-500 uppercase tracking-wide text-[10px]">
                      {/* CE columns */}
                      <th className="px-2 py-2 text-right">Trend</th>
                      <th className="px-2 py-2 text-right">Chg OI</th>
                      <th className="px-2 py-2 text-right">Vol</th>
                      <th className="px-2 py-2 text-right">OI</th>
                      <th className="px-2 py-2 text-right">IV</th>
                      {showGreeks && (
                        <>
                          <th className="px-2 py-2 text-right">Delta</th>
                          <th className="px-2 py-2 text-right">Gamma</th>
                          <th className="px-2 py-2 text-right">Theta</th>
                        </>
                      )}
                      <th className="px-2 py-2 text-right border-r border-gray-700">
                        LTP
                      </th>

                      {/* Strike */}
                      <th className="px-3 py-2 text-center bg-gray-800
                                     border-r border-gray-700 text-white">
                        Strike
                      </th>

                      {/* PE columns */}
                      <th className="px-2 py-2 text-left">LTP</th>
                      {showGreeks && (
                        <>
                          <th className="px-2 py-2 text-left">Delta</th>
                          <th className="px-2 py-2 text-left">Gamma</th>
                          <th className="px-2 py-2 text-left">Theta</th>
                        </>
                      )}
                      <th className="px-2 py-2 text-left">IV</th>
                      <th className="px-2 py-2 text-left">OI</th>
                      <th className="px-2 py-2 text-left">Vol</th>
                      <th className="px-2 py-2 text-left">Chg OI</th>
                      <th className="px-2 py-2 text-left">Trend</th>
                    </tr>
                  </thead>

                  <tbody>
                    {chain.strikes.map(row => (
                      <StrikeRow
                        key            = {row.strike}
                        row            = {row}
                        maxCallOI      = {maxCallOI}
                        maxPutOI       = {maxPutOI}
                        maxPain        = {maxPain}
                        underlyingPrice= {underlying}
                        showGreeks     = {showGreeks}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* ── Footer info ── */}
            <div className="flex flex-wrap justify-between items-center
                            text-gray-700 text-xs pb-2">
              <span>
                Source: {chain.source} ·
                ATM Strike: {fmt.num(chain.atm_strike)} ·
                Greeks: Black-Scholes (ArthAI)
              </span>
              <span>
                Updated: {new Date(chain.timestamp).toLocaleTimeString('en-IN')}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  )
}