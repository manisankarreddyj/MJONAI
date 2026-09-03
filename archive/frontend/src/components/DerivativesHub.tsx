import React from 'react'
import { Layers, Zap, AlertOctagon, TrendingUp } from 'lucide-react'

export const DerivativesHub: React.FC = () => {
  const gexStrikes = [
    { strike: 23600, callOi: '15.2k', putOi: '110.5k', gexCr: '+12.5', isPutWall: true },
    { strike: 23700, callOi: '25.0k', putOi: '85.2k', gexCr: '+28.4' },
    { strike: 23800, callOi: '65.4k', putOi: '55.0k', gexCr: '+45.0', isZeroGamma: true },
    { strike: 23900, callOi: '95.1k', putOi: '20.1k', gexCr: '-18.2' },
    { strike: 24000, callOi: '120.8k', putOi: '10.5k', gexCr: '-65.4', isCallWall: true },
  ]

  return (
    <div className="space-y-6">
      {/* Hero Summary */}
      <div className="glass-panel rounded-xl p-6">
        <div className="flex items-center gap-2 text-xs font-mono text-blue-400 uppercase tracking-wider mb-1">
          <Layers className="w-4 h-4" />
          <span>Module 1 Institutional Option Chain & Gamma Positioning</span>
        </div>
        <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">
          Dealer Gamma Exposure (GEX) & Zero-Gamma Matrix
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Real-time institutional options dealer hedging requirements and Gamma Flip price discovery.
        </p>
      </div>

      {/* GEX Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-panel p-4 rounded-xl">
          <div className="text-xs text-slate-400 font-semibold uppercase">Zero-Gamma Level (Flip Point)</div>
          <div className="text-3xl font-extrabold font-mono text-blue-400 mt-1">23,800</div>
          <div className="text-xs text-emerald-400 font-mono mt-1">
            Spot (23,914) &gt; Zero-Gamma $\rightarrow$ Positive Gamma (Mean Reverting)
          </div>
        </div>

        <div className="glass-panel p-4 rounded-xl">
          <div className="text-xs text-slate-400 font-semibold uppercase">Major Call Wall (Dealer Magnet)</div>
          <div className="text-3xl font-extrabold font-mono text-rose-400 mt-1">24,000</div>
          <div className="text-xs text-slate-400 font-mono mt-1">Heavy Call OI: 120.8k contracts</div>
        </div>

        <div className="glass-panel p-4 rounded-xl">
          <div className="text-xs text-slate-400 font-semibold uppercase">Major Put Wall (Support Floor)</div>
          <div className="text-3xl font-extrabold font-mono text-emerald-400 mt-1">23,600</div>
          <div className="text-xs text-slate-400 font-mono mt-1">Heavy Put OI: 110.5k contracts</div>
        </div>
      </div>

      {/* Option Strike GEX Ladder */}
      <div className="glass-panel rounded-xl p-5 overflow-hidden">
        <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200 mb-4 flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          Strike-by-Strike Gamma Exposure (INR Crores)
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-xs font-mono text-left">
            <thead>
              <tr className="border-b border-white/10 text-slate-400 uppercase">
                <th className="py-2.5 px-3">Call OI</th>
                <th className="py-2.5 px-3 text-center">Strike Price</th>
                <th className="py-2.5 px-3 text-right">Put OI</th>
                <th className="py-2.5 px-3 text-right">Net GEX (₹ Cr)</th>
                <th className="py-2.5 px-3 text-right">Classification</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {gexStrikes.map((s) => (
                <tr key={s.strike} className={s.isZeroGamma ? 'bg-blue-500/10' : ''}>
                  <td className="py-2.5 px-3 text-slate-300">{s.callOi}</td>
                  <td className="py-2.5 px-3 text-center font-bold text-slate-100">{s.strike}</td>
                  <td className="py-2.5 px-3 text-right text-slate-300">{s.putOi}</td>
                  <td className={`py-2.5 px-3 text-right font-bold ${s.gexCr.startsWith('+') ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {s.gexCr}
                  </td>
                  <td className="py-2.5 px-3 text-right">
                    {s.isCallWall && <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-400 border border-rose-500/30">CALL WALL</span>}
                    {s.isPutWall && <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">PUT WALL</span>}
                    {s.isZeroGamma && <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">GAMMA FLIP</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
