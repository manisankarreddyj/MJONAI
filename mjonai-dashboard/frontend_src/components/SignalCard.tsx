interface Signal {
  id?: string
  symbol: string
  action: string
  entry_price?: number
  entry_low?: number
  entry_high?: number
  stop_loss?: number
  target_1?: number
  target_2?: number
  confidence?: number
  final_confidence?: number
  consensus?: string
  risk_percent?: number
  risk_reward?: number
  market_mood?: string
  bull_verdict?: string
  bear_verdict?: string
  econ_verdict?: string
  devil_verdict?: string
  why_approved?: string
  status?: string
  trading_mode?: string
  created_at?: string
  correlation_multiplier?: number
  vix_size_multiplier?: number
  vix_regime?: string
  vix_value?: number
}

interface SignalCardProps {
  signal: Signal
}

function AgentBadge({
  agent,
  verdict
}: {
  agent: string
  verdict?: string
}) {
  const isBullish = verdict?.toLowerCase().includes('buy') ||
    verdict?.toLowerCase().includes('bullish') ||
    verdict?.toLowerCase().includes('agree') ||
    verdict?.toLowerCase().includes('failed')  // devil failed to break = good

  const isNeutral = verdict?.toLowerCase().includes('neutral') ||
    verdict?.toLowerCase().includes('caution') ||
    verdict?.toLowerCase().includes('moderate')

  const color = isBullish
    ? 'bg-emerald-900/50 text-emerald-400 border-emerald-800'
    : isNeutral
    ? 'bg-yellow-900/50 text-yellow-400 border-yellow-800'
    : 'bg-red-900/50 text-red-400 border-red-800'

  return (
    <div className={`text-xs px-2 py-1 rounded border ${color} flex items-center gap-1`}>
      <span className="font-medium">{agent}:</span>
      <span>{verdict || 'N/A'}</span>
    </div>
  )
}

export default function SignalCard({ signal }: SignalCardProps) {
  const isBuy = signal.action === 'BUY'
  const confidence = signal.final_confidence || signal.confidence || 0
  const entry = signal.entry_price || signal.entry_low || 0
  
  const time = signal.created_at
    ? new Date(signal.created_at).toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      })
    : '--'

  const actionColor = isBuy
    ? 'bg-emerald-500/20 text-emerald-400 border-emerald-600'
    : 'bg-red-500/20 text-red-400 border-red-600'

  const confidenceColor =
    confidence >= 80 ? 'text-emerald-400' :
    confidence >= 65 ? 'text-yellow-400' :
    'text-red-400'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 
                    hover:border-blue-800 transition-all duration-200 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-white">{signal.symbol}</span>
          <span className={`px-3 py-1 rounded-full text-sm font-bold border ${actionColor}`}>
            {signal.action}
          </span>
          {signal.trading_mode === 'PAPER' && (
            <span className="px-2 py-0.5 rounded text-xs bg-blue-900/50 
                           text-blue-400 border border-blue-800">
              PAPER
            </span>
          )}
          
          {/* Risk Scaling Badge (Task 2.1) */}
          {(() => {
            const corrMult = signal.correlation_multiplier ?? 1.0
            const vixMult  = signal.vix_size_multiplier ?? 1.0
            const totalMult = corrMult * vixMult
            
            if (totalMult >= 1.0) return null
            
            return (
              <div className="flex items-center gap-1">
                <span className="px-2 py-0.5 rounded text-xs font-bold bg-orange-950/40 
                               text-orange-400 border border-orange-800"
                      title={`Final Size: ${Math.round(totalMult * 100)}%`}>
                  {(totalMult * 100).toFixed(0)}% SIZE
                </span>
                {corrMult < 1.0 && (
                  <span className="text-[10px] text-orange-500/80 font-bold uppercase tracking-tighter" title="Sector Exposure Cap">
                    [SEC-LOCK]
                  </span>
                )}
                {vixMult < 1.0 && (
                  <span className="text-[10px] text-red-500/80 font-bold uppercase tracking-tighter" title="Market Volatility Cap">
                    [VOL-LOCK]
                  </span>
                )}
              </div>
            )
          })()}
        </div>
        <div className="text-right">
          <div className={`text-lg font-bold ${confidenceColor}`}>
            {confidence.toFixed(0)}%
          </div>
          <div className="text-xs text-gray-500">{time}</div>
        </div>
      </div>

      {/* Price Levels */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <div className="text-center">
          <div className="text-xs text-gray-500 mb-1">Entry</div>
          <div className="text-sm font-semibold text-white">
            {entry ? `Rs ${entry.toFixed(0)}` : '--'}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500 mb-1">Stop Loss</div>
          <div className="text-sm font-semibold text-red-400">
            {signal.stop_loss ? `Rs ${signal.stop_loss.toFixed(0)}` : '--'}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500 mb-1">Target 1</div>
          <div className="text-sm font-semibold text-emerald-400">
            {signal.target_1 ? `Rs ${signal.target_1.toFixed(0)}` : '--'}
          </div>
        </div>
        <div className="text-center">
          <div className="text-xs text-gray-500 mb-1">Target 2</div>
          <div className="text-sm font-semibold text-emerald-300">
            {signal.target_2 ? `Rs ${signal.target_2.toFixed(0)}` : '--'}
          </div>
        </div>
      </div>

      {/* Risk Metrics */}
      <div className="flex items-center gap-4 mb-4 text-xs text-gray-400">
        <span>Risk: {signal.risk_percent?.toFixed(1) || '--'}%</span>
        <span>R:R = 1:{signal.risk_reward?.toFixed(1) || '--'}</span>
        <span>Mood: {signal.market_mood || '--'}</span>
      </div>

      {/* AI Agent Verdicts */}
      <div className="grid grid-cols-2 gap-2 mb-3">
        <AgentBadge agent="Bull" verdict={signal.bull_verdict} />
        <AgentBadge agent="Bear" verdict={signal.bear_verdict} />
        <AgentBadge agent="Econ" verdict={signal.econ_verdict} />
        <AgentBadge agent="Devil" verdict={signal.devil_verdict} />
      </div>

      {/* Consensus */}
      {signal.consensus && (
        <div className="text-xs text-center py-1 rounded bg-gray-800 text-gray-300">
          {signal.consensus}
        </div>
      )}

      {/* Why Approved */}
      {signal.why_approved && (
        <div className="mt-3 text-xs text-gray-400 border-t border-gray-800 pt-3">
          {signal.why_approved}
        </div>
      )}
    </div>
  )
}