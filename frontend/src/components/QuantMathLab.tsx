import React from 'react'
import { Shield, Cpu, Activity, Disc } from 'lucide-react'

export const QuantMathLab: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="glass-panel rounded-xl p-6">
        <div className="flex items-center gap-2 text-xs font-mono text-purple-400 uppercase tracking-wider mb-1">
          <Cpu className="w-4 h-4" />
          <span>Module 2 Advanced Mathematical & Microstructure Laboratory</span>
        </div>
        <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight">
          Microstructure Estimators & Regime Memory
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Non-linear statistical estimators: Hurst Exponent (H), Yang-Zhang Realized Volatility, 1D Kalman Filter, and Amihud Illiquidity.
        </p>
      </div>

      {/* 4 Models Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Model 1: Hurst Exponent */}
        <div className="glass-panel p-5 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold uppercase text-slate-200 flex items-center gap-2">
              <Disc className="w-4 h-4 text-blue-400" />
              1. Hurst Exponent (H)
            </h3>
            <span className="text-xs font-mono bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20">
              H = 0.42 (Mean-Reverting)
            </span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed mb-4">
            Rescaled Range (R/S) structural memory. H &lt; 0.45 indicates strong anti-persistent mean-reversion, favoring S01 RSI Pullback and S04 Mean Reversion.
          </p>
          <div className="w-full bg-black/40 rounded-full h-3 overflow-hidden border border-white/10">
            <div className="bg-gradient-to-r from-emerald-500 to-blue-500 h-full rounded-full" style={{ width: '42%' }} />
          </div>
          <div className="flex justify-between text-[10px] font-mono text-slate-500 mt-1.5">
            <span>0.0 (Mean-Reverting)</span>
            <span>0.5 (Random Walk)</span>
            <span>1.0 (Persistent Trend)</span>
          </div>
        </div>

        {/* Model 2: Yang-Zhang Volatility */}
        <div className="glass-panel p-5 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold uppercase text-slate-200 flex items-center gap-2">
              <Activity className="w-4 h-4 text-amber-400" />
              2. Yang-Zhang Realized Vol (2000)
            </h3>
            <span className="text-xs font-mono bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded border border-blue-500/20">
              σ(YZ) = 12.4%
            </span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed mb-4">
            The only minimum-variance, unbiased realized volatility estimator accounting for overnight opening jumps and continuous intraday drift.
          </p>
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="bg-black/40 p-2.5 rounded border border-white/5">
              <div className="text-slate-400">Yang-Zhang (20D):</div>
              <div className="text-slate-100 font-bold mt-0.5">12.4% Realized</div>
            </div>
            <div className="bg-black/40 p-2.5 rounded border border-white/5">
              <div className="text-slate-400">Classical ATR:</div>
              <div className="text-slate-100 font-bold mt-0.5">14.1% Estimate</div>
            </div>
          </div>
        </div>

        {/* Model 3: 1D Kalman Filter */}
        <div className="glass-panel p-5 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold uppercase text-slate-200 flex items-center gap-2">
              <Shield className="w-4 h-4 text-purple-400" />
              3. 1D State-Space Kalman Filter
            </h3>
            <span className="text-xs font-mono bg-purple-500/10 text-purple-400 px-2 py-0.5 rounded border border-purple-500/20">
              Velocity: +2.1 pts/m
            </span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed mb-3">
            Eliminates moving average phase lag while filtering out microstructure noise with zero lookahead bias.
          </p>
          <div className="bg-black/40 p-3 rounded-lg border border-white/5 text-xs font-mono space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-400">Latent Estimated Price:</span>
              <span className="text-slate-100 font-bold">23,916.20</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Measurement Noise Covariance:</span>
              <span className="text-slate-300">0.01</span>
            </div>
          </div>
        </div>

        {/* Model 4: Amihud Illiquidity */}
        <div className="glass-panel p-5 rounded-xl">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold uppercase text-slate-200 flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-400" />
              4. Amihud Illiquidity Ratio (2002)
            </h3>
            <span className="text-xs font-mono bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded border border-emerald-500/20">
              Liquid (0.018)
            </span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed mb-3">
            Measures price impact per ₹10 Lakhs turnover to safeguard against executing in illiquid strikes or wide bid-ask spreads.
          </p>
          <div className="bg-black/40 p-3 rounded-lg border border-white/5 text-xs font-mono space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-400">Slippage Penalty Buffer:</span>
              <span className="text-emerald-400 font-bold">0.02% (Ultra Low)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Corwin-Schultz Spread:</span>
              <span className="text-slate-300">3.2 bps</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
