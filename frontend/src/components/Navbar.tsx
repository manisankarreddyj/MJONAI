import React from 'react'
import { Activity, BarChart2, Shield, Layers, Radio } from 'lucide-react'

interface NavbarProps {
  activeTab: string
  setActiveTab: (tab: string) => void
  regime: string
  mqiLevel: string
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  regime,
  mqiLevel
}) => {
  const getRegimeColor = (r: string) => {
    switch (r) {
      case 'BULL': return 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400'
      case 'BEAR': return 'bg-rose-500/15 border-rose-500/30 text-rose-400'
      case 'DEGRADED': return 'bg-amber-500/15 border-amber-500/30 text-amber-400'
      default: return 'bg-blue-500/15 border-blue-500/30 text-blue-400'
    }
  }

  return (
    <header className="sticky top-0 z-50 bg-[#080c14]/85 backdrop-blur-xl border-b border-white/10 px-6 py-3.5 flex items-center justify-between">
      {/* Brand & Live Pulse */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_#10b981] animate-pulse" />
          <span className="font-extrabold text-lg tracking-wider bg-gradient-to-r from-blue-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">
            MJONAI
          </span>
          <span className="text-[10px] font-mono tracking-widest text-slate-400 uppercase px-1.5 py-0.5 rounded bg-white/5 border border-white/10">
            QUANT TERMINAL
          </span>
        </div>

        {/* Dynamic Status Badges */}
        <div className="flex items-center gap-2 text-xs font-mono">
          <span className={`px-2.5 py-1 rounded-md border font-semibold ${getRegimeColor(regime)}`}>
            REGIME: {regime}
          </span>
          <span className="px-2.5 py-1 rounded-md border border-white/10 bg-white/5 text-slate-300">
            MQI: {mqiLevel}
          </span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <nav className="flex items-center gap-1 bg-[#0f172a]/60 p-1 rounded-lg border border-white/5">
        <button
          onClick={() => setActiveTab('cockpit')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeTab === 'cockpit'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
          }`}
        >
          <Activity className="w-3.5 h-3.5" />
          Market Cockpit
        </button>

        <button
          onClick={() => setActiveTab('tradingview')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeTab === 'tradingview'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
          }`}
        >
          <BarChart2 className="w-3.5 h-3.5" />
          TradingView Studio
        </button>

        <button
          onClick={() => setActiveTab('derivatives')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeTab === 'derivatives'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
          }`}
        >
          <Layers className="w-3.5 h-3.5" />
          GEX & F&O Flow
        </button>

        <button
          onClick={() => setActiveTab('quantmath')}
          className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium transition-all ${
            activeTab === 'quantmath'
              ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/30'
              : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
          }`}
        >
          <Shield className="w-3.5 h-3.5" />
          Quant Math Lab
        </button>
      </nav>

      {/* Multi-Broker Status Indicator */}
      <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
        <div className="flex items-center gap-1.5">
          <Radio className="w-3.5 h-3.5 text-emerald-400" />
          <span>Angel One: <strong className="text-emerald-400">LIVE</strong></span>
        </div>
        <div className="flex items-center gap-1.5">
          <Radio className="w-3.5 h-3.5 text-emerald-400" />
          <span>Shoonya: <strong className="text-emerald-400">LIVE</strong></span>
        </div>
      </div>
    </header>
  )
}
