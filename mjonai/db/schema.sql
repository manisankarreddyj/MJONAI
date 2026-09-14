-- MJONAI SUPABASE DDL — REGENERATED 2026-09-14 FROM WRITER PAYLOADS
-- Source of truth: mjonai/db/*.py dataclasses, _KNOWN_SIGNAL_COLUMNS, _MARKET_STATE_COLUMNS
--                  and insert/update/upsert payload builders.
-- Live DB may contain migration-added supplementary columns not listed here.
-- NEVER execute this DDL against live Supabase.
-- Static drift guard: tests/test_schema_drift.py

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════════════════════════════════════════════════
-- trades
-- Writer: TradeRecord (dataclass) + insert_trade + close_trade + cancel_trade
-- Columns: all TradeRecord fields (including stt_tax) + id (Supabase-generated) +
--          stt (close_trade UPDATE column, not in dataclass).
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price NUMERIC(12,4),
    initial_sl NUMERIC(12,4),
    current_sl NUMERIC(12,4),
    trailing_sl NUMERIC(12,4),
    sl_stage TEXT DEFAULT 'INITIAL',
    target_price NUMERIC(12,4),
    quantity INTEGER,
    quantity_remaining INTEGER,
    strategy_id TEXT,
    signal_id TEXT,
    asset_class TEXT DEFAULT 'EQUITY',
    decision_price NUMERIC(12,4),
    slippage_bps NUMERIC(8,2),
    uses_partial_exit BOOLEAN DEFAULT TRUE,
    status TEXT DEFAULT 'OPEN',
    system_mode TEXT DEFAULT 'RESEARCH',
    exit_price NUMERIC(12,4),
    gross_pnl NUMERIC(14,4),
    net_pnl NUMERIC(14,4),
    stt_tax NUMERIC(12,4),
    stt NUMERIC(12,4),
    exchange_turnover_fee NUMERIC(12,4),
    brokerage NUMERIC(12,4),
    exit_reason TEXT,
    actual_rr NUMERIC(8,4),
    price_low_since_entry NUMERIC(12,4),
    price_high_since_entry NUMERIC(12,4),
    mae_pct NUMERIC(8,4),
    mfe_pct NUMERIC(8,4),
    giveback_pct NUMERIC(8,4),
    entry_time TEXT,
    exit_time TEXT,
    created_at TEXT,
    updated_at TEXT,
    research_valid BOOLEAN DEFAULT TRUE,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- trade_tranches
-- Writer: TrancheRecord (dataclass) + insert_trade_tranches + close_tranche
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS trade_tranches (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trade_id TEXT NOT NULL,
    tranche_number INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    target_price NUMERIC(12,4),
    target_rr NUMERIC(8,4),
    status TEXT DEFAULT 'OPEN',
    exit_price NUMERIC(12,4),
    gross_pnl NUMERIC(14,4),
    net_pnl NUMERIC(14,4),
    exit_time TEXT,
    updated_at TEXT,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- signals (LEGACY)
-- Writer: pipeline.py:899 caller payload (pass-through insert_signal)
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol TEXT,
    signal_type TEXT,
    entry_price NUMERIC(12,4),
    stop_loss NUMERIC(12,4),
    target NUMERIC(12,4),
    confidence NUMERIC(6,4),
    timeframe TEXT,
    market_state TEXT,
    mqi_level TEXT,
    status TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- signal_intelligence_log
-- Writer: _KNOWN_SIGNAL_COLUMNS whitelist (signals.py:189-212) — THE contract
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS signal_intelligence_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    is_deleted BOOLEAN DEFAULT FALSE,
    strategy_id TEXT,
    strategy_version TEXT,
    symbol TEXT,
    sector TEXT,
    signal_type TEXT,
    system_mode TEXT DEFAULT 'RESEARCH',
    generated_at TIMESTAMPTZ,
    market_open_minutes INTEGER,
    time_of_day_bucket TEXT,
    day_of_week TEXT,
    week_of_month TEXT,
    market_state TEXT,
    mqi_level TEXT,
    mqi_score NUMERIC,
    vix_at_signal NUMERIC,
    vix_rank NUMERIC,
    nifty_level NUMERIC,
    nifty_vs_ema200_pct NUMERIC,
    breadth_pct NUMERIC,
    fii_flow_cr NUMERIC,
    macro_flags TEXT,
    technical_score NUMERIC,
    rsi_value NUMERIC,
    rsi_score NUMERIC,
    macd_score NUMERIC,
    ema_score NUMERIC,
    supertrend_score NUMERIC,
    candle_score NUMERIC,
    candle_pattern TEXT,
    mtf_score NUMERIC,
    volatility_score NUMERIC,
    liquidity_score NUMERIC,
    context_score NUMERIC,
    final_confidence NUMERIC,
    entry_price NUMERIC,
    stop_loss NUMERIC,
    target NUMERIC,
    sl_method TEXT,
    swing_low_used NUMERIC,
    atr_at_signal NUMERIC,
    sl_distance_pct NUMERIC,
    target_distance_pct NUMERIC,
    planned_rr NUMERIC,
    real_rr_planned NUMERIC,
    planned_quantity INTEGER,
    planned_capital NUMERIC,
    planned_risk_amount NUMERIC,
    position_size_pct NUMERIC,
    devil_gap_risk NUMERIC,
    devil_liquidity NUMERIC,
    devil_data_quality NUMERIC,
    devil_pattern_memory NUMERIC,
    devil_correlation NUMERIC,
    devil_real_rr NUMERIC,
    devil_portfolio_limits NUMERIC,
    devil_event_risk NUMERIC,
    devil_all_passed BOOLEAN,
    devil_failure_reason TEXT,
    devil_checks_mode TEXT,
    earnings_safe BOOLEAN,
    earnings_days_away INTEGER,
    sector_cap_ok BOOLEAN,
    duplicate_symbol BOOLEAN,
    event_risk_flag BOOLEAN,
    bull_verdict TEXT,
    bull_confidence NUMERIC,
    bull_key_reasons TEXT[],
    bull_concerns TEXT[],
    bull_model_used TEXT,
    bull_fallback_used BOOLEAN,
    supervisor_decision TEXT,
    supervisor_reason TEXT,
    supervisor_deciding_factor TEXT,
    supervisor_model_used TEXT,
    was_executed BOOLEAN DEFAULT FALSE,
    trade_id TEXT,
    expiry_reason TEXT,
    actual_outcome TEXT,
    actual_rr NUMERIC,
    actual_pnl_gross NUMERIC,
    actual_pnl_net NUMERIC,
    holding_days INTEGER,
    exit_reason TEXT,
    forward_return_1d NUMERIC,
    forward_return_3d NUMERIC,
    forward_return_5d NUMERIC,
    forward_return_10d NUMERIC,
    forward_return_20d NUMERIC,
    pnl_1d NUMERIC,
    pnl_3d NUMERIC,
    pnl_5d NUMERIC,
    pnl_10d NUMERIC,
    pnl_20d NUMERIC,
    raw_signal_value NUMERIC,
    signal_direction TEXT,
    market_regime TEXT,
    metadata_json JSONB,
    sl_price NUMERIC,
    target_price NUMERIC,
    timeframe TEXT
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- agent_logs
-- Writer: AgentLogRecord (dataclass) + insert_agent_log runtime adds (called_at, updated_at)
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS agent_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name TEXT NOT NULL,
    signal_id TEXT,
    raw_verdict TEXT,
    confidence_given NUMERIC,
    key_reasons TEXT[],
    concerns TEXT[],
    full_response TEXT,
    latency_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    agent_model TEXT DEFAULT 'gpt-4o',
    fallback_used BOOLEAN DEFAULT FALSE,
    system_mode TEXT DEFAULT 'RESEARCH',
    called_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    actual_outcome TEXT,
    actual_rr NUMERIC,
    was_correct BOOLEAN
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- pattern_memory
-- Writer: PatternMemoryRecord (dataclass) + upsert_pattern runtime adds
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS pattern_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    setup_hash TEXT NOT NULL UNIQUE,
    symbol TEXT,
    strategy_id TEXT,
    sl_method TEXT DEFAULT 'STRUCTURE',
    market_state TEXT DEFAULT 'NEUTRAL',
    vix_range TEXT DEFAULT 'NORMAL',
    candle_pattern TEXT DEFAULT 'NONE',
    occurrences INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    breakevens INTEGER DEFAULT 0,
    win_rate NUMERIC,
    laplace_win_rate NUMERIC,
    avg_rr_achieved NUMERIC,
    expectancy_rr NUMERIC,
    profit_factor NUMERIC,
    last_10_outcomes TEXT[],
    last_outcome TEXT,
    is_quarantined BOOLEAN DEFAULT FALSE,
    is_deleted BOOLEAN DEFAULT FALSE,
    system_mode TEXT DEFAULT 'RESEARCH',
    first_seen TEXT,
    last_seen TEXT,
    updated_at TEXT
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- daily_portfolio_snapshot
-- Writer: PortfolioSnapshot (dataclass) + upsert_daily_snapshot
-- NOTE: writer excludes cash_balance, margin_used, daily_pnl from DB writes.
-- Live DB also has migration-added columns (capital_free, closed_trades_today,
-- high_water_mark, loss_trades_today, realised_pnl, win_trades_today) not used by writers.
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS daily_portfolio_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    snapshot_date TEXT NOT NULL,
    capital_total NUMERIC,
    cash_balance NUMERIC,
    margin_used NUMERIC,
    daily_pnl NUMERIC,
    daily_pnl_pct NUMERIC,
    unrealized_pnl NUMERIC,
    peak_equity NUMERIC,
    drawdown_pct NUMERIC,
    open_positions INTEGER,
    closed_trades INTEGER,
    win_count INTEGER,
    loss_count INTEGER,
    system_mode TEXT DEFAULT 'RESEARCH',
    metrics_json JSONB,
    updated_at TEXT
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- intraday_portfolio_snapshot
-- Writer: IntradaySnapshotRecord (dataclass) + upsert_intraday_snapshot
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS intraday_portfolio_snapshot (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    checkpoint_time TEXT,
    current_equity NUMERIC,
    cash_available NUMERIC,
    margin_utilized NUMERIC,
    unrealized_pnl NUMERIC,
    realized_pnl NUMERIC,
    open_positions_count INTEGER,
    drawdown_pct NUMERIC,
    kill_line_triggered BOOLEAN DEFAULT FALSE,
    system_mode TEXT DEFAULT 'RESEARCH'
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- market_state_history
-- Writer: _MARKET_STATE_COLUMNS whitelist (snapshots.py:376-381)
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS market_state_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date TEXT NOT NULL,
    nifty_price NUMERIC,
    ema200 NUMERIC,
    price_structure TEXT,
    breadth_pct NUMERIC,
    breadth_score NUMERIC,
    vix NUMERIC,
    vix_score NUMERIC,
    fii_net_cr NUMERIC,
    fii_score NUMERIC,
    total_score NUMERIC,
    market_state TEXT,
    mqi_score NUMERIC,
    mqi_level TEXT,
    no_trade_day BOOLEAN DEFAULT FALSE,
    high_vol_override BOOLEAN DEFAULT FALSE,
    data_quality TEXT,
    ema20 NUMERIC,
    session_phase TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- scan_log
-- Writer: ScanLogRecord (dataclass) + insert_scan_log runtime add (scanned_at)
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS scan_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbols_scanned INTEGER,
    signals_generated INTEGER,
    signals_approved INTEGER,
    scan_duration_ms NUMERIC,
    timeframe TEXT DEFAULT '15m',
    asset_class TEXT DEFAULT 'EQUITY',
    system_mode TEXT DEFAULT 'RESEARCH',
    passed_liquidity INTEGER DEFAULT 0,
    passed_earnings INTEGER DEFAULT 0,
    passed_breadth INTEGER DEFAULT 0,
    passed_pattern_memory INTEGER DEFAULT 0,
    scanned_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- system_health_log
-- Writer: SystemHealthRecord (dataclass) + insert_health_log runtime add (logged_at)
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS system_health_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    oracle_cpu_pct NUMERIC,
    oracle_ram_pct NUMERIC,
    oracle_disk_pct NUMERIC,
    websocket_healthy BOOLEAN,
    internet_ok BOOLEAN,
    groq_latency_ms NUMERIC,
    gemini_latency_ms NUMERIC,
    supabase_latency_ms NUMERIC,
    angelone_latency_ms NUMERIC,
    system_mode TEXT DEFAULT 'RESEARCH',
    logged_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- strategy_performance
-- Writer: StrategyPerformanceRecord (dataclass) + upsert_strategy_performance
-- UNIQUE: strategy_id, strategy_version, period_start, period_end, market_state, mqi_level, system_mode
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS strategy_performance (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    strategy_id TEXT NOT NULL,
    strategy_version TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    market_state TEXT DEFAULT 'ALL',
    mqi_level TEXT DEFAULT 'ALL',
    system_mode TEXT DEFAULT 'RESEARCH',
    total_trades INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate NUMERIC,
    profit_factor NUMERIC,
    sharpe_ratio NUMERIC,
    max_drawdown_pct NUMERIC,
    calmar_ratio NUMERIC,
    avg_rr NUMERIC,
    net_pnl NUMERIC,
    last_computed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- agent_weight_log
-- Writer: AgentWeightRecord (dataclass) + insert_weight_log
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS agent_weight_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name TEXT NOT NULL,
    old_weight NUMERIC,
    new_weight NUMERIC,
    weight_change NUMERIC,
    trigger_reason TEXT DEFAULT 'PERIODIC_EVALUATION',
    accuracy_pct NUMERIC,
    trades_evaluated INTEGER DEFAULT 0,
    system_mode TEXT DEFAULT 'RESEARCH',
    recalibrated_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- risk_events
-- Writer: insert_risk_event (inline dict)
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS risk_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type TEXT,
    message TEXT,
    level TEXT DEFAULT 'INFO',
    system_mode TEXT DEFAULT 'RESEARCH',
    triggered_at TIMESTAMPTZ
);

-- ═══════════════════════════════════════════════════════════════════════════════
-- system_log
-- Writer: insert_system_log (inline dict)
-- ═══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS system_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type TEXT,
    message TEXT,
    level TEXT DEFAULT 'INFO',
    system_mode TEXT DEFAULT 'RESEARCH',
    created_at TIMESTAMPTZ
);

-- END OF DDL — regenerated 2026-09-14, never execute against live.

-- ═══════════════════════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY (canonical source: mjonai/db/rls.py — owner-approved
-- Decision 3 Option B, 2026-09-14). Deny-by-default to the public anon JWT;
-- the backend authenticates with service_role (BYPASSRLS).
-- Apply via tools/scripts/apply_supabase_rls.py AFTER SUPABASE_SERVICE_ROLE_KEY
-- is configured. Do not paste this block into the live SQL editor piecemeal.
-- ═══════════════════════════════════════════════════════════════════════════════
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE trades FORCE ROW LEVEL SECURITY;

ALTER TABLE trade_tranches ENABLE ROW LEVEL SECURITY;
ALTER TABLE trade_tranches FORCE ROW LEVEL SECURITY;

ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE signals FORCE ROW LEVEL SECURITY;

ALTER TABLE signal_intelligence_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_intelligence_log FORCE ROW LEVEL SECURITY;

ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs FORCE ROW LEVEL SECURITY;

ALTER TABLE pattern_memory ENABLE ROW LEVEL SECURITY;
ALTER TABLE pattern_memory FORCE ROW LEVEL SECURITY;

ALTER TABLE daily_portfolio_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_portfolio_snapshot FORCE ROW LEVEL SECURITY;

ALTER TABLE intraday_portfolio_snapshot ENABLE ROW LEVEL SECURITY;
ALTER TABLE intraday_portfolio_snapshot FORCE ROW LEVEL SECURITY;

ALTER TABLE market_state_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE market_state_history FORCE ROW LEVEL SECURITY;

ALTER TABLE scan_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_log FORCE ROW LEVEL SECURITY;

ALTER TABLE system_health_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_health_log FORCE ROW LEVEL SECURITY;

ALTER TABLE strategy_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE strategy_performance FORCE ROW LEVEL SECURITY;

ALTER TABLE agent_weight_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_weight_log FORCE ROW LEVEL SECURITY;

ALTER TABLE risk_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_events FORCE ROW LEVEL SECURITY;

ALTER TABLE system_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_log FORCE ROW LEVEL SECURITY;
