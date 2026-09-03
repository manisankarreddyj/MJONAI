'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { getSystemStatus } from '@/lib/api'

const navItems = [
  { href: '/',             label: 'Dashboard',   icon: '📊' },
  { href: '/signals',      label: 'Signals',     icon: '🎯' },
  { href: '/options',      label: 'Options',     icon: '⛓️' },
  { href: '/portfolio',    label: 'Portfolio',   icon: '💼' },
  { href: '/paper-trading',label: 'Paper Trades',icon: '📄' },
  { href: '/performance',  label: 'Performance', icon: '📈' },
  { href: '/market',       label: 'Market',      icon: '🌍' },
  { href: '/assistant',    label: 'Assistant',   icon: '🤖' },
  { href: '/system',       label: 'System',      icon: '⚙️' },
]

export default function NavBar() {
  const pathname    = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [vixData, setVixData] = useState<any>(null)

  // Fetch VIX / System Status (Task 2.2)
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const data = await getSystemStatus()
        if (data && data.success && data.status) {
          setVixData(data.status.vix)
        }
      } catch (err) {
        console.error("VIX Fetch Error:", err)
      }
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000) // 30s refresh
    return () => clearInterval(interval)
  }, [])

  const isCrisis = vixData?.regime === 'CRISIS'
  const navBorderColor = isCrisis ? 'border-red-600 shadow-[0_0_15px_rgba(220,38,38,0.3)]' : 'border-gray-800'
  const regimeColor = 
    vixData?.regime === 'NORMAL' ? 'text-emerald-400 bg-emerald-900/30 border-emerald-800' :
    vixData?.regime === 'LOW_VOL' ? 'text-blue-400 bg-blue-900/30 border-blue-800' :
    vixData?.regime === 'ELEVATED' ? 'text-yellow-400 bg-yellow-900/30 border-yellow-800' :
    'text-red-400 bg-red-900/40 border-red-800'

  return (
    <nav className={`bg-gray-900 border-b ${navBorderColor} sticky top-0 z-50 transition-all duration-500`}>
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">

          {/* Logo */}
          <Link href="/" className="flex items-center gap-2 main-logo">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center
                            justify-center text-white font-bold text-sm">
              A
            </div>
            <div>
              <span className="text-white font-bold text-lg">ArthAI</span>
              <div className="text-xs text-gray-400 leading-none">
                Paper Trading
              </div>
            </div>
          </Link>

          {/* Desktop Nav */}
          <div className="hidden lg:flex items-center gap-0.5 overflow-x-auto">
            {navItems.map((item) => {
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-1.5 px-2.5 py-2 rounded-lg
                              text-sm transition-colors duration-150 whitespace-nowrap
                              ${isActive
                                ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
                                : 'text-gray-400 hover:text-white hover:bg-gray-800'
                              }`}
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </div>

          {/* Status & VIX Badge */}
          <div className="hidden md:flex items-center gap-4 shrink-0">
            {vixData && (
              <div className={`flex items-center gap-2 px-2.5 py-1 rounded border ${regimeColor} animate-pulse-slow`}>
                <span className="text-[10px] font-bold uppercase tracking-wider opacity-70">VIX</span>
                <span className="text-xs font-bold">{vixData.vix}</span>
                <span className="h-3 w-px bg-current opacity-20" />
                <span className="text-[10px] font-extrabold uppercase">{vixData.regime}</span>
              </div>
            )}
            
            <div className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${isCrisis ? 'bg-red-500' : 'bg-emerald-400'} animate-pulse`} />
              <span className="text-xs text-gray-400 font-medium">{isCrisis ? 'Crisis' : 'Live'}</span>
            </div>
          </div>

          {/* Mobile menu button */}
          <button
            className="md:hidden text-gray-400 hover:text-white p-2"
            onClick={() => setMobileOpen(!mobileOpen)}
          >
            {mobileOpen ? '✕' : '☰'}
          </button>
        </div>

        {/* Mobile menu */}
        {mobileOpen && (
          <div className="md:hidden py-2 border-t border-gray-800">
            {navItems.map((item) => {
              const isActive = pathname === item.href
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-2 px-4 py-3 text-sm
                              ${isActive
                                ? 'text-blue-400 bg-blue-600/10'
                                : 'text-gray-400 hover:text-white'
                              }`}
                >
                  <span>{item.icon}</span>
                  <span>{item.label}</span>
                </Link>
              )
            })}
          </div>
        )}
      </div>
    </nav>
  )
}