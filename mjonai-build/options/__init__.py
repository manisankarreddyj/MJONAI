"""
Module: options/__init__.py
Purpose: SOTA Comprehensive Package initialization & exports for MJONAI Options Intelligence Suite.
"""

from options.greeks import (
    calculate_black_scholes_greeks,
    calculate_implied_volatility,
    OptionGreeksResult,
)
from options.chain_engine import (
    get_atm_strike,
    calculate_pcr,
    calculate_max_pain,
    calculate_expected_move,
    select_optimal_strike,
    build_option_chain_ladder,
    OptionChainLadderResult,
)
from options.oi_scanner import (
    classify_oi_buildup,
    calculate_gamma_exposure,
    scan_oi_anomalies,
    OIScanResult,
)
from options.directional_options import (
    generate_directional_option_trade,
    generate_vertical_spread_trade,
    DirectionalOptionTradeResult,
    VerticalSpreadTradeResult,
    LOT_SIZES,
)
from options.volatility import (
    calculate_iv_rank,
    calculate_iv_percentile,
    classify_volatility_regime,
    calculate_iv_crush,
    analyze_volatility_term_structure,
    calculate_volatility_skew,
    get_strike_delta_adjustment,
    VolatilitySkewResult,
    VolatilityRegimeResult,
)
from options.multi_leg import (
    construct_short_strangle_trade,
    construct_iron_condor_trade,
    calculate_strangle_rebalance_adjustment,
    calculate_atm_straddle_expected_range,
    ShortStrangleTradeResult,
    IronCondorTradeResult,
)

__all__ = [
    # 1. Greeks & BSM
    "calculate_black_scholes_greeks",
    "calculate_implied_volatility",
    "OptionGreeksResult",
    # 2. Chain & ATM Engine
    "get_atm_strike",
    "calculate_pcr",
    "calculate_max_pain",
    "calculate_expected_move",
    "select_optimal_strike",
    "build_option_chain_ladder",
    "OptionChainLadderResult",
    # 3. Open Interest & Gamma Flow
    "classify_oi_buildup",
    "calculate_gamma_exposure",
    "scan_oi_anomalies",
    "OIScanResult",
    # 4. Directional Options & Spreads
    "generate_directional_option_trade",
    "generate_vertical_spread_trade",
    "DirectionalOptionTradeResult",
    "VerticalSpreadTradeResult",
    "LOT_SIZES",
    # 5. Volatility Surface, Skew & IV Rank
    "calculate_iv_rank",
    "calculate_iv_percentile",
    "classify_volatility_regime",
    "calculate_iv_crush",
    "analyze_volatility_term_structure",
    "calculate_volatility_skew",
    "get_strike_delta_adjustment",
    "VolatilitySkewResult",
    "VolatilityRegimeResult",
    # 6. Non-Directional Multi-Leg & Delta Hedging
    "construct_short_strangle_trade",
    "construct_iron_condor_trade",
    "calculate_strangle_rebalance_adjustment",
    "calculate_atm_straddle_expected_range",
    "ShortStrangleTradeResult",
    "IronCondorTradeResult",
]
