-- =============================================================================
-- MJONAI MASTER SUPABASE DATABASE SCHEMA DDL
-- Purpose: Complete, production-ready schema for all 15 tables with indexes,
--          foreign keys, unique constraints, and multi-asset support.
-- =============================================================================

-- Enable UUID extension if not enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 1. TRADING & EXECUTION LEDGER
-- =============================================================================

-- Master Parent Trades Table
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(64) NOT NULL,
    direction VARCHAR(8) NOT NULL DEFAULT 'BUY',
    entry_price NUMERIC(12, 4) NOT NULL,
    decision_price NUMERIC(12, 4),
    slippage_bps NUMERIC(8, 2) DEFAULT 0.0,
    initial_sl NUMERIC(12, 4) NOT NULL,
    current_sl NUMERIC(12, 4) NOT NULL,
    trailing_sl NUMERIC(12, 4),
    sl_stage VARCHAR(32) NOT NULL DEFAULT 'INITIAL',
    target_price NUMERIC(12, 4) NOT NULL,
    quantity INTEGER NOT NULL,
    quantity_remaining INTEGER,
    strategy_id VARCHAR(64) NOT NULL,
    signal_id UUID,
    asset_class VARCHAR(32) NOT NULL DEFAULT 'EQUITY',
    uses_partial_exit BOOLEAN DEFAULT TRUE,
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    -- Exit & P&L Attribution
    exit_price NUMERIC(12, 4),
    gross_pnl NUMERIC(14, 4),
    net_pnl NUMERIC(14, 4),
    stt_tax NUMERIC(10, 4),
    exchange_turnover_fee NUMERIC(10, 4),
    brokerage NUMERIC(10, 4),
    exit_reason VARCHAR(64),
    actual_rr NUMERIC(8, 2),
    -- Excursion Analytics
    price_low_since_entry NUMERIC(12, 4),
    price_high_since_entry NUMERIC(12, 4),
    mae_pct NUMERIC(8, 2),
    mfe_pct NUMERIC(8, 2),
    giveback_pct NUMERIC(8, 2),
    -- Research Fields
    market_state VARCHAR(32),
    mqi_level VARCHAR(32),
    vix_at_entry NUMERIC(8, 2),
    sector VARCHAR(64),
    research_valid BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE,
    -- Timestamps
    entry_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trades_status_mode ON trades(status, system_mode);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_mode ON trades(symbol, system_mode);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_exit_time ON trades(exit_time DESC);

-- Child Tranches Table (3-Tranche Scaling)
CREATE TABLE IF NOT EXISTS trade_tranches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id UUID NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    tranche_number INTEGER NOT NULL DEFAULT 1,
    quantity INTEGER NOT NULL,
    target_price NUMERIC(12, 4),
    target_rr NUMERIC(8, 2),
    status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
    exit_price NUMERIC(12, 4),
    gross_pnl NUMERIC(14, 4),
    net_pnl NUMERIC(14, 4),
    exit_time TIMESTAMPTZ,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tranches_trade_id ON trade_tranches(trade_id);
CREATE INDEX IF NOT EXISTS idx_tranches_status ON trade_tranches(status);


-- =============================================================================
-- 2. SIGNALS & FACTOR INTELLIGENCE
-- =============================================================================

CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(64) NOT NULL,
    direction VARCHAR(8) NOT NULL DEFAULT 'BUY',
    strategy_id VARCHAR(64) NOT NULL,
    setup_name VARCHAR(64),
    entry_price NUMERIC(12, 4) NOT NULL,
    sl_price NUMERIC(12, 4) NOT NULL,
    target_price NUMERIC(12, 4) NOT NULL,
    confidence NUMERIC(6, 4) DEFAULT 0.5,
    market_state VARCHAR(32) DEFAULT 'NEUTRAL',
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_created_at ON signals(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol);

CREATE TABLE IF NOT EXISTS signal_intelligence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    signal_id UUID NOT NULL,
    symbol VARCHAR(64) NOT NULL,
    strategy_id VARCHAR(64) NOT NULL,
    market_state VARCHAR(32) DEFAULT 'NEUTRAL',
    mqi_score INTEGER DEFAULT 50,
    rvol_score NUMERIC(8, 2),
    sector_breadth_score NUMERIC(8, 2),
    vix_value NUMERIC(8, 2),
    final_verdict VARCHAR(32) DEFAULT 'APPROVE',
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    forward_return_1d NUMERIC(8, 4),
    forward_return_5d NUMERIC(8, 4),
    forward_return_20d NUMERIC(8, 4),
    forward_returns_computed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sig_intel_signal_id ON signal_intelligence(signal_id);
CREATE INDEX IF NOT EXISTS idx_sig_intel_created_at ON signal_intelligence(created_at DESC);


