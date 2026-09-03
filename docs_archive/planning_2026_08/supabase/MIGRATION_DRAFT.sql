-- MJONAI SUPABASE MIGRATION DRAFT (auto-generated 2026-08-25)
-- Base: ACTUAL WRITER payloads (runtime journals + code dataclass contracts).
-- db/schema.sql was NOT used as column source (stale third generation:
-- initial_sl/target_price/stt_tax names match neither live DB nor writers).
-- Additive-only: CREATE + ADD COLUMN IF NOT EXISTS. No drops, no renames, no data changes.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- trades: writer-required columns missing in live
ALTER TABLE trades ADD COLUMN IF NOT EXISTS asset_class TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS candle_pattern TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS day_of_week TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS decision_price NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS risk_per_share NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS setup_hash TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS slippage_bps NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS target_1 NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS target_2 NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS target_3 NUMERIC;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS time_bucket TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS timeframe TEXT;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS week_of_month TEXT;
-- signal_intelligence_log: writer-required columns missing in live
ALTER TABLE signal_intelligence_log ADD COLUMN IF NOT EXISTS market_regime TEXT;
ALTER TABLE signal_intelligence_log ADD COLUMN IF NOT EXISTS metadata_json JSONB;
ALTER TABLE signal_intelligence_log ADD COLUMN IF NOT EXISTS sl_price NUMERIC;
ALTER TABLE signal_intelligence_log ADD COLUMN IF NOT EXISTS target_price NUMERIC;
ALTER TABLE signal_intelligence_log ADD COLUMN IF NOT EXISTS timeframe TEXT;
-- pattern_memory: writer-required columns missing in live
ALTER TABLE pattern_memory ADD COLUMN IF NOT EXISTS breakevens INTEGER;
ALTER TABLE pattern_memory ADD COLUMN IF NOT EXISTS expectancy_rr NUMERIC;
ALTER TABLE pattern_memory ADD COLUMN IF NOT EXISTS laplace_win_rate NUMERIC;
ALTER TABLE pattern_memory ADD COLUMN IF NOT EXISTS profit_factor NUMERIC;
-- daily_portfolio_snapshot: writer-required columns missing in live
ALTER TABLE daily_portfolio_snapshot ADD COLUMN IF NOT EXISTS capital_free NUMERIC;
ALTER TABLE daily_portfolio_snapshot ADD COLUMN IF NOT EXISTS closed_trades_today INTEGER;
ALTER TABLE daily_portfolio_snapshot ADD COLUMN IF NOT EXISTS high_water_mark NUMERIC;
ALTER TABLE daily_portfolio_snapshot ADD COLUMN IF NOT EXISTS loss_trades_today INTEGER;
ALTER TABLE daily_portfolio_snapshot ADD COLUMN IF NOT EXISTS open_positions INTEGER;
ALTER TABLE daily_portfolio_snapshot ADD COLUMN IF NOT EXISTS realised_pnl NUMERIC;
ALTER TABLE daily_portfolio_snapshot ADD COLUMN IF NOT EXISTS win_trades_today INTEGER;
CREATE TABLE IF NOT EXISTS intraday_portfolio_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cash_available NUMERIC,
    checkpoint_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    current_equity NUMERIC,
    drawdown_pct NUMERIC,
    kill_line_triggered BOOLEAN,
    margin_utilized NUMERIC,
    open_positions_count INTEGER,
    realized_pnl NUMERIC,
    system_mode TEXT,
    unrealized_pnl NUMERIC,
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_intraday_portfolio_snapshot_checkpoint ON intraday_portfolio_snapshot(checkpoint_time DESC);
-- market_state_history: writer-required columns missing in live
ALTER TABLE market_state_history ADD COLUMN IF NOT EXISTS data_quality TEXT;
ALTER TABLE market_state_history ADD COLUMN IF NOT EXISTS ema20 NUMERIC;
ALTER TABLE market_state_history ADD COLUMN IF NOT EXISTS session_phase TEXT;
-- agent_weight_log: writer-required columns missing in live
ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS accuracy_pct NUMERIC;
ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS agent_name TEXT;
ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS new_weight NUMERIC;
ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS old_weight NUMERIC;
ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS recalibrated_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS system_mode TEXT DEFAULT 'RESEARCH';
ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS trades_evaluated INTEGER;
ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS trigger_reason TEXT;
ALTER TABLE agent_weight_log ADD COLUMN IF NOT EXISTS weight_change NUMERIC;
-- strategy_performance: writer-required columns missing in live
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS avg_rr NUMERIC;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS calmar_ratio NUMERIC;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS last_computed_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS losses INTEGER;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS market_state TEXT;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS max_drawdown_pct NUMERIC;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS mqi_level TEXT;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS net_pnl NUMERIC;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS period_end DATE;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS period_start DATE;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS profit_factor NUMERIC;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS sharpe_ratio NUMERIC;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS strategy_id TEXT;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS strategy_version TEXT;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS system_mode TEXT DEFAULT 'RESEARCH';
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS total_trades INTEGER;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS win_rate NUMERIC;
ALTER TABLE strategy_performance ADD COLUMN IF NOT EXISTS wins INTEGER;
-- risk_events: writer-required columns missing in live
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS level TEXT;
ALTER TABLE risk_events ADD COLUMN IF NOT EXISTS system_mode TEXT DEFAULT 'RESEARCH';
-- system_log: writer-required columns missing in live
ALTER TABLE system_log ADD COLUMN IF NOT EXISTS system_mode TEXT DEFAULT 'RESEARCH';

-- END OF MIGRATION DRAFT - review before applying.