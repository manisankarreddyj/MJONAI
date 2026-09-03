import React, { useState, useEffect } from 'react'
import { Navbar } from './components/Navbar'
import { MarketCockpit } from './components/MarketCockpit'
import { TradingViewStudio } from './components/TradingViewStudio'
import { DerivativesHub } from './components/DerivativesHub'
import { QuantMathLab } from './components/QuantMathLab'

export default function App() {
  const [activeTab, setActiveTab] = useState('cockpit')
  const [marketData, setMarketData] = useState<any>(null)

  useEffect(() => {
    async function fetchMarketData() {
      try {
        const res = await fetch('/api/market/cockpit')
        if (res.ok) {
          const json = await res.json()
          setMarketData(json)
        }
      } catch (e) {
        console.error('Failed fetching cockpit data:', e)
      }
    }
    fetchMarketData()
    const interval = setInterval(fetchMarketData, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="min-h-screen bg-[#060911] text-slate-100 flex flex-col">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        regime={marketData?.regime || 'NEUTRAL'}
        mqiLevel={marketData?.mqi_level || 'MEDIUM'}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6">
        {activeTab === 'cockpit' && <MarketCockpit data={marketData} />}
        {activeTab === 'tradingview' && <TradingViewStudio />}
        {activeTab === 'derivatives' && <DerivativesHub />}
        {activeTab === 'quantmath' && <QuantMathLab />}
      </main>

      <footer className="border-t border-white/5 py-4 text-center text-xs font-mono text-slate-500">
        MJONAI Autonomous Quant Engine · Module 1 & 2 Live Operational Cockpit · Top 1% Institutional Architecture
      </footer>
    </div>
  )
}