-- =============================================================================
-- 3. REASONING, PATTERN MEMORY & AI AGENT GOVERNANCE
-- =============================================================================

CREATE TABLE IF NOT EXISTS patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    setup_hash VARCHAR(128) NOT NULL,
    strategy_id VARCHAR(64) NOT NULL,
    market_state VARCHAR(32) NOT NULL DEFAULT 'ALL',
    timeframe VARCHAR(16) NOT NULL DEFAULT '15m',
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    occurrences INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    win_rate_pct NUMERIC(6, 2) DEFAULT 50.0,
    laplace_win_rate_pct NUMERIC(6, 2) DEFAULT 50.0,
    expectancy NUMERIC(8, 4) DEFAULT 0.0,
    profit_factor NUMERIC(8, 2),
    consecutive_losses INTEGER NOT NULL DEFAULT 0,
    is_quarantined BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    last_occurred_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_pattern_hash_mode UNIQUE (setup_hash, system_mode)
);

CREATE INDEX IF NOT EXISTS idx_patterns_lookup ON patterns(setup_hash, system_mode);

CREATE TABLE IF NOT EXISTS agent_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name VARCHAR(64) NOT NULL,
    signal_id UUID,
    raw_verdict VARCHAR(64) NOT NULL,
    confidence_given NUMERIC(6, 4) NOT NULL DEFAULT 0.5,
    key_reasons JSONB,
    concerns JSONB,
    latency_ms NUMERIC(10, 2),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    was_correct BOOLEAN,
    actual_rr NUMERIC(8, 2),
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    called_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_logs_mode_called ON agent_logs(system_mode, called_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_logs_signal ON agent_logs(signal_id);

CREATE TABLE IF NOT EXISTS agent_weight_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name VARCHAR(64) NOT NULL,
    old_weight NUMERIC(6, 4) NOT NULL,
    new_weight NUMERIC(6, 4) NOT NULL,
    weight_change NUMERIC(6, 4) NOT NULL DEFAULT 0.0,
    trigger_reason VARCHAR(128) DEFAULT 'PERIODIC_EVALUATION',
    accuracy_pct NUMERIC(6, 2),
    trades_evaluated INTEGER DEFAULT 0,
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    recalibrated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_weight_log ON agent_weight_log(agent_name, system_mode, recalibrated_at DESC);


-- =============================================================================
-- 4. PORTFOLIO & MARKET STATE SNAPSHOTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS daily_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_date DATE NOT NULL,
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    peak_equity NUMERIC(14, 4) NOT NULL,
    current_equity NUMERIC(14, 4) NOT NULL,
    drawdown_pct NUMERIC(8, 4) NOT NULL DEFAULT 0.0,
    realized_pnl_today NUMERIC(14, 4) DEFAULT 0.0,
    unrealized_pnl NUMERIC(14, 4) DEFAULT 0.0,
    total_trades_today INTEGER DEFAULT 0,
    winning_trades_today INTEGER DEFAULT 0,
    losing_trades_today INTEGER DEFAULT 0,
    kill_line_breached BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_daily_snapshot UNIQUE (snapshot_date, system_mode)
);

CREATE INDEX IF NOT EXISTS idx_daily_snapshots_date ON daily_snapshots(snapshot_date DESC, system_mode);

CREATE TABLE IF NOT EXISTS intraday_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    current_equity NUMERIC(14, 4) NOT NULL,
    drawdown_pct NUMERIC(8, 4) NOT NULL DEFAULT 0.0,
    open_positions_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_intraday_snapshots_time ON intraday_snapshots(snapshot_time DESC, system_mode);

CREATE TABLE IF NOT EXISTS market_state_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    market_state VARCHAR(32) NOT NULL DEFAULT 'NEUTRAL',
    vix_regime VARCHAR(32) DEFAULT 'NORMAL',
    mqi_score INTEGER DEFAULT 50,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_market_state_snapshots_time ON market_state_snapshots(snapshot_time DESC);


-- =============================================================================
-- 5. SYSTEM MISSION CONTROL, HEALTH & AUDIT
-- =============================================================================

CREATE TABLE IF NOT EXISTS scan_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbols_scanned INTEGER NOT NULL DEFAULT 0,
    signals_generated INTEGER NOT NULL DEFAULT 0,
    signals_approved INTEGER NOT NULL DEFAULT 0,
    scan_duration_ms NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    timeframe VARCHAR(16) NOT NULL DEFAULT '15m',
    asset_class VARCHAR(32) NOT NULL DEFAULT 'EQUITY',
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    scanned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scan_log_scanned_at ON scan_log(scanned_at DESC, system_mode);

