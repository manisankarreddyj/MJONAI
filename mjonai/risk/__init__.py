"""
Package: risk
Purpose: Elite Multi-Tier Institutional Quantitative Risk & Capital Preservation Engine.

Modules:
  - behavioral_guard: Psychological discipline sentry, progressive cooldowns, and symbol lockouts.
  - devil_checks: 8 deterministic mathematical veto checks run before any LLM execution.
  - emergency_triggers: 15% Lifetime Kill Line, 3% Daily Risk Stop, Soft Stop, and Flash Crash sentries.
  - gap_risk: Directional GARCH volatility modeling, overnight gap distributions, and weekend scaling.
  - special_modes: Crisis mode, Union Budget speech blackout, and dynamic holiday-aware expiry modes.
  - trade_risk: Fractal structure stops, multi-factor position sizing, 3-tranche scaling, and tax deductions.
"""

# Behavioral Psychology Guard
from mjonai.risk.behavioral_guard import (
    BehavioralGuardStatus,
    record_trade_outcome,
    is_symbol_locked,
    check_behavioral_guard,
    get_behavioral_guard_status,
    reset_guard as reset_behavioral_guard,
)

# Deterministic Devil Checks
from mjonai.risk.devil_checks import (
    DevilCheckResult,
    check_gap_risk,
    check_liquidity,
    check_data_quality,
    check_pattern_memory,
    check_correlation,
    check_real_rr,
    check_portfolio_limits,
    check_event_risk,
    run_all_devil_checks,
    evaluate_devil_checks,
)

# Multi-Tier Emergency Circuit Breakers
from mjonai.risk.emergency_triggers import (
    EmergencyRiskStatus,
    restore_risk_state,
    reset_daily_state as reset_emergency_daily_state,
    set_manual_pause,
    clear_manual_pause,
    is_trading_allowed,
    get_emergency_risk_status,
    update_consecutive_losses,
    check_daily_loss,
)

# Directional GARCH Overnight Gap Risk
from mjonai.risk.gap_risk import (
    GapRiskResult,
    calculate_overnight_gap_risk,
    evaluate_gap_risk,
)

# Special Macro Events & Market Regimes
from mjonai.risk.special_modes import (
    SpecialModesResult,
    is_crisis_mode,
    is_budget_day_blackout,
    is_rbi_policy_blackout,
    calculate_volatility_size_multiplier,
    check_special_modes,
    evaluate_special_modes,
    set_crisis_override,
)

# Sizing, 3-Tranche Scaling & Trade Levels
from mjonai.risk.trade_risk import (
    TradeRiskLevels,
    find_swing_low,
    find_swing_high,
    get_market_weight,
    get_confidence_weight,
    calculate_costs,
    split_tranche_quantities,
    calculate_position_size,
    validate_trade,
    calculate_trade_levels,
    evaluate_trade_risk_levels,
)

__all__ = [
    # Behavioral Guard
    "BehavioralGuardStatus",
    "record_trade_outcome",
    "is_symbol_locked",
    "check_behavioral_guard",
    "get_behavioral_guard_status",
    "reset_behavioral_guard",

    # Devil Checks
    "DevilCheckResult",
    "check_gap_risk",
    "check_liquidity",
    "check_data_quality",
    "check_pattern_memory",
    "check_correlation",
    "check_real_rr",
    "check_portfolio_limits",
    "check_event_risk",
    "run_all_devil_checks",
    "evaluate_devil_checks",

    # Emergency Triggers
    "EmergencyRiskStatus",
    "restore_risk_state",
    "reset_emergency_daily_state",
    "set_manual_pause",
    "clear_manual_pause",
    "is_trading_allowed",
    "get_emergency_risk_status",
    "update_consecutive_losses",
    "check_daily_loss",

    # Gap Risk
    "GapRiskResult",
    "calculate_overnight_gap_risk",
    "evaluate_gap_risk",

    # Special Modes
    "SpecialModesResult",
    "is_crisis_mode",
    "is_budget_day_blackout",
    "is_rbi_policy_blackout",
    "calculate_volatility_size_multiplier",
    "check_special_modes",
    "evaluate_special_modes",
    "set_crisis_override",

    # Trade Risk
    "TradeRiskLevels",
    "find_swing_low",
    "find_swing_high",
    "get_market_weight",
    "get_confidence_weight",
    "calculate_costs",
    "split_tranche_quantities",
    "calculate_position_size",
    "validate_trade",
    "calculate_trade_levels",
    "evaluate_trade_risk_levels",
]
