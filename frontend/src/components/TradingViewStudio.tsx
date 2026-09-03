import React, { useEffect, useRef, useState } from 'react'
import { BarChart2, Search } from 'lucide-react'

declare global {
  interface Window {
    TradingView: any
  }
}

export const TradingViewStudio: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null)
  const [selectedSymbol, setSelectedSymbol] = useState('NSE:NIFTY')

  const popularSymbols = [
    { label: 'Nifty 50', sym: 'NSE:NIFTY' },
    { label: 'Bank Nifty', sym: 'NSE:BANKNIFTY' },
    { label: 'Sensex', sym: 'BSE:SENSEX' },
    { label: 'Reliance', sym: 'NSE:RELIANCE' },
    { label: 'HDFC Bank', sym: 'NSE:HDFCBANK' },
    { label: 'TCS', sym: 'NSE:TCS' },
    { label: 'Infosys', sym: 'NSE:INFY' },
  ]

  useEffect(() => {
    if (containerRef.current && window.TradingView) {
      containerRef.current.innerHTML = ''
      new window.TradingView.widget({
        autosize: true,
        symbol: selectedSymbol,
        interval: '15',
        timezone: 'Asia/Kolkata',
        theme: 'dark',
        style: '1',
        locale: 'en',
        toolbar_bg: '#080c14',
        enable_publishing: false,
        allow_symbol_change: true,
        container_id: 'tradingview_widget_container',
        hide_side_toolbar: false,
        studies: [
          'STD;EMA',
          'STD;RSI',
          'STD;MACD',
        ],
      })
    }
  }, [selectedSymbol])

  const [customInput, setCustomInput] = useState('')

  const handleCustomSearch = (e: React.FormEvent) => {
    e.preventDefault()
    if (!customInput.trim()) return
    let clean = customInput.trim().toUpperCase()
    if (!clean.includes(':')) {
      clean = `NSE:${clean}`
    }
    setSelectedSymbol(clean)
    setCustomInput('')
  }

  return (
    <div className="space-y-4">
      {/* Symbol Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 glass-panel p-3.5 rounded-xl">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-blue-400" />
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              TradingView Studio
            </span>
          </div>

          {/* Dynamic Symbol Search Box */}
          <form onSubmit={handleCustomSearch} className="relative flex items-center">
            <input
              type="text"
              value={customInput}
              onChange={(e) => setCustomInput(e.target.value)}
              placeholder="Search any stock (e.g. SBIN, TATAMOTORS)..."
              className="bg-black/50 border border-white/10 rounded-lg px-3 py-1 text-xs font-mono text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-blue-500 w-64 pl-8"
            />
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
          </form>
        </div>

        {/* Fast Scrip Switchers */}
        <div className="flex flex-wrap items-center gap-1.5">
          {popularSymbols.map((item) => (
            <button
              key={item.sym}
              onClick={() => setSelectedSymbol(item.sym)}
              className={`px-3 py-1 rounded-md text-xs font-mono font-medium transition-all ${
                selectedSymbol === item.sym
                  ? 'bg-blue-600 text-white font-bold shadow-md shadow-blue-600/30'
                  : 'bg-black/40 border border-white/5 text-slate-400 hover:text-slate-200'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Advanced TradingView Widget Container */}
      <div className="glass-panel rounded-xl overflow-hidden border border-white/10" style={{ height: '720px' }}>
        <div id="tradingview_widget_container" ref={containerRef} className="w-full h-full" />
      </div>
    </div>
  )
}