CREATE TABLE IF NOT EXISTS system_health_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    oracle_cpu_pct NUMERIC(6, 2),
    oracle_ram_pct NUMERIC(6, 2),
    oracle_disk_pct NUMERIC(6, 2),
    websocket_healthy BOOLEAN DEFAULT TRUE,
    internet_ok BOOLEAN DEFAULT TRUE,
    groq_latency_ms NUMERIC(10, 2),
    gemini_latency_ms NUMERIC(10, 2),
    supabase_latency_ms NUMERIC(10, 2),
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_health_log_logged_at ON system_health_log(logged_at DESC);

CREATE TABLE IF NOT EXISTS strategy_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id VARCHAR(64) NOT NULL,
    strategy_version VARCHAR(32) NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    market_state VARCHAR(32) NOT NULL DEFAULT 'ALL',
    mqi_level VARCHAR(32) NOT NULL DEFAULT 'ALL',
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    total_trades INTEGER NOT NULL DEFAULT 0,
    wins INTEGER NOT NULL DEFAULT 0,
    losses INTEGER NOT NULL DEFAULT 0,
    win_rate NUMERIC(6, 2),
    profit_factor NUMERIC(8, 2),
    sharpe_ratio NUMERIC(8, 4),
    max_drawdown_pct NUMERIC(8, 4),
    calmar_ratio NUMERIC(8, 4),
    avg_rr NUMERIC(8, 2),
    net_pnl NUMERIC(14, 4),
    last_computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_strat_perf UNIQUE (
        strategy_id, strategy_version, period_start, period_end, market_state, mqi_level, system_mode
    )
);

CREATE INDEX IF NOT EXISTS idx_strat_perf ON strategy_performance(strategy_id, system_mode, win_rate DESC);

CREATE TABLE IF NOT EXISTS risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(64) NOT NULL,
    message TEXT NOT NULL,
    level VARCHAR(32) NOT NULL DEFAULT 'WARNING',
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    triggered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_risk_events_triggered ON risk_events(triggered_at DESC);

CREATE TABLE IF NOT EXISTS system_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(64) NOT NULL,
    message TEXT NOT NULL,
    level VARCHAR(32) NOT NULL DEFAULT 'INFO',
    system_mode VARCHAR(32) NOT NULL DEFAULT 'RESEARCH',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_log_created_at ON system_log(created_at DESC);


-- =============================================================================
-- 6. SAFE NON-DESTRUCTIVE MIGRATIONS FOR EXISTING DATABASES
-- Purpose: Ensures existing databases seamlessly receive all new SOTA columns
--          and indexes without modifying, locking, or deleting existing rows.
-- =============================================================================

-- Trades Enhancements (Slippage, Excursions, Taxes)
ALTER TABLE trades ADD COLUMN IF NOT EXISTS slippage_bps NUMERIC(8, 2) DEFAULT 0.0;
ALTER TABLE trades ADD COLUMN IF NOT EXISTS decision_price NUMERIC(12, 4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS giveback_pct NUMERIC(8, 2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS mae_pct NUMERIC(8, 2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS mfe_pct NUMERIC(8, 2);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS stt_tax NUMERIC(10, 4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS exchange_turnover_fee NUMERIC(10, 4);
ALTER TABLE trades ADD COLUMN IF NOT EXISTS brokerage NUMERIC(10, 4);

-- Patterns Enhancements (Bayesian Laplace & Mathematical Expectancy)
ALTER TABLE patterns ADD COLUMN IF NOT EXISTS laplace_win_rate_pct NUMERIC(6, 2) DEFAULT 50.0;
ALTER TABLE patterns ADD COLUMN IF NOT EXISTS expectancy NUMERIC(8, 4) DEFAULT 0.0;
ALTER TABLE patterns ADD COLUMN IF NOT EXISTS profit_factor NUMERIC(8, 2);
ALTER TABLE patterns ADD COLUMN IF NOT EXISTS is_quarantined BOOLEAN NOT NULL DEFAULT FALSE;

-- AI Agent Logs Enhancements (Token Cost Telemetry & Latency)
ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER;
ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS completion_tokens INTEGER;
ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS latency_ms NUMERIC(10, 2);
ALTER TABLE agent_logs ADD COLUMN IF NOT EXISTS actual_rr NUMERIC(8, 2);

-- System Scan Funnel Enhancements (Multi-Timeframe & Multi-Asset)
ALTER TABLE scan_log ADD COLUMN IF NOT EXISTS timeframe VARCHAR(16) DEFAULT '15m';
ALTER TABLE scan_log ADD COLUMN IF NOT EXISTS asset_class VARCHAR(32) DEFAULT 'EQUITY';
ALTER TABLE scan_log ADD COLUMN IF NOT EXISTS system_mode VARCHAR(32) DEFAULT 'RESEARCH';

