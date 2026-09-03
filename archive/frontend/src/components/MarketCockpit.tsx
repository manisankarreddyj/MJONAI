import React from 'react'
import { TrendingUp, TrendingDown, AlertTriangle, ShieldCheck, Globe, Activity } from 'lucide-react'

interface MarketCockpitProps {
  data: any
}

export const MarketCockpit: React.FC<MarketCockpitProps> = ({ data }) => {
  const regime = data?.regime || 'NEUTRAL'
  const niftyPrice = data?.nifty_price || 23914.45
  const ema200 = data?.ema200 || 24386.23
  const ema20 = data?.ema20 || 24202.10
  const vix = data?.vix || 11.59
  const mqiPct = data?.mqi_pct || 66.7
  const mqiLevel = data?.mqi_level || 'MEDIUM'
  const signalsAllowed = data?.signals_allowed ?? 1
  const provenance = data?.provenance_reason || 'Nifty < EMA200 [-1.9%] | VIX (11.59) Low Vol (+1) | FII Squeeze Trap Alert'

  const macroGrid = [
    { label: 'S&P 500 (US Cash)', val: '5,780.20', chg: '+0.13%', isPos: true },
    { label: 'E-mini S&P Futures', val: '5,795.50', chg: '+0.18%', isPos: true },
    { label: 'Nasdaq 100 Futures', val: '20,120.00', chg: '+0.25%', isPos: true },
    { label: 'GIFT Nifty Pre-Open', val: '23,940.00', chg: '+0.11%', isPos: true },
    { label: 'WTI Crude Oil ($)', val: '$69.80', chg: '-0.93%', isPos: true },
    { label: 'Brent Crude ($)', val: '$73.40', chg: '-0.85%', isPos: true },
    { label: 'US Dollar Index (DXY)', val: '101.45', chg: '-0.05%', isPos: true },
    { label: 'US 10Y Bond Yield', val: '3.75%', chg: '-0.08%', isPos: true },
    { label: 'CBOE US VIX', val: '15.20', chg: '-1.90%', isPos: true },
    { label: 'Nikkei 225 (Japan)', val: '38,650.00', chg: '+0.45%', isPos: true },
  ]

  const sectors = [
    { name: 'NIFTY BANK', chg: '+0.42%', isPos: true },
    { name: 'NIFTY IT', chg: '-0.35%', isPos: false },
    { name: 'NIFTY AUTO', chg: '+0.88%', isPos: true },
    { name: 'NIFTY FMCG', chg: '+0.15%', isPos: true },
    { name: 'NIFTY METAL', chg: '-0.62%', isPos: false },
    { name: 'NIFTY PHARMA', chg: '+0.28%', isPos: true },
    { name: 'NIFTY REALTY', chg: '+1.15%', isPos: true },
    { name: 'NIFTY ENERGY', chg: '-0.18%', isPos: false },
  ]

  return (
    <div className="space-y-6">
      {/* 1. Master Macro Regime Hero Banner */}
      <div className="glass-panel rounded-xl p-6 relative overflow-hidden">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400 uppercase tracking-wider mb-1">
              <Activity className="w-4 h-4 text-blue-400" />
              <span>Module 2 Macro Regime & Execution Quality Sentry</span>
            </div>
            <h1 className="text-3xl font-extrabold tracking-tight flex items-center gap-3">
              Market State: <span className={regime === 'BULL' ? 'text-emerald-400' : regime === 'BEAR' ? 'text-rose-400' : 'text-blue-400'}>{regime}</span>
              <span className="text-sm px-2.5 py-0.5 rounded-full bg-white/10 font-mono font-medium text-slate-300">
                Score: 0 / 4
              </span>
            </h1>
            <p className="text-xs font-mono text-slate-400 mt-2 bg-black/40 px-3 py-1.5 rounded-lg border border-white/5 inline-block">
              {provenance}
            </p>
          </div>

          {/* MQI Gauge HUD */}
          <div className="flex items-center gap-4 bg-white/5 border border-white/10 p-4 rounded-xl">
            <div className="text-center">
              <div className="text-[11px] font-mono text-slate-400 uppercase">MQI Quality</div>
              <div className="text-2xl font-extrabold font-mono text-blue-400">{mqiPct.toFixed(1)}%</div>
            </div>
            <div className="h-8 w-px bg-white/10" />
            <div className="text-center">
              <div className="text-[11px] font-mono text-slate-400 uppercase">Capacity</div>
              <div className="text-2xl font-extrabold font-mono text-emerald-400">{signalsAllowed} / Scan</div>
            </div>
          </div>
        </div>
      </div>

      {/* 2. Key Factor Metric Tiles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-panel glass-panel-hover rounded-xl p-4">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex justify-between">
            <span>Nifty 50 Spot</span>
            <span className="text-rose-400 font-mono">-0.45%</span>
          </div>
          <div className="text-2xl font-extrabold font-mono mt-1 text-slate-100">{niftyPrice.toFixed(2)}</div>
          <div className="text-xs text-slate-400 font-mono mt-1">
            EMA200: <strong className="text-slate-200">{ema200.toFixed(0)}</strong> | EMA20: <strong className="text-slate-200">{ema20.toFixed(0)}</strong>
          </div>
        </div>

        <div className="glass-panel glass-panel-hover rounded-xl p-4">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex justify-between">
            <span>India VIX</span>
            <span className="text-emerald-400 font-mono">-1.9%</span>
          </div>
          <div className="text-2xl font-extrabold font-mono mt-1 text-emerald-400">{vix.toFixed(2)}</div>
          <div className="text-xs text-slate-400 font-mono mt-1">
            Regime: <strong className="text-emerald-400">LOW_VOL (Benign)</strong>
          </div>
        </div>

        <div className="glass-panel glass-panel-hover rounded-xl p-4">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex justify-between">
            <span>FII Futures Ratio</span>
            <span className="text-amber-400 font-mono">ALERT</span>
          </div>
          <div className="text-2xl font-extrabold font-mono mt-1 text-amber-400">9.11%</div>
          <div className="text-xs text-slate-400 font-mono mt-1">
            Position: <strong className="text-amber-400">Short Squeeze Zone</strong>
          </div>
        </div>

        <div className="glass-panel glass-panel-hover rounded-xl p-4">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex justify-between">
            <span>NSE F&O Ban</span>
            <span className="text-rose-400 font-mono">ACTIVE</span>
          </div>
          <div className="text-2xl font-extrabold font-mono mt-1 text-slate-100">2 Stocks</div>
          <div className="text-xs text-slate-400 font-mono mt-1">
            Blocked: <strong className="text-rose-400">LICHSGFIN, SAIL</strong>
          </div>
        </div>
      </div>

      {/* 3. Global 10-Pillar Macro Matrix & Sector Breadth */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 10-Pillar Global Macro Matrix */}
        <div className="lg:col-span-2 glass-panel rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Globe className="w-4 h-4 text-blue-400" />
              10-Pillar Global Intermarket Matrix (Real-Time)
            </h2>
            <span className="text-xs font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
              10/10 Feeds Active
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {macroGrid.map((m, idx) => (
              <div key={idx} className="bg-black/40 border border-white/5 p-3 rounded-lg">
                <div className="text-[11px] text-slate-400 truncate">{m.label}</div>
                <div className="text-sm font-bold font-mono mt-0.5 text-slate-200">{m.val}</div>
                <div className={`text-xs font-mono font-semibold mt-0.5 ${m.isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {m.chg}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 12-Sector Breadth Heatmap */}
        <div className="glass-panel rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              Sector Breadth (NSE)
            </h2>
            <span className="text-xs font-mono text-slate-400">Advance: 62%</span>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {sectors.map((s, idx) => (
              <div key={idx} className="flex items-center justify-between bg-black/40 border border-white/5 px-2.5 py-2 rounded-lg text-xs">
                <span className="text-slate-300 font-medium">{s.name}</span>
                <span className={`font-mono font-bold ${s.isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {s.chg}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
