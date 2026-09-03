# Supabase Schema Diff Report

**Generated:** 2026-08-25 (UTC)

Three-way reconciliation: LIVE remote schema (measured read-only via PostgREST)
vs WRITER contracts (journal payload unions + code dataclass fields).
`db/schema.sql` excluded as DDL source - it matches neither.

## trades - ALTER

- Missing writer columns (13): ['asset_class', 'candle_pattern', 'day_of_week', 'decision_price', 'risk_per_share', 'setup_hash', 'slippage_bps', 'target_1', 'target_2', 'target_3', 'time_bucket', 'timeframe', 'week_of_month']
- Live-only legacy columns left untouched (33): ['actual_rr', 'breadth_pct_entry', 'bull_confidence', 'bull_verdict', 'current_sl', 'entry_day_of_week', 'entry_time_bucket', 'entry_week_of_month', 'exit_day_of_week', 'exit_price', 'exit_reason', 'exit_time', 'gross_pnl', 'holding_days', 'mae_pct', 'market_state', 'market_state_exit', 'mfe_pct', 'mqi_level', 'net_pnl', 'nifty_level_entry', 'planned_rr', 'research_valid', 'sl_method', 'sl_stage', 'slippage', 'strategy_version', 'time_barrier_date', 'trailing_sl', 'uses_partial_exit', 'vix_at_entry', 'vix_at_exit', 'vix_rank']

## signal_intelligence_log - ALTER

- Missing writer columns (5): ['market_regime', 'metadata_json', 'sl_price', 'target_price', 'timeframe']
- Live-only legacy columns left untouched (76): ['atr_at_signal', 'breadth_pct', 'bull_concerns', 'bull_confidence', 'bull_fallback_used', 'bull_key_reasons', 'bull_model_used', 'bull_verdict', 'candle_pattern', 'candle_score', 'context_score', 'day_of_week', 'devil_all_passed', 'devil_checks_mode', 'devil_correlation', 'devil_data_quality', 'devil_event_risk', 'devil_failure_reason', 'devil_gap_risk', 'devil_liquidity', 'devil_pattern_memory', 'devil_portfolio_limits', 'devil_real_rr', 'duplicate_symbol', 'earnings_days_away', 'earnings_safe', 'ema_score', 'event_risk_flag', 'expiry_reason', 'fii_flow_cr', 'forward_return_3d', 'liquidity_score', 'macd_score', 'macro_flags', 'market_open_minutes', 'market_state', 'mqi_level', 'mtf_score', 'nifty_level', 'nifty_vs_ema200_pct', 'planned_capital', 'planned_risk_amount', 'planned_rr', 'pnl_10d', 'pnl_1d', 'pnl_20d', 'pnl_3d', 'pnl_5d', 'position_size_pct', 'real_rr_planned', 'rsi_score', 'rsi_value', 'sector', 'sector_cap_ok', 'signal_direction', 'sl_distance_pct', 'sl_method', 'stop_loss', 'strategy_version', 'supertrend_score', 'supervisor_deciding_factor', 'supervisor_decision', 'supervisor_model_used', 'supervisor_reason', 'swing_low_used', 'system_mode', 'target', 'target_distance_pct', 'technical_score', 'time_of_day_bucket', 'trade_id', 'vix_at_signal', 'vix_rank', 'volatility_score', 'was_executed', 'week_of_month']

## pattern_memory - ALTER

- Missing writer columns (4): ['breakevens', 'expectancy_rr', 'laplace_win_rate', 'profit_factor']

## daily_portfolio_snapshot - ALTER

- Missing writer columns (7): ['capital_free', 'closed_trades_today', 'high_water_mark', 'loss_trades_today', 'open_positions', 'realised_pnl', 'win_trades_today']
- Live-only legacy columns left untouched (29): ['capital_cash', 'consecutive_losses', 'consecutive_wins', 'cumulative_return_pct', 'daily_return_pct', 'data_points_available', 'deployment_pct', 'drawdown_from_peak', 'losses_today', 'mqi_level', 'nifty_close', 'nifty_return_today', 'open_trades_count', 'peak_equity', 'realised_pnl_today', 'sharpe_rolling_30', 'signals_approved', 'signals_expired', 'signals_generated', 'signals_rejected', 'total_pnl_today', 'total_tax_today', 'trades_closed_today', 'trades_opened_today', 'vix', 'vix_rank', 'win_rate_last_10', 'win_rate_last_30', 'wins_today']

## intraday_portfolio_snapshot - CREATE

- NEW TABLE (writers currently fail silently against it).
- Columns created: ['cash_available', 'checkpoint_time', 'created_at', 'current_equity', 'drawdown_pct', 'kill_line_triggered', 'margin_utilized', 'open_positions_count', 'realized_pnl', 'system_mode', 'unrealized_pnl']

## market_state_history - ALTER

- Missing writer columns (3): ['data_quality', 'ema20', 'session_phase']
- Live-only legacy columns left untouched (2): ['breadth_pct', 'fii_net_cr']

## agent_weight_log - ALTER

- Missing writer columns (9): ['accuracy_pct', 'agent_name', 'new_weight', 'old_weight', 'recalibrated_at', 'system_mode', 'trades_evaluated', 'trigger_reason', 'weight_change']

## strategy_performance - ALTER

- Missing writer columns (19): ['avg_rr', 'calmar_ratio', 'last_computed_at', 'losses', 'market_state', 'max_drawdown_pct', 'mqi_level', 'net_pnl', 'period_end', 'period_start', 'profit_factor', 'sharpe_ratio', 'strategy_id', 'strategy_version', 'system_mode', 'total_trades', 'updated_at', 'win_rate', 'wins']

## risk_events - ALTER

- Missing writer columns (2): ['level', 'system_mode']

## system_log - ALTER

- Missing writer columns (1): ['system_mode']
